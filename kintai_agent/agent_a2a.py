"""
Kintai Agent - A2A Server
AgentCore Runtime (A2Aプロトコル) 用

Memory統合版: リクエストごとにsession_managerを作成してAgentに渡す
"""

import os
from typing import Optional

from strands import Agent
from strands.multiagent.a2a import A2AServer, StrandsA2AExecutor
from strands.tools.mcp.mcp_client import MCPClient
from mcp.client.streamable_http import streamable_http_client
from a2a.server.agent_execution.context import RequestContext
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore

from core import KintaiAgentCore, build_system_prompt

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
            region_name=os.environ.get("AWS_REGION", "ap-northeast-1"),
        )

        print(f"✅ Memory session manager created: session={session_id[:20]}...")
        return session_manager

    except Exception as e:
        print(f"❌ Failed to create session manager: {e}")
        return None


core = KintaiAgentCore(
    gateway_url=os.getenv("GATEWAY_URL"),
    model_id=os.getenv("MODEL_ID", "jp.anthropic.claude-sonnet-4-6"),
    region=os.getenv("AWS_REGION", "ap-northeast-1"),
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
                        system_prompt=build_system_prompt(output_format="natural"),
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
                system_prompt=build_system_prompt(output_format="natural"),
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
    system_prompt=build_system_prompt(output_format="natural"),
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
