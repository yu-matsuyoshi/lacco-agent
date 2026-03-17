---
title: AWS Bedrock AgentCore CDK L2 Construct Guide
inclusion: fileMatch
fileMatchPattern: 'cdk/**/*.ts'
---

# AWS Bedrock AgentCore CDK L2 Construct ガイド

このプロジェクトでは、AWS CDKのL2 Constructを使用してAmazon Bedrock AgentCoreリソースをデプロイします。

## パッケージ

**Python:**
```python
from aws_cdk.aws_bedrock_agentcore_alpha import (
    Runtime,
    Gateway,
    GatewayTarget,
    Browser,
    CodeInterpreter,
    Memory,
    AgentRuntimeArtifact,
    RuntimeNetworkConfiguration,
    GatewayProtocolConfiguration,
    GatewayAuthorizer,
    LambdaToolSchema,
    ApiSchema
)
```

**注意:** `aws-bedrock-agentcore-alpha`はアルファモジュールのため、破壊的変更が発生する可能性があります。

## 主要なL2 Construct

### 1. Runtime

エージェントをホスティングするためのConstruct。

**主要プロパティ:**
- `runtime_name`: ランタイム名
- `agent_runtime_artifact`: エージェントのアーティファクト（ECR、ローカルアセット、直接コード）
- `execution_role`: IAMロール
- `network_configuration`: ネットワーク設定（Public/VPC）
- `protocol_configuration`: プロトコル設定（HTTP/WebSocket）
- `authorizer_configuration`: 認証設定（IAM/Cognito/JWT/OAuth）
- `environment_variables`: 環境変数

**例:**
```python
runtime = Runtime(
    self, "MyRuntime",
    runtime_name="my-agent",
    agent_runtime_artifact=AgentRuntimeArtifact.from_asset("./agent"),
    network_configuration=RuntimeNetworkConfiguration.using_public_network()
)
```

### 2. Gateway

ツールとMCPサーバーを統合するためのConstruct。

**主要プロパティ:**
- `gateway_name`: Gateway名
- `description`: 説明
- `protocol_configuration`: プロトコル設定（MCP）
- `authorizer_configuration`: 認証設定（Cognito/JWT/IAM/OAuth）
- `kms_key`: 暗号化キー
- `role`: IAMロール

**例:**
```python
gateway = Gateway(
    self, "MyGateway",
    gateway_name="my-gateway",
    protocol_configuration=GatewayProtocolConfiguration.mcp(
        instructions="Use this gateway to connect to tools"
    )
)
```

### 3. GatewayTarget

Gatewayに登録するツールを定義するConstruct。

**ターゲットタイプ:**

#### Lambda Target
```python
gateway.add_lambda_target(
    "GetProjectsTarget",
    target_name="get_projects",
    description="Get projects from S3",
    lambda_function=get_projects_fn,
    tool_schema=LambdaToolSchema.from_inline({
        "get_projects": {
            "description": "Get all projects",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    })
)
```

#### OpenAPI Target
```python
gateway.add_open_api_target(
    "ApiTarget",
    target_name="my-api",
    description="External API",
    api_schema=ApiSchema.from_asset("./schema.yaml"),
    credential_provider_configurations=[
        GatewayCredentialProvider.from_api_key_identity_arn(
            api_key_arn,
            secret_arn,
            header_name="X-API-Key"
        )
    ]
)
```

#### Smithy Target
```python
gateway.add_smithy_target(
    "SmithyTarget",
    target_name="my-smithy",
    description="Smithy model",
    smithy_model=ApiSchema.from_asset("./model.json")
)
```

#### MCP Server Target
```python
gateway.add_mcp_server_target(
    "McpTarget",
    target_name="google-calendar",
    description="Google Calendar MCP server",
    url="https://calendar-mcp.example.com",
    path="/mcp",
    credential_provider_configurations=[
        GatewayCredentialProvider.from_oauth_identity_arn(
            oauth_arn,
            secret_arn
        )
    ]
)
```

## ベストプラクティス

### 1. ツール命名規則

Gatewayは各ツール名にターゲット名をプレフィックスとして付加します：
- ターゲット名: `my-lambda-target`
- ツール名: `calculate_price`
- 実際の呼び出し名: `my-lambda-target___calculate_price`

Lambda関数内でこのプレフィックスを除去する必要があります。

### 2. 認証設定

**デフォルト（Cognito M2M）:**
```python
gateway = Gateway(self, "MyGateway", gateway_name="my-gateway")
# Cognitoが自動作成される
```

**カスタムJWT:**
```python
gateway = Gateway(
    self, "MyGateway",
    gateway_name="my-gateway",
    authorizer_configuration=GatewayAuthorizer.using_custom_jwt(
        discovery_url="https://auth.example.com/.well-known/openid-configuration",
        allowed_clients=["client-id"],
        allowed_audiences=["audience"]
    )
)
```

