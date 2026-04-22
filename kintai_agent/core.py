"""
Kintai Agent - Core Logic
共通ロジック（HTTP版・A2A版両方で使用）
"""
from typing import Optional, List, Dict, Any
import os
import json
import re
import asyncio
import time
from datetime import datetime
from pathlib import Path
from strands import Agent
from strands.models import BedrockModel
import boto3
from botocore.exceptions import ClientError


def load_commands_reference() -> str:
    """コマンドリファレンスを読み込む"""
    commands_path = Path(__file__).parent / "prompts" / "commands.md"
    try:
        return commands_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return "（コマンドリファレンスが見つかりません）"

# MCP imports
try:
    from strands.tools.mcp.mcp_client import MCPClient
    from mcp.client.streamable_http import streamable_http_client
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    MCPClient = None
    streamable_http_client = None

from bedrock_agentcore.identity.auth import requires_access_token

# Memory imports
try:
    from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig
    from bedrock_agentcore.memory.integrations.strands.session_manager import (
        AgentCoreMemorySessionManager,
    )
    MEMORY_AVAILABLE = True
except ImportError:
    MEMORY_AVAILABLE = False
    AgentCoreMemoryConfig = None
    AgentCoreMemorySessionManager = None

from models import (
    CommandResult,
    WorkEntry,
)
from command_generator import CommandGenerator

# Credential Provider名（CLIで作成したもの）
GATEWAY_OAUTH_PROVIDER_NAME = "kintai-gateway-m2m"


def create_session_manager(
    session_id: str,
    actor_id: str,
    memory_id: Optional[str] = None,
) -> Optional["AgentCoreMemorySessionManager"]:
    """
    AgentCoreMemorySessionManagerを作成

    Args:
        session_id: セッションID
        actor_id: アクターID（ユーザーID）
        memory_id: Memory ID（省略時は環境変数から取得）

    Returns:
        AgentCoreMemorySessionManager または None
    """
    if not MEMORY_AVAILABLE:
        print("⚠️ Memory integration not available")
        return None

    memory_id = memory_id or os.environ.get("AGENTCORE_MEMORY_ID_HTTP")
    if not memory_id:
        print("⚠️ Memory not configured (AGENTCORE_MEMORY_ID_HTTP not set)")
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


def _build_base_sections(today: str) -> str:
    """共通部分: role, context, tools, commands, rules"""
    commands_ref = load_commands_reference()

    return f"""<role>
あなたは工数管理システム（OA Lacco APP）のアシスタントです。
ユーザーの自然言語入力を解析し、OA Lacco APPのコマンドを生成します。
</role>

<context>
今日の日付: {today}
</context>

<tools>
工数登録の前に、必ず以下のツールを使用してプロジェクトIDと区分IDを確認してください：
- get_projects: プロジェクト一覧取得
- get_categories: 区分一覧取得
- validate_percentage: 割合検証（合計100%か確認）
</tools>

<commands>
{commands_ref}
</commands>

<rules>
【日付の解釈】
- 「今日」→ {today}
- 「明日」→ 翌日の日付
- 「昨日」→ 前日の日付
- 具体的な日付指定もOK（例: 2/18, 2月18日）

【プロジェクトと区分の区別（重要）】
プロジェクト（案件）と区分（作業種別）は別の概念です。

- プロジェクト: 案件名・プロジェクト名（例：ECサイトリニューアル、基幹システム刷新PJ）
- 区分: 作業の種類（例：開発、設計、保守、会議、テスト）

プロジェクト名に「開発」「保守」などの単語が含まれていても、
それは区分ではなくプロジェクト名の一部です。

例：
- 「モバイルアプリ開発」プロジェクトで「保守」作業 → プロジェクト: モバイルアプリ開発, 区分: 保守
- 「システム保守運用」プロジェクトで「開発」作業 → プロジェクト: システム保守運用, 区分: 開発

【曖昧な入力への対応】
区分が明示されていない場合や判別が難しい場合は、必ずユーザーに確認してください。
デフォルトで「開発」を仮定せず、確認を求めてください。

【割合】
割合の合計は必ず100%になるようにしてください。
</rules>
"""


