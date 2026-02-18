# Kintai Agent - 工数管理エージェント

OA Lacco APPへの工数入力を自然言語化するAIエージェントです。AWS CDK（L2 Construct）でインフラをデプロイし、Amazon Bedrock AgentCore Runtimeで運用します。

## アーキテクチャ

**AWS環境（CDK L2 Constructでデプロイ）：**
- **S3 Bucket**: マスタデータ（CSV）の保存
- **Lambda Functions**: ツール実装（get_projects、get_categories、validate_percentage）
- **AgentCore Gateway**: ツールとMCPサーバーの統合レイヤー（L2 Construct）
- **AgentCore Runtime**: Strands Agentのホスティング環境（L2 Construct）

**ローカル環境：**
- **Streamlit UI**: boto3でAgentCore Runtime APIを呼び出すWebインターフェース

## 機能

- 自然言語から工数コマンドを生成
- Google Calendarイベントから工数を推測（AgentCore Gateway経由）
- 案件名の曖昧性解決（LLM推論）
- 割合の自動検証
- A2Aプロトコル対応（AgentCore Runtime経由）

## セットアップ

### 1. 依存関係のインストール

```bash
pip install -r requirements.txt
```

### 2. AWS認証情報の設定

```bash
aws configure
```

### 3. 環境変数の設定

`.env.example`を`.env`にコピーして、必要な値を設定してください：

```bash
cp .env.example .env
```

必須の環境変数：
- `AWS_REGION`: AWSリージョン（例: us-east-1）
- `AWS_ACCOUNT_ID`: AWSアカウントID

### 4. Google Calendar OAuth2設定（オプション）

Google Calendar連携を使用する場合、事前にOAuth2 Credential Providerを作成する必要があります。

#### 4.1. Google Cloud Consoleで設定

1. Google Cloud Consoleでプロジェクトを作成
2. Google Calendar APIを有効化
3. OAuth 2.0クライアントIDを作成（Webアプリケーション）
4. リダイレクトURIを設定: `https://bedrock-agentcore.{region}.amazonaws.com/oauth/callback`
5. クライアントIDとシークレットを取得

#### 4.2. AWS Secrets Managerに保存

```bash
aws secretsmanager create-secret \
    --name kintai-agent-google-calendar-oauth \
    --secret-string '{"clientId":"xxx.apps.googleusercontent.com","clientSecret":"yyy"}' \
    --region us-east-1
```

#### 4.3. OAuth2 Credential Providerを作成

```bash
python3 cdk/scripts/setup-google-calendar-oauth.py \
    --region us-east-1 \
    --provider-name google-calendar \
    --secret-arn arn:aws:secretsmanager:us-east-1:123456789012:secret:kintai-agent-google-calendar-oauth-abc123
```

出力されたProvider ARNをメモしてください。

#### 4.4. CDKスタックを更新

`cdk/lib/kintai-agent-stack.ts`のGoogle Calendar MCP Server Targetセクションのコメントを解除し、
Provider ARNを設定してください。

**注意：**
- OAuth2でもA2Aサーバーとして動作可能
- 初回のみユーザーがブラウザで承認
- 以降はToken Vaultで自動管理
- Service Accountやドメイン全体の委任は不要

## デプロイ

### 1. CDK（L2 Construct）でインフラをデプロイ

```bash
cd cdk

# 初回のみ：CDK Bootstrapを実行
cdk bootstrap

# TypeScriptをビルド
npm run build

# デプロイ内容を確認
cdk diff

# デプロイ実行
cdk deploy
```

デプロイされるリソース：
- S3バケット（マスタデータ）
- Lambda関数（get_projects、get_categories、validate_percentage）
- AgentCore Gateway（Lambda Targets + MCP Server Target）
- AgentCore Runtime（Strands Agent）

### 2. マスタデータのアップロード

CDKデプロイ時に自動的にS3にアップロードされます。
手動でアップロードする場合：

```bash
aws s3 cp data/projects.csv s3://kintai-agent-data-ACCOUNT_ID/master-data/projects.csv
aws s3 cp data/categories.csv s3://kintai-agent-data-ACCOUNT_ID/master-data/categories.csv
```

