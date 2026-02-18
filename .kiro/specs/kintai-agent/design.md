# 設計書

## 概要

工数管理エージェント（Kintai Agent）は、Strands Agentsフレームワークを使用して構築され、**Amazon Bedrock AgentCore Runtime**にデプロイされるAIエージェントです。ユーザーの自然言語入力やGoogle Calendarのイベントから、OA Lacco APPの工数入力コマンドを自動生成します。

インフラストラクチャは**AWS CDK（Python）**で定義され、以下のコンポーネントで構成されます：

**AWS環境（CDKでデプロイ）：**
1. **S3 Bucket**: マスタデータ（CSV）の保存
2. **Lambda Functions**: ツール実装（get_projects、get_categories、validate_percentage）
3. **AgentCore Gateway**: ツールとMCPサーバーの統合レイヤー
4. **AgentCore Runtime (A2A)**: Strands Agentのホスティング環境（A2Aプロトコル対応）
5. **AgentCore Memory**: 会話履歴の永続化と自動要約
6. **Cognito User Pool**: ユーザー認証

**ローカル環境：**
- **Streamlit UI (A2A版)**: A2Aプロトコルでエージェントと通信するWebインターフェース

## アーキテクチャ

### システム構成図

```
┌─────────────────────────────────────────────────────────────────┐
│  AWS Cloud (CDKでデプロイ)                                        │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Amazon S3                                                  │ │
│  │ - kintai-agent-data/projects.csv                           │ │
│  │ - kintai-agent-data/categories.csv                         │ │
│  └────────────────────────────────────────────────────────────┘ │
│                             ↓                                    │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ AWS Lambda Functions (ツール実装)                           │ │
│  │ ┌──────────────────┐ ┌──────────────────┐ ┌─────────────┐│ │
│  │ │ get_projects     │ │ get_categories   │ │ validate_   ││ │
│  │ │ (S3から読み込み) │ │ (S3から読み込み) │ │ percentage  ││ │
│  │ └──────────────────┘ └──────────────────┘ └─────────────┘│ │
│  └────────────────────────────────────────────────────────────┘ │
│                             ↓                                    │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Amazon Bedrock AgentCore Gateway                           │ │
│  │                                                            │ │
│  │ Targets:                                                   │ │
│  │ - Lambda Target: get_projects                              │ │
│  │ - Lambda Target: get_categories                            │ │
│  │ - Lambda Target: validate_percentage                       │ │
│  │ - MCP Server Target: Google Calendar (外部MCPサーバー)      │ │
│  │                                                            │ │
│  │ 機能:                                                       │ │
│  │ - ツールの統合と検索                                        │ │
│  │ - 認証管理（OAuth2）                                        │ │
│  │ - プロトコル変換（MCP ↔ Lambda/API）                       │ │
│  └────────────────────────────────────────────────────────────┘ │
│                             ↓                                    │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Amazon Bedrock AgentCore Runtime (A2A)                     │ │
│  │                                                            │ │
│  │  ┌──────────────────────────────────────────────────────┐ │ │
│  │  │ Kintai Agent (Strands Agent + Memory)                │ │ │
│  │  │                                                      │ │ │
│  │  │ - 自然言語処理                                        │ │ │
│  │  │ - 案件マッチング（LLM推論）                           │ │ │
│  │  │ - コマンド生成                                        │ │ │
│  │  │ - Gateway経由でツールを呼び出し                       │ │ │
│  │  │ - AgentCoreMemorySessionManager で会話履歴管理       │ │ │
│  │  └──────────────────────────────────────────────────────┘ │ │
│  │                                                            │ │
│  │ Protocol: A2A (Agent-to-Agent)                             │ │
│  │ - context_id で会話コンテキスト識別                        │ │
│  │ - KintaiA2AExecutor でリクエストごとにAgent作成           │ │
│  └────────────────────────────────────────────────────────────┘ │
│                             │                                    │
│                             ↓                                    │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Amazon Bedrock AgentCore Memory                            │ │
│  │ - BuiltInSummarization strategy                            │ │
│  │ - session_id ベースの会話履歴永続化                        │ │
│  │ - 自動要約で長期会話をサポート                             │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Amazon Cognito User Pool                                   │ │
│  │ - ユーザー認証                                             │ │
│  │ - アクセストークン発行                                      │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                             ↑
                             │ A2A Protocol (HTTPS)
                             │ X-Amzn-Bedrock-AgentCore-Runtime-Session-Id
                             │
         ┌──────────────────────────────────────┐
         │ ローカル環境                          │
         │                                      │
         │  ┌────────────────────────────────┐ │
         │  │ Streamlit UI (A2A版)           │ │
         │  │ - A2A Client でメッセージ送信   │ │
         │  │ - context_id で会話管理        │ │
         │  │ - Cognito認証                  │ │
         │  │ - 自然言語入力                  │ │
         │  └────────────────────────────────┘ │
         └──────────────────────────────────────┘
                             ↓
         ┌──────────────────────────────────────┐
         │ External Services                    │
         │ - Amazon Bedrock (Claude)            │
         │ - Google Calendar API (MCP経由)      │
         └──────────────────────────────────────┘
```