def _build_json_output_section() -> str:
    """HTTP版: JSON出力形式"""
    return """<output_format>
必ず以下のJSON形式で出力してください：

```json
{
  "success": true,
  "commands": [
    "add 2026/01/27 12345 1 50%"
  ],
  "explanation": "プロジェクトAで開発作業を50%実施",
  "warnings": [],
  "suggestions": [],
  "entries": [
    {
      "date": "2026/01/27",
      "project_id": 12345,
      "project_name": "プロジェクトA",
      "category_id": 1,
      "category_name": "開発",
      "percentage": 50,
      "confidence": "high",
      "reason": "完全一致"
    }
  ]
}
```

エラーの場合:
```json
{
  "success": false,
  "commands": [],
  "explanation": "エラーの説明",
  "warnings": ["警告"],
  "suggestions": ["提案"],
  "entries": []
}
```
</output_format>
"""


def _build_natural_response_section(today: str) -> str:
    """A2A版: 自然言語出力形式"""
    return f"""<response_format>
自然な日本語で応答してください。

【プロジェクト一覧や区分一覧を聞かれた場合】
ツールで取得した情報を見やすい形式で表示してください。

【工数登録の依頼の場合】
1. まず入力内容を理解したことを伝える
2. 生成したコマンドを表示
3. 登録内容の説明を添える

例（単日登録）:
「ECサイトリニューアル案件で設計作業を100%で登録しますね。

生成されたコマンド:
```
add {today} 12345 2 100%
```

- 日付: {today}
- プロジェクト: ECサイトリニューアル
- 区分: 設計
- 割合: 100%」

例（月全体登録）:
「2月全体にECサイトリニューアル案件で開発作業を50%で登録しますね。

生成されたコマンド:
```
add -r 2026/02 12345 1 50%
```
※ 2月の全営業日に登録されます」

【コピー・削除・確認の依頼の場合】

例（コピー）:
「昨日の工数を今日にコピーしますね。

生成されたコマンド:
```
cp 2026/02/17 .
```」

例（削除）:
「2月18日の工数を削除しますね。

生成されたコマンド:
```
rm 2026/02/18
```

例（確認）:
「今月の工数を確認しますね。

コマンド:
```
ls now
```」
</response_format>

<guidelines>
- 不明なプロジェクトは類似候補を提案
- 曖昧な入力は確認を求める（特に区分）
- フレンドリーで丁寧な口調で応答
</guidelines>
"""


def build_system_prompt(output_format: str = "json") -> str:
    """
    システムプロンプトを構築

    Args:
        output_format: "json"（HTTP版）または "natural"（A2A版）

    Returns:
        システムプロンプト文字列
    """
    today = datetime.now().strftime("%Y/%m/%d")
    base = _build_base_sections(today)

    if output_format == "natural":
        return base + _build_natural_response_section(today)
    else:
        return base + _build_json_output_section()


