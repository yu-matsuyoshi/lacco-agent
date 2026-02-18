"""
Kintai Agent Frontend - Streamlit App
工数管理エージェントのフロントエンド
"""
import streamlit as st
import boto3
import requests
import urllib.parse
from botocore.exceptions import ClientError

from config import (
    REGION,
    USER_POOL_ID,
    CLIENT_ID,
    RUNTIME_ARN,
    API_TIMEOUT,
)

# ページ設定
st.set_page_config(
    page_title="工数管理エージェント",
    page_icon="📊",
    layout="wide",
)


def authenticate(username: str, password: str) -> dict | None:
    """
    Cognito認証を実行

    Args:
        username: ユーザー名
        password: パスワード

    Returns:
        認証結果（トークン情報）またはNone
    """
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


def call_agent(access_token: str, action: str, **kwargs) -> dict | None:
    """
    AgentCore Runtimeを呼び出し

    Args:
        access_token: Cognitoアクセストークン
        action: アクション名
        **kwargs: 追加パラメータ

    Returns:
        レスポンス辞書またはNone
    """
    encoded_arn = urllib.parse.quote(RUNTIME_ARN, safe='')
    url = f"https://bedrock-agentcore.{REGION}.amazonaws.com/runtimes/{encoded_arn}/invocations"

    payload = {"action": action, **kwargs}

    try:
        response = requests.post(
            url,
            headers={
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            },
            json=payload,
            timeout=API_TIMEOUT
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        st.error("リクエストがタイムアウトしました。再度お試しください。")
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"APIエラー: {str(e)}")
        return None


def show_login_page():
    """ログインページを表示"""
    st.title("📊 工数管理エージェント")
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
                            st.rerun()


def show_main_page():
    """メインページを表示"""
    # ヘッダー
    col1, col2 = st.columns([4, 1])
    with col1:
        st.title("📊 工数管理エージェント")
    with col2:
        st.write(f"👤 {st.session_state.get('username', '')}")
        if st.button("ログアウト"):
            st.session_state.clear()
            st.rerun()

    st.markdown("---")

    # タブ
    tab1, tab2 = st.tabs(["💬 テキスト入力", "📅 カレンダー連携"])

    with tab1:
        show_text_input_tab()

    with tab2:
        show_calendar_tab()


def show_text_input_tab():
    """テキスト入力タブ"""
    st.subheader("自然言語で工数を入力")

    # 入力例
    with st.expander("入力例を見る"):
        st.markdown("""
        - 「明日はプロジェクトAで開発作業を100%」
        - 「今日はプロジェクトAで50%、メンテナンス業務で50%」
        - 「1/27はECサイト構築で設計を80%、会議を20%」
        - 「プロジェクト一覧を教えてください」
        """)

    # 入力フォーム
    text_input = st.text_area(
        "工数内容を入力してください",
        placeholder="例: 明日はプロジェクトAで開発作業を100%",
        height=100
    )

    if st.button("コマンド生成", type="primary", use_container_width=True):
        if not text_input:
            st.warning("テキストを入力してください")
        else:
            with st.spinner("コマンドを生成中..."):
                result = call_agent(
                    st.session_state['access_token'],
                    "generate_from_text",
                    text=text_input
                )

                if result:
                    show_result(result)


def show_calendar_tab():
    """カレンダー連携タブ（未実装）"""
    st.subheader("Google Calendarから工数を生成")

    st.info("""
    📅 **Google Calendar連携は現在無効化されています**

    この機能を有効にするには、以下の設定が必要です：
    1. Google Cloud ConsoleでOAuth2クライアントを作成
    2. AgentCore IdentityにOAuth2 Credential Providerを登録
    3. CDKスタックのGoogle Calendar MCP Server Targetを有効化
    """)


def show_result(result: dict):
    """結果を表示"""
    if result.get('success'):
        st.success("コマンドを生成しました")

        # コマンド表示
        commands = result.get('commands', [])
        if commands:
            st.subheader("生成されたコマンド")
            for cmd in commands:
                st.code(cmd, language="bash")

        # 説明
        explanation = result.get('explanation', '')
        if explanation:
            st.subheader("説明")
            st.write(explanation)

        # エントリー詳細
        entries = result.get('entries', [])
        if entries:
            st.subheader("工数エントリー")
            for entry in entries:
                with st.container():
                    cols = st.columns([2, 2, 1, 1])
                    cols[0].write(f"📁 {entry.get('project_name', 'N/A')}")
                    cols[1].write(f"🏷️ {entry.get('category_name', 'N/A')}")
                    cols[2].write(f"📊 {entry.get('percentage', 0)}%")
                    confidence = entry.get('confidence', 'low')
                    confidence_emoji = {"high": "✅", "medium": "⚠️", "low": "❓"}.get(confidence, "❓")
                    cols[3].write(f"{confidence_emoji} {confidence}")

        # 警告
        warnings = result.get('warnings', [])
        if warnings:
            st.subheader("警告")
            for warning in warnings:
                st.warning(warning)

        # 提案
        suggestions = result.get('suggestions', [])
        if suggestions:
            st.subheader("提案")
            for suggestion in suggestions:
                st.info(suggestion)
    else:
        st.error("コマンド生成に失敗しました")

        error = result.get('error', '')
        if error:
            st.error(error)

        explanation = result.get('explanation', '')
        if explanation:
            st.write(explanation)


def main():
    """メインエントリーポイント"""
    # セッション初期化
    if 'authenticated' not in st.session_state:
        st.session_state['authenticated'] = False

    # 認証状態に応じてページ表示
    if st.session_state['authenticated']:
        show_main_page()
    else:
        show_login_page()


if __name__ == "__main__":
    main()