### CDKスタック構成（L2 Construct使用）

```python
from aws_cdk import Stack
from aws_cdk.aws_bedrock_agentcore_alpha import (
    Runtime,
    Gateway,
    AgentRuntimeArtifact,
    RuntimeNetworkConfiguration,
    GatewayProtocolConfiguration,
    LambdaToolSchema,
    GatewayCredentialProvider
)

class KintaiAgentStack(Stack):
    def __init__(self, scope, id, **kwargs):
        super().__init__(scope, id, **kwargs)
        
        # 1. S3バケット
        self.data_bucket = s3.Bucket(
            self, "DataBucket",
            bucket_name=f"kintai-agent-data-{self.account}"
        )
        
        # 2. Lambda関数（ツール実装）
        self.get_projects_fn = lambda_.Function(
            self, "GetProjects",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.handler",
            code=lambda_.Code.from_asset("cdk/lambda/get_projects")
        )
        self.data_bucket.grant_read(self.get_projects_fn)
        
        self.get_categories_fn = lambda_.Function(
            self, "GetCategories",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.handler",
            code=lambda_.Code.from_asset("cdk/lambda/get_categories")
        )
        self.data_bucket.grant_read(self.get_categories_fn)
        
        self.validate_percentage_fn = lambda_.Function(
            self, "ValidatePercentage",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.handler",
            code=lambda_.Code.from_asset("cdk/lambda/validate_percentage")
        )
        
        # 3. AgentCore Gateway（L2 Construct）
        self.gateway = Gateway(
            self, "KintaiGateway",
            gateway_name="kintai-gateway",
            description="Gateway for Kintai Agent tools",
            protocol_configuration=GatewayProtocolConfiguration.mcp(
                instructions="Use these tools to access project/category data and validate percentages"
            )
        )
        
        # 4. Gateway Targets（L2 Construct）
        # Lambda Targets
        self.gateway.add_lambda_target(
            "GetProjectsTarget",
            target_name="get_projects",
            description="Get projects from S3",
            lambda_function=self.get_projects_fn,
            tool_schema=LambdaToolSchema.from_inline({
                "get_projects": {
                    "description": "Get all available projects",
                    "parameters": {"type": "object", "properties": {}}
                }
            })
        )
        
        self.gateway.add_lambda_target(
            "GetCategoriesTarget",
            target_name="get_categories",
            description="Get categories from S3",
            lambda_function=self.get_categories_fn,
            tool_schema=LambdaToolSchema.from_inline({
                "get_categories": {
                    "description": "Get all available categories",
                    "parameters": {"type": "object", "properties": {}}
                }
            })
        )
        
        self.gateway.add_lambda_target(
            "ValidatePercentageTarget",
            target_name="validate_percentage",
            description="Validate percentage totals",
            lambda_function=self.validate_percentage_fn,
            tool_schema=LambdaToolSchema.from_inline({
                "validate_percentage": {
                    "description": "Validate that percentages sum to 100",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "entries": {
                                "type": "array",
                                "items": {"type": "object"}
                            }
                        },
                        "required": ["entries"]
                    }
                }
            })
        )
        
        # MCP Server Target（Google Calendar）
        # 注: OAuth認証情報は事前にAWSコンソールで作成
        self.gateway.add_mcp_server_target(
            "GoogleCalendarTarget",
            target_name="google_calendar",
            description="Google Calendar MCP server",
            url="https://calendar-mcp.example.com",
            path="/mcp",
            credential_provider_configurations=[
                GatewayCredentialProvider.from_oauth_identity_arn(
                    oauth_arn="arn:aws:bedrock-agentcore:...",
                    secret_arn="arn:aws:secretsmanager:..."
                )
            ]
        )
        
        # 5. AgentCore Runtime（L2 Construct）
        self.runtime = Runtime(
            self, "KintaiRuntime",
            runtime_name="kintai-agent",
            description="Kintai Agent Runtime",
            agent_runtime_artifact=AgentRuntimeArtifact.from_asset("./kintai_agent"),
            network_configuration=RuntimeNetworkConfiguration.using_public_network(),
            environment_variables={
                "GATEWAY_ENDPOINT": self.gateway.gateway_arn,
                "DATA_BUCKET": self.data_bucket.bucket_name
            }
        )
        
        # Gateway呼び出し権限を付与
        self.gateway.grant_read(self.runtime.execution_role)
```

