# Kintai Agent - 工数管理エージェント

OA Lacco APPへの工数入力を自然言語化するAIエージェントです。AWS CDK（L2 Construct）でインフラをデプロイし、Amazon Bedrock AgentCore Runtimeで運用します。

## アーキテクチャ

```
[ユーザー] ─[Cognito]→ [Runtime A2A] ─[M2M Token]→ [Gateway] ─[IAM]→ [Lambda]
                              │                        │
                              │                        └─ AgentCore Identity
                              │                           (Credential Provider)
                              └─ AgentCore Memory
                                 (会話履歴)
```

**AWS環境（CDK L2 Constructでデプロイ）：**
- **S3 Bucket**: マスタデータ（CSV）の保存
- **Lambda Functions**: ツール実装（get_projects、get_categories、validate_percentage）
- **AgentCore Gateway**: ツールとMCPサーバーの統合レイヤー
- **AgentCore Runtime**: Strands Agent（A2Aプロトコル対応）
- **AgentCore Memory**: 会話履歴の永続化・自動要約
- **Cognito User Pool**: ユーザー認証 + M2Mクライアント
- **DynamoDB**: M2Mトークンキャッシュ

**ローカル環境：**
- **Streamlit UI (A2A版)**: A2Aプロトコルでエージェントを呼び出すWebインターフェース

## 認証フロー

| 区間 | 認証方式 | 説明 |
|------|---------|------|
| ユーザー → Runtime | Cognito | ユーザーがログインしてトークン取得 |
| Runtime → Gateway | AgentCore Identity | M2Mトークンを自動取得 |
| Gateway → Lambda | IAM | 自動付与（CDK設定） |

詳細は `.kiro/steering/a2a-platform-guide.md` を参照してください。

## 機能

- 自然言語から工数コマンドを生成
- Google Calendarイベントから工数を推測（AgentCore Gateway経由）
- 案件名の曖昧性解決（LLM推論）
- 割合の自動検証
- A2Aプロトコル対応
- 会話履歴の自動管理（AgentCore Memory）

## セットアップ

### 1. 依存関係のインストール

```bash
# CDK
cd cdk
npm install

# エージェント
cd ../kintai_agent
pip install -r requirements.txt

# フロントエンド
cd ../frontend_a2a
pip install -r requirements.txt
```

### 2. AWS認証情報の設定

```bash
# SSO の場合
aws configure sso --profile <profile-name>
aws sso login --profile <profile-name>

# アクセスキーの場合
aws configure --profile <profile-name>
```

## デプロイ

### 1. CDKでインフラをデプロイ

```bash
cd cdk

# 初回のみ：CDK Bootstrap
AWS_REGION=ap-northeast-1 CDK_DEFAULT_REGION=ap-northeast-1 npx cdk bootstrap --profile <profile-name>

# デプロイ実行
AWS_REGION=ap-northeast-1 CDK_DEFAULT_REGION=ap-northeast-1 npx cdk deploy --profile <profile-name>
```

**重要**: `CDK_DEFAULT_REGION` を明示的に指定しないと、デフォルトリージョンにデプロイされる場合があります。

### 2. M2M Credential Provider のセットアップ

CDKデプロイだけでは不完全です。AgentCore Identity の Credential Provider を作成します。

```bash
cd cdk/scripts
./setup-m2m-credential-provider.sh --profile <profile-name>
```

**このスクリプトが行うこと:**
1. CloudFormation出力からCognito設定を取得
2. M2Mクライアントシークレットを取得
3. AgentCore Identity Credential Providerを作成

### 3. フロントエンド設定の更新

`frontend_a2a/config.py` をCDK出力の値で更新：

```python
REGION = "ap-northeast-1"
USER_POOL_ID = "<CDK出力: UserPoolId>"
CLIENT_ID = "<CDK出力: UserPoolClientId>"
RUNTIME_ARN = "<Runtime ARN>"
```

Runtime ARN の確認：
```bash
aws bedrock-agentcore-control list-agent-runtimes \
  --region ap-northeast-1 \
  --profile <profile-name> \
  --query 'agentRuntimes[?agentRuntimeName==`kintai_agent_a2a`].agentRuntimeArn' \
  --output text
```

