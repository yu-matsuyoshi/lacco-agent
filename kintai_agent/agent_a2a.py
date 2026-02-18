"""
Kintai Agent - A2A Server
AgentCore Runtime (A2Aプロトコル) 用

Memory統合版: リクエストごとにsession_managerを作成してAgentに渡す
"""

import os
from datetime import datetime
from typing import Optional

from strands import Agent
from strands.multiagent.a2a import A2AServer, StrandsA2AExecutor
from strands.tools.mcp.mcp_client import MCPClient
from mcp.client.streamable_http import streamable_http_client
from a2a.server.agent_execution.context import RequestContext
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore

from core import KintaiAgentCore

# Memory統合（オプショナル）
try:
    from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig
    from bedrock_agentcore.memory.integrations.strands.session_manager import (
        AgentCoreMemorySessionManager,
    )
    MEMORY_AVAILABLE = True
except ImportError:
    MEMORY_AVAILABLE = False
    print("⚠️ Memory integration not available (bedrock-agentcore[strands-agents] not installed)")


def build_a2a_system_prompt() -> str:
    """A2A用システムプロンプトを構築（自然言語レスポンス）"""
    today = datetime.now().strftime("%Y/%m/%d")
    return f"""あなたは工数管理システム（OA Lacco APP）のアシスタントです。
ユーザーと自然な会話をしながら、工数入力をサポートします。

## 今日の日付
{today}

## 役割
- ユーザーの自然言語入力を解析
- プロジェクト（案件）と区分を**別々に**特定
- OA Lacco APPのコマンドを生成
- 結果をわかりやすく説明

## 利用可能なツール
1. get_projects: プロジェクト一覧取得
2. get_categories: 区分一覧取得
3. validate_percentage: 割合検証（合計100%か確認）

**重要**: 工数登録の前に、必ず get_projects と get_categories を呼び出して、
正確なプロジェクトIDと区分IDを確認してください。

## コマンド形式
OA Lacco APP add <日付> <案件ID> <区分ID> <割合>%

## 日付の解釈
- 「今日」→ {today}
- 「明日」→ 翌日の日付
- 「昨日」→ 前日の日付
- 具体的な日付指定もOK（例: 2/18, 2月18日）

## プロジェクトと区分の区別（重要）

**プロジェクト（案件）** と **区分（作業種別）** は別の概念です。

- **プロジェクト**: 案件名・プロジェクト名（例：ECサイトリニューアル、基幹システム刷新PJ）
- **区分**: 作業の種類（例：開発、設計、保守、会議、テスト）

プロジェクト名に「開発」「保守」などの単語が含まれていても、
それは区分ではなくプロジェクト名の一部です。

例：
- 「モバイルアプリ開発」プロジェクトで「保守」作業 → プロジェクト: モバイルアプリ開発, 区分: 保守
- 「システム保守運用」プロジェクトで「開発」作業 → プロジェクト: システム保守運用, 区分: 開発

## 曖昧な入力への対応

区分が明示されていない場合や判別が難しい場合は、**必ずユーザーに確認**してください。
デフォルトで「開発」を仮定せず、確認を求めてください。

確認例：
- 「作業区分は何になりますか？（開発、設計、保守、会議など）」
- 「"〇〇"はプロジェクト名でよろしいですか？作業区分も教えてください」

## 応答方法
自然な日本語で応答してください。

**プロジェクト一覧や区分一覧を聞かれた場合:**
ツールで取得した情報を見やすい形式で表示してください。

**工数登録の依頼の場合:**
1. まず入力内容を理解したことを伝える
2. 生成したコマンドを表示
3. 登録内容の説明を添える

例:
「ECサイトリニューアル案件で設計作業を100%で登録しますね。

生成されたコマンド:
```
OA Lacco APP add {today} 12345 2 100%
```

- 日付: {today}
- プロジェクト: ECサイトリニューアル
- 区分: 設計
- 割合: 100%」

## 注意事項
- 割合の合計は必ず100%になるようにする
- 不明なプロジェクトは類似候補を提案
- 曖昧な入力は確認を求める（特に区分）
- フレンドリーで丁寧な口調で応答
"""