### レイヤー構成

1. **インフラストラクチャ層（AWS CDK）**
   - S3: マスタデータストレージ
   - Lambda: ツール実装
   - IAM: 権限管理

2. **統合層（AgentCore Gateway）**
   - Lambda Targets: マスタデータアクセスツール
   - MCP Server Targets: 外部サービス連携（Google Calendar）
   - 認証管理（OAuth2）
   - プロトコル変換

3. **ホスティング層（AgentCore Runtime）**
   - マネージドエージェントホスティング
   - 自動スケーリング
   - セッション管理
   - セキュリティ分離

4. **アプリケーション層（Strands Agent）**
   - 自然言語処理
   - 案件マッチング（LLM推論）
   - コマンド生成
   - Gateway経由でツールを呼び出し

5. **プレゼンテーション層（ローカル）**
   - Streamlit UI: boto3でAgentCore Runtime APIを呼び出し

6. **外部サービス層**
   - Amazon Bedrock: Claude APIアクセス
   - Google Calendar API: MCP経由でアクセス

## コンポーネントとインターフェース

### 1. CDK Stack (Infrastructure)

**責務**: AWS リソースの定義とデプロイ

**構成**:
```python
class KintaiAgentStack(Stack):
    def __init__(self, scope, id, **kwargs):
        # S3バケット
        self.data_bucket = s3.Bucket(...)
        
        # Lambda関数
        self.get_projects_fn = lambda_.Function(...)
        self.get_categories_fn = lambda_.Function(...)
        self.validate_percentage_fn = lambda_.Function(...)
        
        # AgentCore Gateway
        self.gateway = agentcore.Gateway(...)
        
        # Gateway Targets
        self.add_lambda_targets()
        self.add_mcp_server_target()
        
        # AgentCore Runtime
        self.runtime = agentcore.Runtime(...)
```

### 2. Lambda Functions (Tools)

**get_projects**:
```python
def lambda_handler(event, context):
    """
    S3から案件マスタを取得
    
    Returns:
        List[Dict]: [{"id": 12345, "name": "プロジェクトA"}, ...]
    """
    # S3からprojects.csvを読み込み
    # パースしてJSON形式で返す
```