### 4. Cognitoユーザーの作成

```bash
# ユーザー作成
aws cognito-idp admin-create-user \
  --user-pool-id <USER_POOL_ID> \
  --username testuser \
  --user-attributes Name=email,Value=test@example.com \
  --temporary-password "TempPass123!" \
  --profile <profile-name> \
  --region ap-northeast-1

# パスワードを確定（初回変更をスキップ）
aws cognito-idp admin-set-user-password \
  --user-pool-id <USER_POOL_ID> \
  --username testuser \
  --password "TestPass123!" \
  --permanent \
  --profile <profile-name> \
  --region ap-northeast-1
```

## 使い方

### Streamlit UI（A2A版）

```bash
cd frontend_a2a
streamlit run app.py
```

ブラウザで http://localhost:8501 にアクセスし、Cognitoユーザーでログイン。

### 入力例

- 「プロジェクト一覧を教えてください」
- 「区分一覧を見せてください」
- 「明日はプロジェクトAで開発作業を100%」
- 「今日はプロジェクトAで50%、メンテナンス業務で50%」

## プロジェクト構造

```
.
├── .kiro/
│   ├── specs/kintai-agent/          # 仕様書
│   └── steering/                    # プロジェクトガイド
│       ├── project-overview.md      # プロジェクト概要
│       ├── agentcore-cdk-guide.md   # AgentCore CDK L2 Constructガイド
│       └── a2a-platform-guide.md    # 共通A2Aクライアント実装ガイド
├── cdk/                             # CDKインフラコード
│   ├── lib/
│   │   └── kintai-agent-stack.ts    # メインスタック
│   ├── lambda/                      # Lambda関数
│   │   ├── get_projects/
│   │   ├── get_categories/
│   │   └── validate_percentage/
│   └── scripts/
│       └── setup-m2m-credential-provider.sh  # M2M認証セットアップ
├── kintai_agent/                    # エージェントコード
│   ├── agent_a2a.py                 # A2Aサーバー実装
│   ├── core.py                      # コアロジック（トークン管理含む）
│   └── requirements.txt
├── frontend_a2a/                    # A2A版フロントエンド
│   ├── app.py                       # Streamlit UI
│   ├── config.py                    # 設定（Cognito情報等）
│   └── requirements.txt
├── data/                            # マスタデータ
│   ├── projects.csv
│   └── categories.csv
└── README.md
```

## 開発コマンド

### CDK

```bash
cd cdk

# 差分確認
AWS_REGION=ap-northeast-1 CDK_DEFAULT_REGION=ap-northeast-1 npx cdk diff --profile <profile-name>

# デプロイ
AWS_REGION=ap-northeast-1 CDK_DEFAULT_REGION=ap-northeast-1 npx cdk deploy --profile <profile-name>
```

### ログ確認

```bash
# Runtime ログ
aws logs tail /aws/bedrock-agentcore/runtimes/<runtime-id>-DEFAULT --follow --profile <profile-name> --region ap-northeast-1

# Lambda ログ
aws logs tail /aws/lambda/kintai-agent-get-projects --follow --profile <profile-name> --region ap-northeast-1
```

## Google Calendar連携（オプション）

Google Calendar連携を使用する場合、OAuth2 Credential Providerを作成する必要があります。

1. Google Cloud ConsoleでOAuth 2.0クライアントIDを作成
2. リダイレクトURI設定: `https://bedrock-agentcore.{region}.amazonaws.com/oauth/callback`
3. `cdk/scripts/setup-google-calendar-oauth.py` を実行
4. CDKスタックのGoogle Calendar MCP Server Targetセクションのコメントを解除

詳細は `.kiro/steering/agentcore-cdk-guide.md` を参照。

## ドキュメント

| ファイル | 内容 |
|---------|------|
| `.kiro/steering/project-overview.md` | プロジェクト概要・デプロイ手順 |
| `.kiro/steering/agentcore-cdk-guide.md` | AgentCore CDK L2 Constructガイド |
| `.kiro/steering/a2a-platform-guide.md` | 共通A2Aクライアント実装ガイド |
| `.kiro/specs/kintai-agent/tasks.md` | 実装タスク一覧 |

## ライセンス

Internal use only
