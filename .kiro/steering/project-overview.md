---
title: Kintai Agent Project Overview
---

# Kintai Agent プロジェクト概要

## プロジェクトの目的

自然言語入力から勤怠管理システム（OA Lacco APP）のコマンドを生成するAIエージェント。

## アーキテクチャ

### デプロイ構成
- **エージェント**: AWS Bedrock AgentCore Runtime（A2Aプロトコル、Strands Agents SDK使用）
- **メモリ**: AWS Bedrock AgentCore Memory（会話履歴の永続化・自動要約）
- **認証**: Amazon Cognito User Pool
- **ツール**: AWS Lambda関数（TypeScript）
- **ゲートウェイ**: AWS Bedrock AgentCore Gateway
- **UI**: Streamlit（A2A版、ローカル実行）
- **インフラ**: AWS CDK（TypeScript）

### データフロー（A2Aプロトコル）
1. ユーザーがStreamlit UIでログイン（Cognito認証）
2. ユーザーが自然言語入力
3. Streamlit → AgentCore Runtime（A2Aプロトコル、context_id付き）
4. Runtime → Memory（会話履歴取得・保存）
5. Runtime → Gateway → Lambda/MCP Server
6. Lambda → S3（マスタデータ取得）
7. 結果をStreamlit UIに表示

### 会話履歴管理
- `context_id`: A2Aプロトコルの会話コンテキスト識別子
- `AgentCoreMemorySessionManager`: strands-agents統合でAgent作成時に渡す
- 自動要約: 長い会話でも要約してコンテキストを維持

## 主要コンポーネント

### 1. Lambda関数（ツール）
- `get_projects`: プロジェクトマスタ取得
- `get_categories`: 区分マスタ取得
- `validate_percentage`: 割合検証

### 2. AgentCore Gateway
- Lambda Targetでツールを公開
- MCP Server Targetで外部サービス連携（Google Calendar）
- OAuth2認証管理（AgentCore Identity経由）

### 3. AgentCore Identity
- **M2M認証**: Runtime→Gateway間の認証にOAuth2 Credential Provider（`kintai-gateway-m2m`）を使用
- Cognito User PoolのM2Mクライアントと連携
- `@requires_access_token`デコレータでトークン取得を自動化
- **注意**: CDK L2 Constructは未提供のため、CDKデプロイ後に別途セットアップが必要
  - セットアップスクリプト: `cdk/scripts/setup-m2m-credential-provider.sh`

### 4. Strands Agent
- 自然言語理解
- コマンド生成
- エラーハンドリング

### 5. AgentCore Memory
- 会話履歴の永続化
- BuiltInSummarization戦略で自動要約
- `AgentCoreMemorySessionManager`でstrands-agents統合
- `context_id`をsession_idとして使用

### 6. Cognito User Pool
- ユーザー認証（USER_PASSWORD_AUTH）
- アクセストークン発行
- ランタイムへの認証に使用

### 7. DynamoDB トークンキャッシュ
- M2Mトークンの共有キャッシュ（全コンテナで共有）
- Cognito M2Mリクエスト数を削減しコスト最適化
- TTL属性による自動削除（トークン期限＋1時間後）
- AgentCore Runtimeのコンテナ入れ替わりに対応

## 開発ガイドライン

### コーディング規約
- **CDK**: TypeScript、L2 Constructを使用
- **Lambda**: TypeScript、Node.js 20.x
- **Agent**: Python、Strands Agents SDK
- **UI**: Python、Streamlit

### ファイル構成
```
.
├── cdk/                    # CDKインフラコード（TypeScript）
│   ├── lib/               # スタック定義
│   │   └── kintai-agent-stack.ts  # メインスタック（Gateway, Runtime, Memory, Cognito, DynamoDB）
│   ├── lambda/            # Lambda関数
│   └── bin/               # エントリーポイント
├── kintai_agent/          # Pythonエージェントコード
│   ├── agent_a2a.py       # A2Aサーバー実装（Memory統合）
│   ├── core.py            # KintaiAgentCoreクラス（DynamoDBトークンキャッシュ含む）
│   └── requirements.txt   # 依存関係
├── frontend_a2a/          # A2A版Streamlit UI
│   ├── app.py             # メインアプリ
│   ├── config.py          # 設定（Cognito情報等）
│   └── requirements.txt   # 依存関係
├── data/                  # マスタデータ（CSV）
│   ├── projects.csv       # プロジェクトマスタ
│   └── categories.csv     # 区分マスタ
└── .kiro/
    ├── specs/             # 仕様書
    └── steering/          # プロジェクトガイド
```

### 環境変数

**Runtime（A2A）環境変数**:
- `AWS_REGION`: AWSリージョン
- `GATEWAY_URL`: AgentCore GatewayのMCPエンドポイント
- `MODEL_ID`: Bedrockモデル ID（例: `us.anthropic.claude-sonnet-4-5-20250929-v1:0`）
- `AGENTCORE_MEMORY_ID`: AgentCore MemoryのID
- `AGENTCORE_RUNTIME_URL`: A2AランタイムのURL
- `TOKEN_CACHE_TABLE`: DynamoDBトークンキャッシュテーブル名