**get_categories**:
```python
def lambda_handler(event, context):
    """
    S3から区分マスタを取得
    
    Returns:
        List[Dict]: [{"id": 1, "name": "開発"}, ...]
    """
    # S3からcategories.csvを読み込み
    # パースしてJSON形式で返す
```

**validate_percentage**:
```python
def lambda_handler(event, context):
    """
    割合の合計を検証
    
    Args:
        entries: List[Dict] - 工数エントリ
        
    Returns:
        ValidationResult: 検証結果
    """
    # 合計が100%かチェック
    # 警告・提案を生成
```

### 3. AgentCore Gateway

**責務**: ツールとMCPサーバーの統合、認証管理、プロトコル変換

**Targets**:
- **Lambda Targets**: 
  - `get_projects`: 案件マスタ取得
  - `get_categories`: 区分マスタ取得
  - `validate_percentage`: 割合検証
  
- **MCP Server Target**:
  - `google-calendar`: Google Calendar API連携（既存MCPサーバー）

**機能**:
- ツールの自動検出とインデックス化
- セマンティック検索
- OAuth2認証管理（AgentCore Identity経由）
- MCP ↔ Lambda/API プロトコル変換

### 3.1. AgentCore Identity（OAuth2認証）

**責務**: OAuth2 Credential Providerの管理、Token Vaultでのトークン保存・リフレッシュ

**重要な制約**:
- CDK L2 Constructは現時点で**利用不可**
- Python SDKスクリプト（`cdk/scripts/setup-google-calendar-oauth.py`）で事前作成が必要
- CDKデプロイ前に一度実行

**OAuth2フロー（A2A対応）**:
1. **初回のみ**: ユーザーがブラウザでGoogleにログインして承認
2. **Token Vaultに保存**: アクセストークンとリフレッシュトークンを保存
3. **以降は自動**: エージェントが自動的にToken Vaultからトークンを取得
4. **自動リフレッシュ**: トークン期限切れ時に自動更新
5. **A2Aモード**: ユーザーIDを指定してトークン取得

**利点**:
- Google Workspaceの中央管理下でも利用可能
- Service Accountやドメイン全体の委任が不要
- 管理者権限不要（ユーザー自身が承認）
- 複数ユーザーのカレンダーに対応可能

**セットアップ手順**:
```bash
# 1. Google Cloud Consoleで OAuth 2.0クライアントIDを作成
# 2. AWS Secrets Managerに保存
aws secretsmanager create-secret \
    --name kintai-agent-google-calendar-oauth \
    --secret-string '{"clientId":"xxx","clientSecret":"yyy"}'

# 3. Python SDKスクリプトを実行
python3 cdk/scripts/setup-google-calendar-oauth.py \
    --region us-east-1 \
    --provider-name google-calendar \
    --secret-arn arn:aws:secretsmanager:...:secret:oauth-credentials

# 4. 出力されたProvider ARNをCDKコードに設定
# 5. CDKデプロイ
```

**CDKでの参照**:
```typescript
// 事前に作成したOAuth2 Credential Provider ARN
const googleCalendarOAuthArn = 'arn:aws:bedrock-agentcore:...';
const googleCalendarSecretArn = 'arn:aws:secretsmanager:...';

gateway.addMcpServerTarget('GoogleCalendarTarget', {
  gatewayTargetName: 'google-calendar',
  credentialProviderConfigurations: [
    agentcore.GatewayCredentialProvider.fromOauthIdentityArn(
      googleCalendarOAuthArn,
      googleCalendarSecretArn
    ),
  ],
});
```

### 4. Kintai Agent (Strands Agent)

**責務**: エージェントのメインロジック、LLMとの対話、Gateway経由でツールを呼び出し