### 3. ネットワーク設定

**Public:**
```python
network_configuration=RuntimeNetworkConfiguration.using_public_network()
```

**VPC:**
```python
network_configuration=RuntimeNetworkConfiguration.using_vpc(
    vpc=vpc,
    subnets=vpc.select_subnets(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS)
)
```

### 4. IAM権限

**Runtimeへの権限付与:**
```python
# Bedrockモデル呼び出し権限
runtime.grant_invoke_model(model)

# S3アクセス権限
bucket.grant_read(runtime.execution_role)
```

**Gatewayへの権限付与:**
```python
# Lambda呼び出し権限（自動付与）
gateway.add_lambda_target(...)  # 自動的にlambda:InvokeFunctionが付与される

# カスタム権限
gateway.grant_read(role)
gateway.grant_manage(role)
```

## AgentCore Identity（OAuth2 Credential Provider）

### 重要な制約

**CDK L2 Constructは現時点で利用不可**

AgentCore IdentityのOAuth2 Credential Providerは、CDK L2 Constructがまだ提供されていません。
CDKドキュメントには「Identity L2 construct when available」と記載されており、将来的に提供予定です。

**利用可能なL1 Construct:**
- `CfnWorkloadIdentity` - Workload Identity用
- `CfnGateway` - Gateway用
- `CfnGatewayTarget` - Gateway Target用

**OAuth2 Credential Providerは含まれていません。**

### M2M認証用 Credential Provider のセットアップ

Runtime→Gateway間のM2M認証には、Cognito M2Mクライアントと連携したCredential Providerが必要です。

**セットアップ手順:**

1. CDKデプロイ（Cognito User Pool、M2Mクライアント、Gatewayが作成される）
2. `cdk/scripts/setup-m2m-credential-provider.sh` を実行

```bash
# CDKデプロイ後に実行
cd cdk/scripts
./setup-m2m-credential-provider.sh --profile <AWS_PROFILE>
```

**スクリプトが行うこと:**
1. CloudFormation出力からCognito設定を取得
2. M2Mクライアントシークレットを取得
3. AgentCore Identity Credential Providerを作成

**CLIで手動作成する場合:**
```bash
aws bedrock-agentcore-control create-oauth2-credential-provider \
  --name kintai-gateway-m2m \
  --credential-provider-vendor CustomOauth2 \
  --oauth2-provider-config-input '{
    "customOauth2ProviderConfig": {
      "oauthDiscovery": {
        "authorizationServerMetadata": {
          "issuer": "https://cognito-idp.<REGION>.amazonaws.com/<USER_POOL_ID>",
          "authorizationEndpoint": "<COGNITO_DOMAIN>/oauth2/authorize",
          "tokenEndpoint": "<COGNITO_DOMAIN>/oauth2/token",
          "tokenEndpointAuthMethods": ["client_secret_post"]
        }
      },
      "clientId": "<M2M_CLIENT_ID>",
      "clientSecret": "<M2M_CLIENT_SECRET>"
    }
  }' \
  --region us-east-1
```

### Google Calendar用 OAuth2 Credential Providerの作成方法

現時点では以下の3つの方法があります：

#### 方法1: AWSコンソールで手動作成（最もシンプル）
- AgentCore Identity コンソール → Credential Providers → Create
- 開発・テスト環境向け
- 一度だけ作成すれば良い

#### 方法2: Python SDKで作成（推奨）
- `boto3.client('bedrock-agentcore-control')`を使用
- CDKデプロイ後に実行するスクリプトとして実装
- バージョン管理可能で再現性が高い
- CI/CDパイプラインに組み込み可能

```python
# cdk/scripts/setup-google-calendar-oauth.py
client = boto3.client('bedrock-agentcore-control', region_name=region)
response = client.create_oauth2_credential_provider(
    name='google-calendar',
    oauth2ProviderConfig={
        'googleOauth2ProviderConfig': {
            'clientId': 'xxx'
        }
    },
    clientSecret='yyy',
    scopes=['https://www.googleapis.com/auth/calendar.readonly']
)
```

#### 方法3: CloudFormation Custom Resource（完全自動化）
- Lambda関数でPython SDKを呼び出し
- CDKから Custom Resourceとして実装
- 最も複雑だが、完全にInfrastructure as Codeとして管理可能

### OAuth2でA2Aサーバーとして利用可能

**重要：OAuth2（ユーザー委譲型）でもA2Aサーバーとして動作可能**

AgentCore IdentityのToken Vault機能により、以下のフローが実現できます：

1. **初回のみ**: ユーザーがブラウザでGoogleにログインして承認
2. **Token Vaultに保存**: アクセストークンとリフレッシュトークンを保存
3. **以降は自動**: エージェントが自動的にToken Vaultからトークンを取得
4. **自動リフレッシュ**: トークン期限切れ時に自動更新
5. **A2Aモード**: ユーザーIDを指定してトークン取得

