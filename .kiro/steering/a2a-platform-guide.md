---
title: A2A Platform Implementation Guide
---

# 共通A2Aクライアント実装ガイド

## 概要

複数のA2Aサーバー（エージェント）を統合し、共通のA2Aクライアントから利用するプラットフォームの構築ガイド。

## アーキテクチャ

### 現状（個別クライアント）

```
[Streamlit Client A] → [Cognito A] → [Kintai Agent Runtime]
[Streamlit Client B] → [Cognito B] → [Expense Agent Runtime]
```

### 目標（共通クライアント）

```
                                    ┌→ [Kintai Agent Runtime]
[共通A2Aクライアント] → [共通Cognito] → [Expense Agent Runtime]
  (React/Next.js)                   └→ [Other Agent Runtime]
```

## 現状の認証フロー（Kintai Agent）

### 全体像

```
ユーザー ─[Cognito Token]→ Runtime ─[M2M Token]→ Gateway ─[IAM]→ Lambda
              │                        │
              │                        └─ AgentCore Identity
              │                           (Credential Provider)
              │
              └─ Cognito 直接認証
```

### 各区間の認証

| 区間 | 認証方式 | AgentCore Identity | 説明 |
|------|---------|-------------------|------|
| ユーザー → Runtime | Cognito 直接 | ❌ 不使用 | ユーザーがログインしてトークン取得 |
| Runtime → Gateway | M2M (OAuth2) | ✅ 使用 | `@requires_access_token` で自動取得 |
| Gateway → Lambda | IAM | ❌ 不使用 | Gateway の ServiceRole が自動付与 |

### 1. ユーザー → Runtime（Cognito 直接認証）

AgentCore Identity は**介在しない**。Cognito User Pool と直接やり取り。

```
ユーザー                    Cognito User Pool                 Runtime
   │                              │                              │
   │─── ログイン ────────────────→│                              │
   │    (username/password)       │                              │
   │                              │                              │
   │←── Access Token ────────────│                              │
   │                              │                              │
   │────────── Bearer Token ─────────────────────────────────────→│
   │                              │                              │
   │                              │←── トークン検証 ─────────────│
```

**フロントエンド (`frontend_a2a/app.py`):**
```python
cognito = boto3.client('cognito-idp', region_name=REGION)
response = cognito.initiate_auth(
    ClientId=CLIENT_ID,
    AuthFlow='USER_PASSWORD_AUTH',
    AuthParameters={'USERNAME': username, 'PASSWORD': password}
)
access_token = response['AuthenticationResult']['AccessToken']

# Runtime 呼び出し
headers = {"Authorization": f"Bearer {access_token}"}
```

**CDK設定:**
```typescript
authorizerConfiguration: agentcore.RuntimeAuthorizerConfiguration.usingCognito(
  this.userPool,
  [this.userPoolClient]
),
```

### 2. Runtime → Gateway（AgentCore Identity 使用）

AgentCore Identity の **Credential Provider** を使用して M2M トークンを取得。

```
Runtime                      AgentCore Identity                    Gateway
   │                                │                                  │
   │─── トークン要求 ──────────────→│                                  │
   │    (Credential Provider名)     │                                  │
   │                                │                                  │
   │                                │─── Cognito M2M ────→ Cognito    │
   │                                │←── アクセストークン ──           │
   │                                │                                  │
   │←── Gateway用トークン ─────────│                                  │
   │                                                                   │
   │────────────── M2Mトークンで呼び出し ─────────────────────────────→│
```

**エージェントコード (`kintai_agent/core.py`):**
```python
from bedrock_agentcore.identity.auth import requires_access_token

CREDENTIAL_PROVIDER_NAME = "kintai-gateway-m2m"

@requires_access_token(
    credential_provider_name=CREDENTIAL_PROVIDER_NAME,
    scopes=["gateway/invoke"],
)
def get_token_inner(access_token: str = None):
    return access_token
```

**関連リソース:**

| リソース | 管理場所 | 作成方法 |
|---------|---------|---------|
| `kintai-gateway-m2m` Credential Provider | AgentCore Identity (Token Vault) | スクリプト |
| Client Secret | Secrets Manager | 自動作成 |
| M2M Client | Cognito User Pool | CDK |

### 3. Gateway → Lambda（IAM 認証）

Gateway が Lambda を呼び出す際は IAM 権限を使用。CDK で自動設定。

```typescript
// CDK で addLambdaTarget 時に自動で権限付与
this.gateway.addLambdaTarget('GetProjectsTarget', {
  targetName: 'get-projects',
  lambdaFunction: this.getProjectsFn,
  // ...
});
// → Gateway の ServiceRole に lambda:InvokeFunction が付与される
```

### Runtime Authorizer の選択肢