**実装**:
```python
from strands_agents import Agent

class KintaiAgent:
    def __init__(self, gateway_endpoint: str):
        """
        エージェントを初期化
        
        Args:
            gateway_endpoint: AgentCore GatewayのMCPエンドポイント
        """
        self.agent = Agent(
            model="anthropic.claude-3-5-sonnet-20241022-v2:0",
            tools_endpoint=gateway_endpoint,  # Gateway経由でツールにアクセス
            system_prompt=self._build_system_prompt()
        )
    
    async def generate_from_text(self, text: str) -> CommandResult:
        """自然言語からコマンドを生成"""
        # LLMに自然言語を渡す
        # Gateway経由でget_projects、get_categoriesを呼び出し
        # 案件マッチング、区分推測
        # コマンド生成
        
    async def generate_from_calendar(self, date: str) -> CommandResult:
        """カレンダーからコマンドを生成"""
        # Gateway経由でgoogle-calendarツールを呼び出し
        # イベント分析
        # コマンド生成
```

**システムプロンプト**:
```
あなたは工数管理の専門家です。ユーザーの自然言語入力から、
OA Lacco APPのコマンド形式（add YYYY/MM/DD 案件ID 区分ID 割合）を生成します。

利用可能なツール：
- get_projects: 案件マスタを取得
- get_categories: 区分マスタを取得
- validate_percentage: 割合の合計を検証
- google-calendar: Google Calendarのイベントを取得

案件マッチングの優先順位：
1. 完全一致
2. 部分一致（1件のみ）
3. LLMで候補から選択（複数部分一致）
4. LLMで全検索（類似度）
```

### 5. Streamlit UI (A2A版)

**責務**: ローカルからA2AプロトコルでAgentCore Runtimeと通信するWebインターフェース

**実装**:
```python
import streamlit as st
import httpx
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.types import Message, Part, Role, TextPart

async def call_a2a_agent(access_token: str, user_message: str, context_id: str):
    """A2Aプロトコルでエージェントを呼び出し"""
    async with httpx.AsyncClient(
        headers={
            "Authorization": f"Bearer {access_token}",
            "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": context_id,
        },
        timeout=300.0
    ) as http_client:
        resolver = A2ACardResolver(httpx_client=http_client, base_url=base_url)
        agent_card = await resolver.get_agent_card()

        config = ClientConfig(httpx_client=http_client, streaming=False)
        factory = ClientFactory(config)
        client = factory.create(agent_card)

        msg = Message(
            kind="message",
            role=Role.user,
            parts=[Part(root=TextPart(kind="text", text=user_message))],
            messageId=uuid4().hex,
            contextId=context_id,  # 会話コンテキスト識別
        )

        async for event in client.send_message(msg):
            # レスポンス処理
            pass
```

### 6. AgentCore Memory

**責務**: 会話履歴の永続化と自動要約

**CDK定義**:
```typescript
const memory = new agentcore.Memory(this, 'KintaiMemory', {
  memoryName: 'kintai_memory',
  description: 'Memory for Kintai Agent conversation history',
  memoryStrategies: [
    agentcore.MemoryStrategy.usingBuiltInSummarization(),
  ],
});

// Runtimeに権限付与
memory.grantWrite(this.runtimeA2A);
memory.grantRead(this.runtimeA2A);
```

**Agent統合（Python）**:
```python
from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig
from bedrock_agentcore.memory.integrations.strands.session_manager import (
    AgentCoreMemorySessionManager,
)

def create_session_manager(session_id: str, actor_id: str):
    """AgentCoreMemorySessionManagerを作成"""
    config = AgentCoreMemoryConfig(
        memory_id=os.environ.get("AGENTCORE_MEMORY_ID"),
        session_id=session_id,  # 33文字以上必要
        actor_id=actor_id,
    )
    return AgentCoreMemorySessionManager(
        agentcore_memory_config=config,
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
    )

# Agent作成時にsession_managerを渡す
agent = Agent(
    model=model,
    system_prompt=system_prompt,
    tools=tools,
    session_manager=session_manager,  # 自動履歴管理
)
```