class KintaiAgentCore:
    """
    工数管理エージェント - コアロジック

    HTTP版・A2A版で共通して使用するロジックを提供します。
    """

    # トークンキャッシュの有効期間（秒）- 5分のバッファを持たせる
    TOKEN_CACHE_BUFFER_SECONDS = 300  # 5分
    # DynamoDBキャッシュのキー
    TOKEN_CACHE_KEY = "gateway_m2m_token"

    def __init__(
        self,
        gateway_url: Optional[str] = None,
        model_id: str = "jp.anthropic.claude-sonnet-4-6",
        region: str = "ap-northeast-1",
    ):
        """
        エージェントを初期化

        Args:
            gateway_url: AgentCore Gateway URL
            model_id: 使用するBedrockモデルID
            region: AWSリージョン
        """
        self.gateway_url = gateway_url or os.getenv("GATEWAY_URL")
        self.model_id = model_id
        self.region = region

        # DynamoDBテーブル名（環境変数から取得）
        self.token_cache_table = os.getenv("TOKEN_CACHE_TABLE")

        # DynamoDBクライアント（トークンキャッシュ用）
        self._dynamodb = None
        if self.token_cache_table:
            self._dynamodb = boto3.resource('dynamodb', region_name=self.region)
            print(f"✅ DynamoDB token cache enabled: {self.token_cache_table}")
        else:
            print("⚠️ TOKEN_CACHE_TABLE not set, using in-memory cache only")

        # フォールバック用のインメモリキャッシュ
        self._cached_token: Optional[str] = None
        self._token_expires_at: float = 0

        # Bedrockモデルを初期化
        self.model = BedrockModel(
            model_id=self.model_id,
            region_name=self.region,
            temperature=0.3,
            max_tokens=4096,
        )

        # システムプロンプト
        self.system_prompt = build_system_prompt()

    def _get_cached_token_from_dynamodb(self) -> Optional[tuple[str, float]]:
        """
        DynamoDBからキャッシュされたトークンを取得

        Returns:
            (token, expires_at) または None
        """
        if not self._dynamodb or not self.token_cache_table:
            return None

        try:
            table = self._dynamodb.Table(self.token_cache_table)
            response = table.get_item(
                Key={'cache_key': self.TOKEN_CACHE_KEY}
            )

            if 'Item' in response:
                item = response['Item']
                token = item.get('token')
                expires_at = float(item.get('expires_at', 0))
                return (token, expires_at)

            return None

        except ClientError as e:
            print(f"⚠️ DynamoDB get error: {e}")
            return None

    def _save_token_to_dynamodb(self, token: str, expires_at: float) -> bool:
        """
        トークンをDynamoDBにキャッシュ

        Args:
            token: アクセストークン
            expires_at: 有効期限（Unixタイムスタンプ）

        Returns:
            保存成功したかどうか
        """
        if not self._dynamodb or not self.token_cache_table:
            return False

        try:
            table = self._dynamodb.Table(self.token_cache_table)
            # TTLは有効期限の1時間後に設定（安全マージン）
            ttl = int(expires_at) + 3600

            table.put_item(
                Item={
                    'cache_key': self.TOKEN_CACHE_KEY,
                    'token': token,
                    'expires_at': int(expires_at),
                    'ttl': ttl,
                    'updated_at': int(time.time()),
                }
            )
            print(f"✅ Token saved to DynamoDB cache")
            return True

        except ClientError as e:
            print(f"⚠️ DynamoDB put error: {e}")
            return False

    async def get_gateway_token(self) -> Optional[str]:
        """
        @requires_access_tokenデコレータを使用してGateway用アクセストークンを取得
        M2M認証でAgentCore IdentityのCredential Providerと通信

        トークンはDynamoDBにキャッシュされ、全コンテナで共有されます。
        有効期限の5分前まで再利用され、Cognitoへのリクエスト数を削減します。
        """
        current_time = time.time()

        # 1. DynamoDBからキャッシュを確認（全コンテナ共有）
        cached = self._get_cached_token_from_dynamodb()
        if cached:
            token, expires_at = cached
            if current_time < expires_at - self.TOKEN_CACHE_BUFFER_SECONDS:
                print("✅ Using cached Gateway access token (from DynamoDB)")
                # インメモリにもキャッシュ（同一コンテナ内の高速化）
                self._cached_token = token
                self._token_expires_at = expires_at
                return token
            else:
                print("⚠️ DynamoDB cached token expired, fetching new one...")

        # 2. インメモリキャッシュを確認（フォールバック）
        if self._cached_token and current_time < self._token_expires_at - self.TOKEN_CACHE_BUFFER_SECONDS:
            print("✅ Using cached Gateway access token (in-memory)")
            return self._cached_token

        # 3. 新しいトークンを取得
        try:
            print(f"🔐 Getting Gateway access token via @requires_access_token")
            print(f"   Provider: {GATEWAY_OAUTH_PROVIDER_NAME}")

            @requires_access_token(
                provider_name=GATEWAY_OAUTH_PROVIDER_NAME,
                scopes=["gateway/invoke"],
                auth_flow="M2M",
            )
            async def get_token(*, access_token: str) -> str:
                return access_token

            token = await get_token(access_token="")
            print("✅ Gateway access token obtained via @requires_access_token")

            # トークンの有効期限（デフォルト1時間）
            expires_at = current_time + 3600

            # 4. DynamoDBにキャッシュ（全コンテナで共有）
            self._save_token_to_dynamodb(token, expires_at)

            # 5. インメモリにもキャッシュ
            self._cached_token = token
            self._token_expires_at = expires_at
            print(f"   Token cached until {time.strftime('%H:%M:%S', time.localtime(expires_at))}")

            return token

        except Exception as e:
            print(f"❌ Failed to get Gateway access token: {e}")
            import traceback
            traceback.print_exc()
            return None

    def get_gateway_token_sync(self) -> Optional[str]:
        """
        Gateway用アクセストークンを同期的に取得
        """
        if not self.gateway_url:
            return None

        try:
            try:
                loop = asyncio.get_running_loop()
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, self.get_gateway_token())
                    return future.result(timeout=30)
            except RuntimeError:
                return asyncio.run(self.get_gateway_token())
        except Exception as e:
            print(f"Warning: Failed to get Gateway OAuth2 token: {e}")
            import traceback
            traceback.print_exc()
            return None

    def create_mcp_client(self, token: str) -> "MCPClient":
        """
        MCPClientを作成

        Args:
            token: Gateway用アクセストークン

        Returns:
            MCPClient インスタンス
        """
        if not MCP_AVAILABLE:
            raise RuntimeError("MCP is not available")
        if not self.gateway_url:
            raise RuntimeError("GATEWAY_URL is not set")

        return MCPClient(
            lambda: streamable_http_client(
                self.gateway_url,
                headers={"Authorization": f"Bearer {token}"}
            )
        )

    def create_agent_with_tools(
        self,
        tools: list,
        session_manager: Optional["AgentCoreMemorySessionManager"] = None
    ) -> Agent:
        """
        ツール付きでAgentを作成

        Args:
            tools: ツールのリスト
            session_manager: セッションマネージャー（Memory統合用）

        Returns:
            Agent インスタンス
        """
        return Agent(
            model=self.model,
            system_prompt=self.system_prompt,
            tools=tools,
            session_manager=session_manager,
        )

    def parse_agent_response(self, response_str: str) -> CommandResult:
        """
        AgentのレスポンスをパースしてCommandResultに変換

        Args:
            response_str: Agentのレスポンス文字列

        Returns:
            CommandResult
        """
        try:
            # JSONブロックを抽出（```json ... ``` または { ... }）
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_str, re.DOTALL)
            if not json_match:
                json_match = re.search(r'(\{[^{]*"success"[^}]*\})', response_str, re.DOTALL)

            if json_match:
                json_str = json_match.group(1)
                result_data = json.loads(json_str)

                commands = result_data.get('commands', [])
                warnings = list(result_data.get('warnings', []))

                if commands:
                    is_valid, errors = CommandGenerator.validate_commands(commands)
                    if not is_valid:
                        warnings.extend(errors)

                    is_total_valid, total_msg, total = CommandGenerator.validate_percentage_total(commands)
                    if not is_total_valid:
                        warnings.append(total_msg)

                entries = []
                for entry_data in result_data.get('entries', []):
                    entries.append(WorkEntry(
                        date=entry_data.get('date', ''),
                        project_id=entry_data.get('project_id', 0),
                        project_name=entry_data.get('project_name', ''),
                        category_id=entry_data.get('category_id', 0),
                        category_name=entry_data.get('category_name', ''),
                        percentage=entry_data.get('percentage', 0),
                        confidence=entry_data.get('confidence', 'low'),
                        reason=entry_data.get('reason')
                    ))

                return CommandResult(
                    success=result_data.get('success', True),
                    commands=commands,
                    explanation=result_data.get('explanation', ''),
                    warnings=warnings,
                    suggestions=result_data.get('suggestions', []),
                    entries=entries
                )
            else:
                return CommandResult(
                    success=True,
                    commands=[response_str],
                    explanation="コマンドを生成しました",
                    warnings=["レスポンスがJSON形式ではありませんでした"],
                    suggestions=[],
                    entries=[]
                )

        except json.JSONDecodeError as e:
            return CommandResult(
                success=False,
                commands=[],
                explanation=f"JSONパースエラー: {str(e)}",
                warnings=[],
                suggestions=["エージェントのレスポンスを確認してください"],
                entries=[]
            )
        except Exception as e:
            return CommandResult(
                success=False,
                commands=[],
                explanation=f"エラーが発生しました: {str(e)}",
                warnings=[],
                suggestions=[],
                entries=[]
            )

    def run_with_mcp_context(
        self,
        text: str,
        session_id: Optional[str] = None,
        actor_id: str = "default-actor"
    ) -> str:
        """
        MCPClientコンテキスト内でAgentを実行

        Args:
            text: ユーザーの自然言語入力
            session_id: セッションID（Memory統合用）
            actor_id: アクターID（ユーザーID）

        Returns:
            Agentのレスポンス（文字列）

        Raises:
            RuntimeError: Gateway接続に失敗した場合
        """
        gateway_token = self.get_gateway_token_sync()

        if not self.gateway_url:
            raise RuntimeError("GATEWAY_URL is not set")
        if not gateway_token:
            raise RuntimeError("Failed to get Gateway OAuth2 token")

        # セッションマネージャーを作成（session_idがある場合）
        session_manager = None
        if session_id:
            session_manager = create_session_manager(session_id, actor_id)

        mcp_client = self.create_mcp_client(gateway_token)

        with mcp_client:
            tools = mcp_client.list_tools_sync()
            memory_status = "enabled" if session_manager else "disabled"
            print(f"✅ Loaded {len(tools)} tools from Gateway, memory={memory_status}")

            agent = self.create_agent_with_tools(tools, session_manager)
            response = agent(text)
            return str(response)

    def generate_from_text(
        self,
        text: str,
        session_id: Optional[str] = None,
        actor_id: str = "default-actor"
    ) -> CommandResult:
        """
        自然言語からコマンドを生成

        Args:
            text: ユーザーの自然言語入力
            session_id: セッションID（Memory統合用）
            actor_id: アクターID（ユーザーID）

        Returns:
            CommandResult: コマンド生成結果
        """
        try:
            response_str = self.run_with_mcp_context(text, session_id, actor_id)
            return self.parse_agent_response(response_str)
        except Exception as e:
            return CommandResult(
                success=False,
                commands=[],
                explanation=f"エラーが発生しました: {str(e)}",
                warnings=[],
                suggestions=[],
                entries=[]
            )

    def generate_from_calendar(self, date: str) -> CommandResult:
        """
        カレンダーからコマンドを生成（現在無効化）
        """
        return CommandResult(
            success=False,
            commands=[],
            explanation="Google Calendar連携は現在無効化されています。",
            warnings=[
                "この機能を有効にするには、以下の手順を実施してください：",
                "1. Task 16.1（Google Calendar OAuth2設定）を完了",
                "2. CDKスタックのGoogle Calendar MCP Server Targetのコメントを解除",
                "3. CDKを再デプロイ"
            ],
            suggestions=[
                "代わりに自然言語入力（generate_from_text）を使用してください"
            ],
            entries=[]
        )