**Frontend設定（config.py）**:
- `REGION`: AWSリージョン
- `USER_POOL_ID`: Cognito User Pool ID
- `CLIENT_ID`: Cognito App Client ID
- `RUNTIME_ARN`: AgentCore Runtime ARN
- `API_TIMEOUT`: APIタイムアウト（秒）

## 重要な制約

1. **AgentCore Gateway**: ツール名にターゲット名がプレフィックスされる（例: `get-projects___get_projects`）
2. **AgentCore Identity（M2M認証）**: OAuth2 Credential ProviderのCDK L2 Constructは未提供
   - CDKデプロイ後に `cdk/scripts/setup-m2m-credential-provider.sh` を実行
   - Cognito M2MクライアントとAgentCore Identityを連携
3. **AgentCore Identity（Google Calendar）**: OAuth2設定は事前にAWSコンソールまたはPython SDKで作成が必要
   - スクリプト: `cdk/scripts/setup-google-calendar-oauth.py`
   - 初回ユーザー承認後、Token Vaultで自動管理
4. **S3アクセス**: Lambda関数にはS3読み込み権限が必要
5. **Streamlit**: ローカル実行のみ、AWSにデプロイしない
6. **A2Aプロトコル**:
   - `context_id`は33文字以上が必要（不足時はパディング）
   - リクエストごとにAgentを作成（MCPClient経由でツール取得）
   - `KintaiA2AExecutor`でカスタム実行ロジックを実装
7. **AgentCore Memory**:
   - `session_id`は33文字以上が必要
   - `bedrock-agentcore[strands-agents]`パッケージが必要
   - Agent作成時に`session_manager`引数で統合
8. **AgentCore Runtime スケーリング**:
   - 完全サーバーレス設計（最小インスタンス数の設定不可）
   - コンテナは15分のアイドル後に自動終了
   - コンテナが頻繁に入れ替わるため、インメモリキャッシュは効果が限定的
   - M2Mトークン等はDynamoDBで共有キャッシュを推奨

## 新しいAWSアカウントへのデプロイ

### 手順

1. **CDKブートストラップ**
   ```bash
   cd cdk
   AWS_REGION=us-east-1 CDK_DEFAULT_REGION=us-east-1 npx cdk bootstrap --profile <新アカウントprofile>
   ```

2. **CDKデプロイ**
   ```bash
   AWS_REGION=us-east-1 CDK_DEFAULT_REGION=us-east-1 npx cdk deploy --profile <新アカウントprofile>
   ```

3. **M2M Credential Providerセットアップ**
   ```bash
   cd cdk/scripts
   ./setup-m2m-credential-provider.sh --profile <新アカウントprofile>
   ```

4. **フロントエンド設定更新**
   - `frontend_a2a/config.py` を新アカウントの値に更新
   - CDK出力から `UserPoolId`、`ClientId`、`RuntimeARN` を取得

5. **Cognitoユーザー作成**
   - AWSコンソールまたはCLIでテスト用ユーザーを作成

### 注意事項
- CDKデプロイだけでは不完全（M2M Credential Providerが未作成）
- `setup-m2m-credential-provider.sh` を必ず実行すること

## よく使うコマンド

### CDKデプロイ
```bash
# cdkディレクトリに移動
cd cdk

# 差分確認（us-east-1リージョン指定）
AWS_REGION=us-east-1 CDK_DEFAULT_REGION=us-east-1 npx cdk diff --profile private-us

# デプロイ（us-east-1リージョン指定）
AWS_REGION=us-east-1 CDK_DEFAULT_REGION=us-east-1 npx cdk deploy --profile private-us

# デプロイ（承認スキップ）
AWS_REGION=us-east-1 CDK_DEFAULT_REGION=us-east-1 npx cdk deploy --profile private-us --require-approval never
```

**注意**: CDK_DEFAULT_REGIONを明示的に指定しないと、デフォルトリージョン（ap-northeast-1等）にデプロイされる場合があります。

### Streamlit起動（A2A版）
```bash
# frontend_a2aディレクトリに移動
cd frontend_a2a

# 依存関係インストール（初回のみ）
pip install -r requirements.txt

# Streamlit起動
streamlit run app.py
```

### ログ確認
```bash
# Runtime（A2A）のログ確認
aws logs tail /aws/bedrock-agentcore/runtime/kintai-agent-a2a --follow

# Lambdaのログ確認
aws logs tail /aws/lambda/KintaiAgentStack-GetProjects* --follow
```

### 環境変数の確認
```bash
# CDK出力からランタイムARNを取得
aws cloudformation describe-stacks --stack-name KintaiAgentStack \
  --query 'Stacks[0].Outputs[?OutputKey==`RuntimeA2AArn`].OutputValue' --output text

# Cognito設定の取得
aws cloudformation describe-stacks --stack-name KintaiAgentStack \
  --query 'Stacks[0].Outputs' --output table
```

### テスト
```bash
# kintai_agentディレクトリでテスト
cd kintai_agent
python -m pytest tests/ -v
```

## 参考リンク

- [Strands Agents SDK](https://github.com/awslabs/strands-agents)
- [AgentCore Documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore.html)
- [A2A Protocol (a2a-sdk)](https://pypi.org/project/a2a-sdk/)
- [OA Lacco APP](https://www.oa-lacco.com/)