### 7. KintaiA2AExecutor（カスタム実行）

**責務**: A2Aリクエストごとにエージェントを作成し、Memory統合を行う

**実装**:
```python
class KintaiA2AExecutor(StrandsA2AExecutor):
    """カスタムA2A Executor"""

    async def _execute_streaming(self, context: RequestContext, updater):
        # 1. context_idからsession_managerを作成
        context_id = context.context_id or "default-context-id"
        session_manager = create_session_manager(context_id, actor_id)

        # 2. Gatewayトークンを取得
        token = await self.core.get_gateway_token()

        # 3. MCPClientでツールを取得
        with mcp_client:
            tools = list(mcp_client.list_tools_sync())

            # 4. リクエスト用Agentを作成
            request_agent = Agent(
                model=self.core.model,
                system_prompt=build_a2a_system_prompt(),
                tools=tools,
                session_manager=session_manager,
            )

            # 5. 実行
            await super()._execute_streaming(context, updater)
```

## データモデル

データモデルは既に`kintai_agent/models.py`で実装済みです。

### Project（案件）

```python
@dataclass
class Project:
    id: int
    name: str
```

**CSV形式**:
```csv
id,name
12345,顧客管理システム（CRM）
67890,基幹システム運用
11111,オンラインショップリニューアル
22222,マイグレーションPJ
33333,スマホアプリ「カイゼン」
44444,BIダッシュボード
55555,セキュリティ対策PJ
66666,AIエバンジェリスト
77777,書籍執筆
88888,AX-PF
99999,社内業務
```

**注意**: プロジェクト名には「開発」「保守」等の区分と混同しやすい単語を避ける

### Category（区分）

```python
@dataclass
class Category:
    id: int
    name: str
```

**CSV形式**:
```csv
id,name
1,開発
2,設計
3,保守
4,会議
5,テスト
6,ドキュメント作成
7,レビュー
8,調査・研究
9,その他
```

### WorkEntry（工数エントリ）

```python
@dataclass
class WorkEntry:
    date: str  # YYYY/MM/DD
    project_id: int
    project_name: str
    category_id: int
    category_name: str
    percentage: int
    confidence: str  # "high" | "medium" | "low"
    reason: Optional[str] = None
```

### ProjectMatch（案件マッチ結果）

```python
@dataclass
class ProjectMatch:
    project_id: int
    project_name: str
    confidence: str  # "high" | "medium" | "low"
    method: str  # "exact_match" | "partial_match" | "llm_select" | "llm_search"
```

### CommandResult（コマンド生成結果）

```python
@dataclass
class CommandResult:
    success: bool
    commands: List[str]
    explanation: str
    warnings: List[str]
    suggestions: List[str]
    entries: List[WorkEntry]
    calendar_analysis: Optional[CalendarAnalysis] = None
```

### CalendarAnalysis（カレンダー分析結果）

```python
@dataclass
class CalendarAnalysis:
    entries: List[WorkEntry]
    total_percentage: int
    unaccounted_hours: float
    unaccounted_percentage: int
```

### ValidationResult（検証結果）

```python
@dataclass
class ValidationResult:
    valid: bool
    total_percentage: int
    errors: List[str]
    warnings: List[str]
```

### CalendarEvent（カレンダーイベント）

```python
@dataclass
class CalendarEvent:
    title: str
    start: datetime
    end: datetime
    duration_hours: float
```

## Correctness Properties


*プロパティとは、システムのすべての有効な実行において真であるべき特性または動作です。本質的には、システムが何をすべきかについての形式的な記述です。プロパティは、人間が読める仕様と機械で検証可能な正確性保証の橋渡しとなります。*

### Property 1: 自然言語入力の完全解析

