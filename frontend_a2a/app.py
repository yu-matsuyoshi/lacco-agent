"""
Kintai Agent Frontend - Streamlit App (A2A版)
工数管理エージェントのフロントエンド（A2Aプロトコル対応）
"""
import streamlit as st
import boto3
import asyncio
import urllib.parse
from uuid import uuid4
from botocore.exceptions import ClientError

import httpx
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.types import Message, Part, Role, TextPart

from config import (
    REGION,
    USER_POOL_ID,
    CLIENT_ID,
    RUNTIME_ARN,
    API_TIMEOUT,
)

# ページ設定
st.set_page_config(
    page_title="工数管理エージェント (A2A)",
    page_icon="🤖",
    layout="wide",
)


def authenticate(username: str, password: str) -> dict | None:
    """Cognito認証を実行"""
    try:
        cognito = boto3.client('cognito-idp', region_name=REGION)
        response = cognito.initiate_auth(
            ClientId=CLIENT_ID,
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={
                'USERNAME': username,
                'PASSWORD': password
            }
        )
        return response['AuthenticationResult']
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'NotAuthorizedException':
            st.error("ユーザー名またはパスワードが正しくありません")
        elif error_code == 'UserNotFoundException':
            st.error("ユーザーが見つかりません")
        else:
            st.error(f"認証エラー: {error_code}")
        return None
    except Exception as e:
        st.error(f"予期しないエラー: {str(e)}")
        return None


async def call_a2a_agent(access_token: str, user_message: str, context_id: str) -> str | None:
    """
    A2Aプロトコルでエージェントを呼び出し

    Args:
        access_token: Cognitoアクセストークン
        user_message: ユーザーのメッセージ
        context_id: 会話コンテキストID（会話履歴を維持するため）

    Returns:
        エージェントのレスポンステキスト
    """
    encoded_arn = urllib.parse.quote(RUNTIME_ARN, safe='')
    base_url = f"https://bedrock-agentcore.{REGION}.amazonaws.com/runtimes/{encoded_arn}/invocations"

    # セッションIDにはcontext_idを使用（会話単位で一貫）
    session_id = context_id

    async with httpx.AsyncClient(
        headers={
            "Authorization": f"Bearer {access_token}",
            "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": session_id,
        },
        timeout=float(API_TIMEOUT)
    ) as http_client:
        # AgentCardを取得
        resolver = A2ACardResolver(
            httpx_client=http_client,
            base_url=base_url
        )
        agent_card = await resolver.get_agent_card()

        # クライアントを作成
        config = ClientConfig(httpx_client=http_client, streaming=False)
        factory = ClientFactory(config)
        client = factory.create(agent_card)

        # メッセージを作成（contextIdで会話履歴を維持）
        msg = Message(
            kind="message",
            role=Role.user,
            parts=[Part(root=TextPart(kind="text", text=user_message))],
            messageId=uuid4().hex,
            contextId=context_id,
        )

        # メッセージを送信してレスポンスを取得
        response_text = ""
        async for event in client.send_message(msg):
            if isinstance(event, Message):
                # Messageの場合
                for part in event.parts:
                    if hasattr(part, 'root') and hasattr(part.root, 'text'):
                        response_text += part.root.text
            elif isinstance(event, tuple) and len(event) >= 1:
                # Taskの場合 (tuple[Task, update_event])
                task = event[0]
                if hasattr(task, 'artifacts') and task.artifacts:
                    for artifact in task.artifacts:
                        if hasattr(artifact, 'parts'):
                            for part in artifact.parts:
                                if hasattr(part, 'root') and hasattr(part.root, 'text'):
                                    response_text += part.root.text

        return response_text if response_text else None


def send_message(user_message: str):
    """メッセージを送信してレスポンスを取得"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        response = loop.run_until_complete(
            call_a2a_agent(
                st.session_state['access_token'],
                user_message,
                st.session_state['context_id'],
            )
        )
        loop.close()
        return response
    except Exception as e:
        st.error(f"エラーが発生しました: {str(e)}")
        return None


def show_login_page():
    """ログインページを表示"""
    st.title("🤖 工数管理エージェント (A2A)")
    st.markdown("---")

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.subheader("ログイン")

        with st.form("login_form"):
            username = st.text_input("ユーザー名")
            password = st.text_input("パスワード", type="password")
            submitted = st.form_submit_button("ログイン", use_container_width=True)

            if submitted:
                if not username or not password:
                    st.error("ユーザー名とパスワードを入力してください")
                else:
                    with st.spinner("認証中..."):
                        auth_result = authenticate(username, password)
                        if auth_result:
                            st.session_state['authenticated'] = True
                            st.session_state['access_token'] = auth_result['AccessToken']
                            st.session_state['username'] = username
                            st.session_state['messages'] = []
                            # 会話コンテキストIDを生成（会話履歴維持用）
                            # 33文字以上必要なため、UUIDを2つ連結
                            st.session_state['context_id'] = uuid4().hex + uuid4().hex[:10]
                            st.rerun()


def show_main_page():
    """メインページを表示"""
    # ヘッダー
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        st.title("🤖 工数管理エージェント (A2A)")
    with col2:
        st.write(f"👤 {st.session_state.get('username', '')}")
    with col3:
        if st.button("新規会話"):
            # 新しい会話コンテキストを生成
            st.session_state['context_id'] = uuid4().hex + uuid4().hex[:10]
            st.session_state['messages'] = []
            st.rerun()
        if st.button("ログアウト"):
            st.session_state.clear()
            st.rerun()

    st.markdown("---")

    # 説明
    with st.expander("使い方"):
        st.markdown("""
        自然言語で工数に関する質問や指示ができます。

        **入力例:**
        - 「プロジェクト一覧を教えてください」
        - 「区分一覧を見せてください」
        - 「明日はプロジェクトAで開発作業を100%」
        - 「今日はプロジェクトAで50%、メンテナンス業務で50%」
        - 「1/27はECサイト構築で設計を80%、会議を20%」
        """)

    # チャット履歴を表示
    for message in st.session_state.get('messages', []):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # 入力フォーム
    if prompt := st.chat_input("メッセージを入力してください"):
        # ユーザーメッセージを追加
        st.session_state['messages'].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # エージェントからのレスポンスを取得
        with st.chat_message("assistant"):
            with st.spinner("考え中..."):
                response = send_message(prompt)

            if response:
                st.markdown(response)
                st.session_state['messages'].append({"role": "assistant", "content": response})
            else:
                error_msg = "レスポンスを取得できませんでした"
                st.error(error_msg)
                st.session_state['messages'].append({"role": "assistant", "content": f"❌ {error_msg}"})


def main():
    """メインエントリーポイント"""
    # セッション初期化
    if 'authenticated' not in st.session_state:
        st.session_state['authenticated'] = False
    if 'messages' not in st.session_state:
        st.session_state['messages'] = []
    if 'context_id' not in st.session_state:
        # 会話コンテキストIDを生成（33文字以上必要）
        st.session_state['context_id'] = uuid4().hex + uuid4().hex[:10]

    # 認証状態に応じてページ表示
    if st.session_state['authenticated']:
        show_main_page()
    else:
        show_login_page()


if __name__ == "__main__":
    main()