**利点:**
- Google Workspaceの中央管理下でも利用可能
- Service Accountやドメイン全体の委任が不要
- 管理者権限不要（ユーザー自身が承認）
- 複数ユーザーのカレンダーに対応可能（ユーザーIDごとにトークン管理）

### CDKでの使用方法

OAuth2 Credential Providerを事前に作成した後、CDKで参照します：

```typescript
// 事前に作成したOAuth2 Credential Provider ARN
const googleCalendarOAuthArn = 'arn:aws:bedrock-agentcore:us-east-1:123456789012:token-vault/abc123/oauth2credentialprovider/google-calendar';
const googleCalendarSecretArn = 'arn:aws:secretsmanager:us-east-1:123456789012:secret:kintai-agent-google-calendar-oauth-abc123';

// MCP Server Targetを追加
gateway.addMcpServerTarget('GoogleCalendarTarget', {
  gatewayTargetName: 'google-calendar',
  description: 'Google Calendar MCP server for event retrieval',
  url: 'https://your-mcp-server-url.com',
  path: '/mcp',
  credentialProviderConfigurations: [
    agentcore.GatewayCredentialProvider.fromOauthIdentityArn(
      googleCalendarOAuthArn,
      googleCalendarSecretArn
    ),
  ],
});
```

### セットアップ手順

1. **Google Cloud Consoleで設定**
   - OAuth 2.0クライアントIDを作成（Webアプリケーション）
   - リダイレクトURIを設定: `https://bedrock-agentcore.{region}.amazonaws.com/oauth/callback`

2. **AWS Secrets Managerに保存**
   ```json
   {
     "clientId": "xxx.apps.googleusercontent.com",
     "clientSecret": "yyy"
   }
   ```

3. **Python SDKスクリプトを実行**
   ```bash
   python3 cdk/scripts/setup-google-calendar-oauth.py \
       --region us-east-1 \
       --provider-name google-calendar \
       --secret-arn arn:aws:secretsmanager:...:secret:oauth-credentials
   ```

4. **CDKスタックを更新**
   - 出力されたProvider ARNをCDKコードに設定
   - コメントを解除してデプロイ

5. **初回ユーザー承認**
   - ユーザーがエージェントにアクセス
   - Google OAuth同意画面で承認
   - Token Vaultにトークン保存

6. **以降は自動動作**
   - エージェントが自動的にトークン取得
   - A2Aサーバーとして動作

## AgentCore Runtime スケーリングの制約

### 重要な制約

AgentCore Runtimeは完全サーバーレス設計で、以下の制約があります：

- **最小インスタンス数の設定不可**: ゼロからスケール
- **15分のアイドルタイムアウト**: 非アクティブなコンテナは自動終了
- **コンテナの頻繁な入れ替わり**: インメモリキャッシュは効果が限定的

### M2Mトークンキャッシュのベストプラクティス

コンテナ間で共有するキャッシュにはDynamoDBを使用します：

```typescript
// DynamoDB テーブル - M2Mトークンキャッシュ用
const tokenCacheTable = new dynamodb.Table(this, 'TokenCacheTable', {
  tableName: `my-agent-token-cache-${this.account}`,
  partitionKey: {
    name: 'cache_key',
    type: dynamodb.AttributeType.STRING,
  },
  billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
  timeToLiveAttribute: 'ttl',  // 自動削除用TTL
});

// Runtimeに権限付与
tokenCacheTable.grantReadWriteData(runtime);

// 環境変数でテーブル名を渡す
runtime.addEnvironmentVariable('TOKEN_CACHE_TABLE', tokenCacheTable.tableName);
```

**Pythonエージェントでの使用例:**
```python
import boto3

class MyAgent:
    def __init__(self):
        self.token_cache_table = os.getenv("TOKEN_CACHE_TABLE")
        self._dynamodb = boto3.resource('dynamodb')

    def get_cached_token(self):
        table = self._dynamodb.Table(self.token_cache_table)
        response = table.get_item(Key={'cache_key': 'my_token'})
        if 'Item' in response:
            return response['Item']['token']
        return None

    def save_token(self, token, expires_at):
        table = self._dynamodb.Table(self.token_cache_table)
        table.put_item(Item={
            'cache_key': 'my_token',
            'token': token,
            'expires_at': int(expires_at),
            'ttl': int(expires_at) + 3600,  # 1時間後に自動削除
        })
```

## 参考リンク

- [公式ドキュメント](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-bedrock-agentcore-alpha-readme.html)
- [CDKサンプル](https://github.com/awslabs/amazon-bedrock-agentcore-samples/tree/main/04-infrastructure-as-code/cdk)
- [AgentCore Identity Documentation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/identity.html)