```typescript
// 1. Cognito 認証（現在使用中）
authorizerConfiguration: agentcore.RuntimeAuthorizerConfiguration.usingCognito(
  userPool, [userPoolClient]
),

// 2. IAM 認証
authorizerConfiguration: agentcore.RuntimeAuthorizerConfiguration.usingIam(),

// 3. カスタム JWT 認証（共通Cognito対応時）
authorizerConfiguration: agentcore.RuntimeAuthorizerConfiguration.usingCustomJwt({
  discoveryUrl: 'https://cognito-idp.../.../.well-known/openid-configuration',
  allowedClients: ['client-id'],
  allowedAudiences: ['audience'],
}),

// 4. 認証なし（開発用）
authorizerConfiguration: agentcore.RuntimeAuthorizerConfiguration.none(),
```

---

## 認証・認可（共通クライアント対応）

### 方式の選択

| 方式 | 説明 | 推奨度 |
|------|------|--------|
| JWT Authorizer | 共通CognitoのJWTを各Runtimeで検証 | ★★★ 推奨 |
| 共通Cognito参照 | 各RuntimeがARNで共通Cognitoを参照 | ★★ |
| IAM認証 | 同一アカウント内でIAM認証 | ★ |

### JWT Authorizer 方式（推奨）

各A2AサーバーのCDKを以下のように変更：

```typescript
// 変更前（独自Cognito）
authorizerConfiguration: agentcore.RuntimeAuthorizerConfiguration.usingCognito(
  this.userPool,
  [this.userPoolClient]
),

// 変更後（共通CognitoのJWT検証）
authorizerConfiguration: agentcore.RuntimeAuthorizerConfiguration.usingCustomJwt({
  discoveryUrl: 'https://cognito-idp.ap-northeast-1.amazonaws.com/<SHARED_USER_POOL_ID>/.well-known/openid-configuration',
  allowedClients: ['<SHARED_CLIENT_ID>'],
  allowedAudiences: ['<SHARED_CLIENT_ID>'],
}),
```

### メリット

- 各エージェントが独立してデプロイ可能
- 共通Cognitoの変更に影響されにくい
- クロスアカウントでも対応可能

## エージェント登録・発見

### Agent Card

A2Aプロトコルでは `/.well-known/agent-card.json` でエージェント情報を公開：

```json
{
  "name": "kintai-agent",
  "description": "工数管理エージェント - 自然言語から工数入力コマンドを生成",
  "version": "1.0.0",
  "capabilities": {
    "streaming": true
  },
  "url": "https://bedrock-agentcore.../invocations/"
}
```

### Agent Card の定義場所

`kintai_agent/agent_a2a.py`:

```python
# Agent 作成時に name と description を定義
agent = Agent(
    model=core.model,
    system_prompt=build_system_prompt(output_format="natural"),
    tools=[],
    name="kintai-agent",
    description="工数管理エージェント - 自然言語から工数入力コマンドを生成",
)

# A2A Server でバージョンと capabilities を設定
a2a_server = KintaiA2AServer(
    agent=agent,
    version="1.0.0",
    # ...
)

# capabilities は KintaiA2AServer 内で設定
self.capabilities = AgentCapabilities(streaming=True)
```

### エージェントレジストリ

共通クライアントで利用可能なエージェント一覧を管理：

```typescript
// DynamoDB または設定ファイルで管理
const agentsRegistry = [
  {
    id: "kintai",
    name: "勤怠管理エージェント",
    runtimeArn: "arn:aws:bedrock-agentcore:ap-northeast-1:XXXXXXXXXXXX:runtime/kintai_agent_a2a-xxx",
    capabilities: ["勤怠入力", "工数管理"],
    contact: "team-a@example.com"
  },
  {
    id: "expense",
    name: "経費精算エージェント",
    runtimeArn: "arn:aws:bedrock-agentcore:ap-northeast-1:XXXXXXXXXXXX:runtime/expense_agent_a2a-xxx",
    capabilities: ["経費申請", "承認ワークフロー"],
    contact: "team-b@example.com"
  },
];
```

## フレームワーク選択

### 比較表

| フレームワーク | A2A Client | 言語 | 特徴 |
|---------------|------------|------|------|
| **Mastra** | ✅ `@mastra/client-js` | TypeScript | TypeScriptファースト、Gatsbyチーム製 |
| Strands Agents (TS) | ❌ 未対応 | TypeScript | Python版のみA2AAgent対応 |
| **@a2a-js/sdk** | ✅ `ClientFactory` | TypeScript | 公式A2A SDK |
| a2a-sdk (Python) | ✅ | Python | 現在のStreamlitで使用中 |

### Mastra（推奨）

```bash
npm install @mastra/client-js
```

```typescript
import { A2A } from "@mastra/client-js";

// A2A クライアント初期化
const a2a = new A2A({ serverUrl: "https://your-a2a-server.com" });

// Agent Card 取得
const agentCard = await a2a.getAgentCard("agent-id");

// メッセージ送信
await a2a.sendMessage({
  to: "agent-id",
  from: "client",
  content: "プロジェクト一覧を教えて",
});

// タスク作成・ストリーミング
const task = await a2a.createTask({
  agentId: "agent-id",
  taskType: "query",
  payload: { query: "..." },
});

a2a.streamTaskUpdates(task.id, (update) => {
  console.log("Task update:", update);
});
```