*任意の*有効な自然言語入力に対して、システムは日付、案件名、区分、割合の情報を抽出し、有効なコマンド形式で出力する

**検証: 要件 1.1, 1.5**

### Property 2: 案件名の段階的マッチング

*任意の*案件名入力に対して、システムは以下の順序でマッチングを試み、信頼度レベルと方法を返す：
1. 完全一致（confidence: high）
2. 部分一致（1件のみ: high、複数: medium）
3. LLM検索（confidence: low）

**検証: 要件 2.1, 2.2, 2.3, 2.4, 2.5**

### Property 3: 日付表現の正規化

*任意の*日付表現（相対日付を含む）に対して、システムはYYYY/MM/DD形式の絶対日付に変換する

**検証: 要件 1.4**

### Property 4: 区分の推測

*任意の*作業内容の記述に対して、システムは区分マスタから適切な区分IDを推測する

**検証: 要件 1.3**

### Property 5: 割合検証と提案

*任意の*工数エントリセットに対して、システムは以下を実行する：
- 合計が100%の場合: 検証成功
- 合計が100%未満の場合: 警告と不足分の提案
- 合計が100%超過の場合: エラーと超過量の表示

**検証: 要件 3.2, 3.3, 3.4, 3.5**

### Property 6: カレンダーイベントの完全抽出

*任意の*日付に対して、システムはGoogle Calendar APIからすべてのイベントを取得し、各イベントのタイトル、開始時刻、終了時刻を抽出する

**検証: 要件 4.1, 4.2**

### Property 7: カレンダーイベントからの案件推測

*任意の*カレンダーイベントタイトルに対して、システムはLLMを使用して案件名を推測する

**検証: 要件 4.3**

### Property 8: カレンダーイベントからの区分推測

*任意の*カレンダーイベントタイトルに対して、システムはLLMを使用して区分を推測する

**検証: 要件 4.4**

### Property 9: イベント時間からの割合計算

*任意の*カレンダーイベントに対して、システムはイベント時間を8時間で割った値に基づいて割合を計算する

**検証: 要件 4.5**

### Property 10: カレンダー分析の不足分提案

*任意の*カレンダー分析結果において、合計割合が100%未満の場合、システムは未計上時間を計算し、社内業務として割り当てることを提案する

**検証: 要件 4.6**

### Property 11: カレンダー分析の説明生成

*任意の*カレンダー分析結果に対して、システムは推測された各案件と区分の説明を提供する

**検証: 要件 4.7**

### Property 12: A2Aリクエストの解析

*任意の*A2Aリクエストに対して、システムはリクエストを受け入れ、アクションタイプを正しく解析する

**検証: 要件 5.1**

### Property 13: A2Aレスポンスの完全性

*任意の*A2Aレスポンスに対して、システムは成功ステータス、コマンド、説明、警告、提案を含むJSONレスポンスを返す

**検証: 要件 5.6**

### Property 14: 日付範囲の営業日生成

*任意の*日付範囲入力に対して、システムは範囲内の各営業日（月曜〜金曜）のコマンドを生成する

**検証: 要件 7.3**

### Property 15: 時間単位からの割合計算

*任意の*時間単位を含む表現に対して、システムは8時間の勤務日に基づいて割合を計算する

**検証: 要件 7.4**

### Property 16: 曖昧入力の処理

*任意の*曖昧な入力に対して、システムは明確化を要求するか、説明付きで合理的な推測を行う

**検証: 要件 7.5**

### Property 17: 無効入力のエラー処理

*任意の*無効な入力に対して、システムは問題を説明するエラーメッセージを返す

**検証: 要件 8.1**

### Property 18: 低信頼度マッチの警告

*任意の*低信頼度（low）の案件マッチに対して、システムはレスポンスに警告を含める

**検証: 要件 8.2**

### Property 19: マッチ失敗時の提案

*任意の*案件マッチ失敗時に、システムは有効な案件名の提案とともにエラーを返す