def create_session_manager(
    session_id: str,
    actor_id: str,
) -> Optional["AgentCoreMemorySessionManager"]:
    """
    AgentCoreMemorySessionManagerを作成

    Args:
        session_id: セッションID（A2Aリクエストから取得）
        actor_id: アクターID（認証済みユーザーID）

    Returns:
        AgentCoreMemorySessionManager または None
    """
    if not MEMORY_AVAILABLE:
        return None

    memory_id = os.environ.get("AGENTCORE_MEMORY_ID")
    if not memory_id:
        print("⚠️ Memory not configured (AGENTCORE_MEMORY_ID not set)")
        return None

    # session_idは33文字以上必要
    if len(session_id) < 33:
        session_id = session_id + "-" + "0" * (33 - len(session_id) - 1)

    try:
        config = AgentCoreMemoryConfig(
            memory_id=memory_id,
            session_id=session_id,
            actor_id=actor_id,
        )

        session_manager = AgentCoreMemorySessionManager(
            agentcore_memory_config=config,
            region_name=os.environ.get("AWS_REGION", "us-east-1"),
        )

        print(f"✅ Memory session manager created: session={session_id[:20]}...")
        return session_manager

    except Exception as e:
        print(f"❌ Failed to create session manager: {e}")
        return None


core = KintaiAgentCore(
    gateway_url=os.getenv("GATEWAY_URL"),
    model_id=os.getenv("MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0"),
    region=os.getenv("AWS_REGION", "us-east-1"),
)


class KintaiA2AExecutor(StrandsA2AExecutor):
    """
    カスタムA2A Executor

    各リクエストで:
    1. context_idからsession_managerを作成（Memory統合）
    2. 新しいGatewayトークンを取得
    3. MCPClientを作成してツールを取得
    4. リクエスト用Agentを作成（session_manager付き）
    5. Agent実行
    6. クリーンアップ
    """

    def __init__(self, agent: Agent, core: KintaiAgentCore, **kwargs):
        super().__init__(agent, **kwargs)
        self.core = core
        self._mcp_client: Optional[MCPClient] = None

    async def _execute_streaming(self, context: RequestContext, updater) -> None:
        """
        リクエストごとにMCPClientとAgentを作成（Memory統合）
        """
        # A2Aリクエストからセッション情報を取得
        # context_idは会話コンテキストを表す（session_idとして使用）
        context_id = context.context_id or "default-context-id"
        # actor_idはユーザー識別子（将来的にはCognito subを使用）
        actor_id = "default-actor"

        print(f"🔵 A2A: Request started - context_id={context_id[:30]}...")

        # 1. session_managerを作成（Memory統合）
        session_manager = create_session_manager(context_id, actor_id)

        # 2. 新しいトークンを取得
        print("🔐 A2A: Getting new Gateway token for this request...")
        token = await self.core.get_gateway_token()

        tools = []
        if token and self.core.gateway_url:
            # 3. MCPClientを作成（httpxクライアント経由で認証ヘッダーを設定）
            print("🔌 A2A: Creating MCPClient...")
            import httpx
            http_client = httpx.AsyncClient(
                headers={"Authorization": f"Bearer {token}"},
                timeout=300.0
            )
            self._mcp_client = MCPClient(
                lambda: streamable_http_client(
                    self.core.gateway_url,
                    http_client=http_client
                )
            )

            try:
                # MCPClientコンテキスト内で実行
                with self._mcp_client:
                    # ツールを取得
                    tools = list(self._mcp_client.list_tools_sync())
                    print(f"✅ A2A: Loaded {len(tools)} tools from Gateway")

                    # 4. リクエスト用Agentを作成（session_manager付き）
                    request_agent = Agent(
                        model=self.core.model,
                        system_prompt=build_a2a_system_prompt(),
                        tools=tools,
                        session_manager=session_manager,
                        name="kintai-agent",
                        description="工数管理エージェント - 自然言語から工数入力コマンドを生成",
                    )
                    memory_status = "enabled" if session_manager else "disabled"
                    print(f"✅ A2A: Request Agent created - tools={len(tools)}, memory={memory_status}")

                    # 5. 一時的にselfのagentを差し替えて実行
                    original_agent = self.agent
                    self.agent = request_agent
                    try:
                        await super()._execute_streaming(context, updater)
                    finally:
                        self.agent = original_agent

            finally:
                # 6. クリーンアップ
                self._mcp_client = None
                print("✅ A2A: MCPClient cleaned up")
        else:
            print("⚠️ A2A: Gateway token or URL not available, running without tools")
            # トークンなしで実行（Memory付きのAgentのみ）
            request_agent = Agent(
                model=self.core.model,
                system_prompt=build_a2a_system_prompt(),
                tools=[],
                session_manager=session_manager,
                name="kintai-agent",
                description="工数管理エージェント - 自然言語から工数入力コマンドを生成",
            )
            original_agent = self.agent
            self.agent = request_agent
            try:
                await super()._execute_streaming(context, updater)
            finally:
                self.agent = original_agent