### @a2a-js/sdk

```bash
npm install @a2a-js/sdk
```

```typescript
import { ClientFactory } from '@a2a-js/sdk';

const client = await ClientFactory.create({
  endpoint: 'https://bedrock-agentcore.../runtimes/{arn}/invocations',
  headers: {
    'Authorization': `Bearer ${accessToken}`,
  },
});

const response = await client.sendMessage({
  role: 'user',
  parts: [{ kind: 'text', text: 'メッセージ' }],
  contextId: 'xxx',
});
```

### 自前実装（fetch）

```typescript
// Agent Card 取得
const getAgentCard = async (runtimeArn: string, accessToken: string) => {
  const encodedArn = encodeURIComponent(runtimeArn);
  const baseUrl = `https://bedrock-agentcore.${region}.amazonaws.com/runtimes/${encodedArn}/invocations`;

  const res = await fetch(`${baseUrl}/.well-known/agent-card.json`, {
    headers: { 'Authorization': `Bearer ${accessToken}` },
  });
  return res.json();
};

// A2A メッセージ送信（JSON-RPC）
const sendMessage = async (baseUrl: string, message: string, contextId: string, accessToken: string) => {
  const res = await fetch(baseUrl, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${accessToken}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      jsonrpc: '2.0',
      method: 'message/send',
      params: {
        message: {
          role: 'user',
          parts: [{ kind: 'text', text: message }],
          messageId: crypto.randomUUID(),
          contextId,
        },
      },
      id: crypto.randomUUID(),
    }),
  });
  return res.json();
};
```

## ネットワークアクセス

### 現状

各A2Aサーバーは `RuntimeNetworkConfiguration.usingPublicNetwork()` を使用しており、パブリックアクセス可能。

### 確認事項

- 各A2Aサーバーがパブリックアクセス可能か
- VPC内のみの場合は VPC Peering や PrivateLink が必要

## IAM権限

### 共通A2Aクライアントに必要な権限

同一アカウント内で複数のA2Aサーバーを呼び出す場合：

```json
{
  "Effect": "Allow",
  "Action": "bedrock-agentcore:InvokeRuntime",
  "Resource": [
    "arn:aws:bedrock-agentcore:ap-northeast-1:XXXXXXXXXXXX:runtime/*"
  ]
}
```

または特定のランタイムのみ：

```json
{
  "Effect": "Allow",
  "Action": "bedrock-agentcore:InvokeRuntime",
  "Resource": [
    "arn:aws:bedrock-agentcore:ap-northeast-1:XXXXXXXXXXXX:runtime/kintai_agent_a2a-*",
    "arn:aws:bedrock-agentcore:ap-northeast-1:XXXXXXXXXXXX:runtime/expense_agent_a2a-*"
  ]
}
```

## コンテキスト管理

### context_id の設計

| パターン | 説明 |
|---------|------|
| ユーザーセッション単位 | 1ユーザー = 1 context_id |
| エージェントごと | エージェント × ユーザー = context_id |
| 会話ごと | 新規会話のたびに新しい context_id |

### 会話履歴

- 各エージェントの AgentCore Memory は独立
- context_id はエージェントごとに管理
- マルチエージェント会話ではオーケストレーションが必要

## インターフェース標準化

### Agent Card の標準項目

各チームで以下を統一：

```json
{
  "name": "agent-name",
  "description": "エージェントの説明",
  "version": "1.0.0",
  "capabilities": {
    "streaming": true,
    "tasks": ["query", "action"]
  },
  "contact": "team@example.com",
  "tags": ["勤怠", "工数管理"]
}
```

### エラーレスポンス形式

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "入力が不正です",
    "details": {}
  }
}
```

## CDK変更チェックリスト

各A2Aサーバーを共通クライアント対応にする際の変更点：

- [ ] `authorizerConfiguration` を JWT Authorizer に変更
- [ ] 独自 Cognito リソースを削除（オプション）
- [ ] Agent Card の `name`, `description`, `version` を適切に設定
- [ ] エージェントレジストリに登録

## 参考リンク

- [Mastra - The TypeScript AI Framework](https://mastra.ai/)
- [Mastra A2A Changelog](https://mastra.ai/blog/changelog-2025-05-15)
- [@a2a-js/sdk - GitHub](https://github.com/a2aproject/a2a-js)
- [A2A Protocol Documentation](https://a2aprotocol.ai/docs/guide/a2a-typescript-guide)
- [Strands Agents A2A](https://strandsagents.com/docs/user-guide/concepts/multi-agent/agent-to-agent/)
- [AWS CDK AgentCore](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-bedrock-agentcore-alpha-readme.html)