**検証: 要件 8.3**

### Property 20: 割合不一致の警告

*任意の*割合検証の問題に対して、システムは不一致に関する具体的な警告を提供する

**検証: 要件 8.4**

### Property 21: 成功時のステータス

*任意の*有効な入力の正常処理時に、システムはエラーなしで成功ステータスを返す

**検証: 要件 8.5**

### Property 22: マスタデータの使用

*任意の*案件マッチングまたは区分推測操作において、システムはロードされた案件マスタまたは区分マスタデータを検索・参照する

**検証: 要件 9.3, 9.4**

### Property 23: 複数コマンドの個別生成

*任意の*複数案件を含む入力に対して、システムは各案件-区分の組み合わせに対して個別のコマンドを生成する

**検証: 要件 10.1**

### Property 24: コマンド形式の一貫性

*任意の*生成されたコマンドに対して、システムは正しいOA Lacco APPコマンド形式（`add <日付> <案件ID> <区分ID> <割合>`）に従うことを保証する

**検証: 要件 10.2**

### Property 25: 複数コマンドの順序付け

*任意の*複数コマンド出力に対して、システムはそれらを明確で順序付けられたリストで提示する

**検証: 要件 10.4**

### Property 26: 統合説明の提供

*任意の*複数コマンド生成時に、システムはすべてのエントリをカバーする統合された説明を提供する

**検証: 要件 10.5**

## エラーハンドリング

### エラーの種類

1. **入力エラー**
   - 無効な日付形式
   - 認識できない案件名
   - 不正な割合（負の値、100%超過）

2. **データエラー**
   - マスタデータファイルの欠落
   - CSVファイルの形式エラー
   - 必須カラムの欠落

3. **外部APIエラー**
   - Claude API接続エラー
   - Google Calendar API認証エラー
   - APIレート制限

4. **検証エラー**
   - 割合の合計が100%でない
   - 案件IDが見つからない
   - 区分IDが見つからない

### エラーレスポンス形式

```python
@dataclass
class ErrorResponse:
    success: bool = False
    error_type: str  # "input_error" | "data_error" | "api_error" | "validation_error"
    error_message: str
    suggestions: List[str]
    details: Optional[Dict[str, Any]] = None
```

### エラーハンドリング戦略

1. **入力エラー**: ユーザーに明確なフィードバックと修正方法を提供
2. **データエラー**: システム管理者に通知、デフォルト値で継続（可能な場合）
3. **外部APIエラー**: リトライロジック（最大3回）、フォールバック処理
4. **検証エラー**: 警告として表示、ユーザーに修正を促す

## 実装の考慮事項

### パフォーマンス

1. **マスタデータのキャッシング**: 起動時に一度だけロード、メモリに保持
2. **LLM呼び出しの最適化**: 必要最小限の呼び出し、バッチ処理の検討
3. **非同期処理**: Google Calendar API呼び出しは非同期で実行

### セキュリティ

1. **API認証情報の管理**: 環境変数または安全なストレージに保存
2. **入力検証**: SQLインジェクション、XSS対策（該当する場合）
3. **ログ**: 個人情報を含まないログ出力

### スケーラビリティ

1. **ステートレス設計**: エージェントはステートレスに保つ
2. **水平スケーリング**: 複数インスタンスの並行実行が可能
3. **レート制限**: 外部API呼び出しのレート制限を考慮

### 保守性

1. **モジュール化**: 各コンポーネントを独立したモジュールとして実装
2. **設定の外部化**: マスタデータパス、APIキーなどは設定ファイルで管理
3. **ログとモニタリング**: 適切なログレベルとエラートラッキング

### 拡張性

1. **プラグイン可能なマッチングアルゴリズム**: 新しいマッチング方法を追加可能
2. **カスタムツール**: 新しいツールを簡単に追加できる設計
3. **多言語対応**: 将来的に英語などの他言語をサポート可能