class KintaiA2AServer(A2AServer):
    """
    カスタムA2A Server

    KintaiA2AExecutorを使用するようにオーバーライド
    """

    def __init__(self, agent: Agent, core: KintaiAgentCore, **kwargs):
        # 親クラスの初期化を呼ばず、必要な部分だけ設定
        self.host = kwargs.get('host', '127.0.0.1')
        self.port = kwargs.get('port', 9000)
        self.version = kwargs.get('version', '0.0.1')

        http_url = kwargs.get('http_url')
        serve_at_root = kwargs.get('serve_at_root', False)

        if http_url:
            self.public_base_url, self.mount_path = self._parse_public_url(http_url)
            self.http_url = http_url.rstrip("/") + "/"
            self._http_url_explicit = True
            if serve_at_root:
                self.mount_path = ""
        else:
            self.public_base_url = f"http://{self.host}:{self.port}"
            self.http_url = f"{self.public_base_url}/"
            self.mount_path = ""
            self._http_url_explicit = False

        self.strands_agent = agent
        self.name = self.strands_agent.name
        self.description = self.strands_agent.description

        # AgentCapabilitiesをインポート
        from a2a.types import AgentCapabilities
        self.capabilities = AgentCapabilities(streaming=True)

        # カスタムExecutorを使用
        enable_streaming = kwargs.get('enable_a2a_compliant_streaming', False)
        self.request_handler = DefaultRequestHandler(
            agent_executor=KintaiA2AExecutor(
                agent,
                core,
                enable_a2a_compliant_streaming=enable_streaming
            ),
            task_store=kwargs.get('task_store') or InMemoryTaskStore(),
            queue_manager=kwargs.get('queue_manager'),
            push_config_store=kwargs.get('push_config_store'),
            push_sender=kwargs.get('push_sender'),
        )
        self._agent_skills = kwargs.get('skills')
        print("✅ KintaiA2AServer initialized with custom executor")


# ツールなしでAgentを作成（ツールはリクエスト時に動的に登録）
agent = Agent(
    model=core.model,
    system_prompt=build_a2a_system_prompt(),
    tools=[],  # 空のツールリスト
    name="kintai-agent",
    description="工数管理エージェント - 自然言語から工数入力コマンドを生成",
)


# AgentCoreが提供するRuntimeの外部URL
# ローカル開発時はフォールバック
RUNTIME_URL = os.getenv("AGENTCORE_RUNTIME_URL", "http://127.0.0.1:9000/")

# カスタムA2A Server作成
a2a_server = KintaiA2AServer(
    agent=agent,
    core=core,
    host="0.0.0.0",
    port=9000,
    http_url=RUNTIME_URL,
    serve_at_root=True,
    enable_a2a_compliant_streaming=True,
)

# AgentCore Runtime用FastAPI app
app = a2a_server.to_fastapi_app()


if __name__ == "__main__":
    a2a_server.serve()