### 3. デプロイ後の確認

デプロイが完了すると、以下の情報が出力されます：

```
Outputs:
KintaiAgentStack.DataBucketName = kintai-agent-data-123456789012
KintaiAgentStack.GatewayArn = arn:aws:bedrock-agentcore:us-east-1:123456789012:gateway/xxx
KintaiAgentStack.GatewayId = xxx
```

Runtime ARNは、AWSコンソールまたはCLIで確認してください：

```bash
aws bedrock-agentcore list-runtimes --region us-east-1
```

### 4. ローカルテスト（オプション）

AgentCore Runtimeにデプロイする前に、ローカルでテストできます：

```bash
# エージェントをローカルで起動
python -m kintai_agent

# 別のターミナルでテストリクエストを送信
curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{"action": "generate_from_text", "text": "明日はプロジェクトAで開発作業を8時間"}'
```

## 使い方

### Streamlit UI（ローカル）

```bash
# エージェントARNを環境変数に設定
export AGENT_ARN="arn:aws:bedrock-agentcore:us-east-1:123456789012:agent/xxx"

# Streamlit UIを起動
streamlit run app.py
```

Streamlit UIは、boto3を使用してAgentCore Runtime上のエージェントを呼び出します。

### boto3で直接呼び出し

```python
import boto3

client = boto3.client('bedrock-agentcore-runtime')

response = client.invoke_agent(
    agentArn='arn:aws:bedrock-agentcore:us-east-1:123456789012:agent/xxx',
    inputText='今日はプロジェクトA 50%、会議 50%'
)

print(response)
```

## プロジェクト構造

```
.
├── .kiro/
│   ├── specs/kintai-agent/      # 仕様書
│   └── steering/                # プロジェクト共通知識
│       └── agentcore-cdk-guide.md  # AgentCore CDK L2 Constructガイド
├── cdk/                         # CDKインフラコード（L2 Construct）
│   ├── bin/                    # CDKアプリエントリーポイント
│   ├── lib/                    # スタック定義
│   │   └── kintai-agent-stack.ts  # メインスタック（L2 Construct使用）
│   ├── lambda/                 # Lambda関数コード
│   │   ├── get_projects/
│   │   ├── get_categories/
│   │   └── validate_percentage/
│   └── scripts/                # セットアップスクリプト
│       └── setup-google-calendar-oauth.py  # OAuth2 Credential Provider作成
├── data/                        # マスタデータ（ローカル開発用）
│   ├── projects.csv            # 案件マスタ
│   └── categories.csv          # 区分マスタ
├── kintai_agent/               # エージェントコード
│   ├── __init__.py
│   ├── agent.py                # Strands Agent実装
│   ├── models.py               # データモデル
│   └── data_loader.py          # CSVローダー
├── app.py                      # Streamlit UI
├── requirements.txt            # 依存関係
├── .env.example               # 環境変数テンプレート
└── README.md                  # このファイル
```

## 開発

### ローカルテスト

エージェントコードをローカルでテストする場合：

```python
from kintai_agent import KintaiAgent

# ローカルのCSVファイルを使用
agent = KintaiAgent(
    projects_path="data/projects.csv",
    categories_path="data/categories.csv"
)

result = await agent.generate_from_text("今日はプロジェクトA 50%、会議 50%")
print(result.commands)
```

### CDKスタックの更新

```bash
cd cdk
cdk diff    # 変更内容を確認
cdk deploy  # デプロイ
```

## AgentCore CDK L2 Construct

このプロジェクトでは、AWS CDKのL2 Constructを使用してAgentCoreリソースをデプロイします。

詳細は `.kiro/steering/agentcore-cdk-guide.md` を参照してください。

**主要なConstruct:**
- `Runtime`: エージェントのホスティング
- `Gateway`: ツールとMCPサーバーの統合
- `GatewayTarget`: Lambda/OpenAPI/Smithy/MCPサーバーターゲット

## ライセンス

Internal use only
