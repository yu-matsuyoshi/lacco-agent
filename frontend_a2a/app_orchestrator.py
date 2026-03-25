"""
共通A2Aクライアント - オーケストレータ版
A2AClientToolProviderを使用して複数のA2Aエージェントをツールとして呼び出す

使い方:
  streamlit run app_orchestrator.py
"""
import os
import streamlit as st
import boto3
from uuid import uuid4
from botocore.exceptions import ClientError

from strands import Agent
from strands.models import BedrockModel
from strands_tools.a2a_client import A2AClientToolProvider

from config import (
    REGION,
    USER_POOL_ID,
    CLIENT_ID,
    RUNTIME_ARN,
    API_TIMEOUT,
)

# ページ設定
st.set_page_config(
    page_title="共通A2Aクライアント (Orchestrator)",
    page_icon="🤖",
    layout="wide",
)

# エージェント設定（将来的には動的に取得）
AGENTS = {
    "kintai": {
        "name": "工数管理エージェント",
        "description": "工数入力を自然言語で行う",
        "url": None,  # 動的に設定
    },
    # 将来的に追加
    # "expense": {
    #     "name": "経費精算エージェント",
    #     "description": "経費精算を自然言語で行う",
    #     "url": "https://...",
    # },
}


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


def get_agent_base_url(runtime_arn: str) -> str:
    """Runtime ARNからA2AエージェントのベースURLを生成"""
    import urllib.parse
    encoded_arn = urllib.parse.quote(runtime_arn, safe='')
    return f"https://bedrock-agentcore.{REGION}.amazonaws.com/runtimes/{encoded_arn}/invocations/"


def create_orchestrator(access_token: str, agent_urls: list[str]) -> Agent:
    """
    オーケストレータエージェントを作成

    A2AClientToolProviderを使用して、複数のA2Aエージェントをツールとして登録
    """
    # A2Aエージェントをツールとして登録
    a2a_provider = A2AClientToolProvider(
        known_agent_urls=agent_urls,
        timeout=API_TIMEOUT,
        httpx_client_args={
            "headers": {"Authorization": f"Bearer {access_token}"},
            "timeout": float(API_TIMEOUT),
        },
    )

    # オーケストレータエージェントのモデル
    # boto3セッションを明示的に作成（SSO対応）
    import boto3
    session = boto3.Session(
        profile_name=os.environ.get("AWS_PROFILE"),
        region_name=REGION,
    )
    model = BedrockModel(
        model_id="apac.anthropic.claude-sonnet-4-20250514-v1:0",  # 推論プロファイル形式
        region_name=REGION,
        boto3_session=session,
    )

    # オーケストレータエージェント
    orchestrator = Agent(
        model=model,
        system_prompt="""あなたは複数のAIエージェントを統括するオーケストレータです。

ユーザーの要求に応じて、適切なエージェントにタスクを振り分けてください。

## 利用可能なツール

1. a2a_discover_agent(url): エージェントを発見・登録
2. a2a_list_discovered_agents(): 登録済みエージェント一覧を表示
3. a2a_send_message(message_text, target_agent_url): エージェントにメッセージを送信

## 振り分けルール

- 工数・勤怠に関する要求 → 工数管理エージェント
- 経費・精算に関する要求 → 経費精算エージェント（準備中）
- スケジュール・予定に関する要求 → スケジュール管理エージェント（準備中）

## 手順

1. まず a2a_list_discovered_agents() で利用可能なエージェントを確認
2. 適切なエージェントに a2a_send_message() でメッセージを送信
3. エージェントからの応答をユーザーに伝える

## 注意

- 複数のエージェントが必要な場合は、順番に呼び出してください
- エージェントが見つからない場合は、その旨をユーザーに伝えてください
""",
        tools=a2a_provider.tools,
    )

    return orchestrator


def send_message(orchestrator: Agent, user_message: str) -> str | None:
    """オーケストレータにメッセージを送信"""
    try:
        result = orchestrator(user_message)
        return str(result)
    except Exception as e:
        st.error(f"エラーが発生しました: {str(e)}")
        return None


def show_login_page():
    """ログインページを表示"""
    st.title("🤖 共通A2Aクライアント (Orchestrator)")
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
                            st.session_state['orchestrator'] = None
                            st.rerun()


def show_main_page():
    """メインページを表示"""
    # ヘッダー
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        st.title("🤖 共通A2Aクライアント (Orchestrator)")
    with col2:
        st.write(f"👤 {st.session_state.get('username', '')}")
    with col3:
        if st.button("新規会話"):
            st.session_state['messages'] = []
            st.session_state['orchestrator'] = None
            st.rerun()
        if st.button("ログアウト"):
            st.session_state.clear()
            st.rerun()

    st.markdown("---")

    # サイドバー: エージェント情報
    with st.sidebar:
        st.subheader("登録エージェント")

        # 現在登録されているエージェント
        agent_url = get_agent_base_url(RUNTIME_ARN)
        AGENTS["kintai"]["url"] = agent_url

        for agent_id, agent_info in AGENTS.items():
            if agent_info.get("url"):
                st.markdown(f"**{agent_info['name']}**")
                st.caption(agent_info['description'])
                st.markdown("---")

        st.caption("💡 オーケストレータが自動的に適切なエージェントを選択します")

    # 説明
    with st.expander("使い方"):
        st.markdown("""
        このクライアントはオーケストレータ方式です。

        **特徴:**
        - 複数のエージェントを自動的に振り分け
        - 適切なエージェントにタスクを委譲
        - 将来的に経費精算、スケジュール管理なども追加可能

        **入力例:**
        - 「プロジェクト一覧を教えてください」
        - 「今日はプロジェクトAで開発作業を100%」
        - 「明日の予定を確認して」（準備中）
        """)

    # オーケストレータを初期化（セッションに保持）
    if st.session_state.get('orchestrator') is None:
        with st.spinner("オーケストレータを初期化中..."):
            try:
                agent_urls = [info["url"] for info in AGENTS.values() if info.get("url")]
                orchestrator = create_orchestrator(
                    st.session_state['access_token'],
                    agent_urls,
                )
                st.session_state['orchestrator'] = orchestrator
                st.success("オーケストレータ準備完了")
            except Exception as e:
                st.error(f"オーケストレータの初期化に失敗: {str(e)}")
                return

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

        # オーケストレータからのレスポンスを取得
        with st.chat_message("assistant"):
            with st.spinner("エージェントに問い合わせ中..."):
                response = send_message(
                    st.session_state['orchestrator'],
                    prompt,
                )

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

    # 認証状態に応じてページ表示
    if st.session_state['authenticated']:
        show_main_page()
    else:
        show_login_page()


if __name__ == "__main__":
    main()
