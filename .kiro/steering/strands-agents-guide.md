---
title: Strands Agents Implementation Guide
inclusion: fileMatch
fileMatchPattern: 'kintai_agent/**/*.py'
---

# Strands Agents 実装ガイド

このプロジェクトでは、Strands Agents SDKを使用してAIエージェントを実装します。

## 基本構造

```python
from strands_agents import Agent, Tool, ToolResult
from strands_agents.bedrock import BedrockLLM

# エージェント初期化
agent = Agent(
    name="kintai-agent",
    llm=BedrockLLM(model_id="anthropic.claude-3-5-sonnet-20241022-v2:0"),
    system_prompt="あなたは勤怠管理のアシスタントです...",
    tools=[tool1, tool2, tool3]
)

# エージェント実行
response = agent.run("明日はプロジェクトAで8時間作業します")
```

## ツール定義

### AgentCore Gateway経由のツール

AgentCore Gatewayに登録されたツールを使用する場合：

```python
from strands_agents import Tool

# Gatewayツールの定義
get_projects_tool = Tool(
    name="get-projects___get_projects",  # ターゲット名___ツール名
    description="Get all available projects",
    parameters={
        "type": "object",
        "properties": {}
    },
    function=lambda **kwargs: call_gateway_tool("get-projects___get_projects", kwargs)
)
```

**重要**: Gateway経由のツールは`ターゲット名___ツール名`の形式になります。

### ツール実装パターン

```python
def call_gateway_tool(tool_name: str, parameters: dict) -> ToolResult:
    """AgentCore Gateway経由でツールを呼び出す"""
    import boto3
    
    client = boto3.client('bedrock-agent-runtime')
    
    response = client.invoke_agent(
        agentId=AGENT_ID,
        agentAliasId=AGENT_ALIAS_ID,
        sessionId=SESSION_ID,
        inputText=f"Use tool {tool_name} with parameters {parameters}"
    )
    
    return ToolResult(
        success=True,
        data=response['output']
    )
```

## システムプロンプト設計

### 基本構造

```python
SYSTEM_PROMPT = """
あなたは勤怠管理システム（OA Lacco APP）のコマンド生成アシスタントです。

## 役割
- ユーザーの自然言語入力を解析
- 適切なプロジェクトと区分を特定
- OA Lacco APPのコマンド形式で出力

## 利用可能なツール
1. get-projects___get_projects: プロジェクト一覧取得
2. get-categories___get_categories: 区分一覧取得
3. validate-percentage___validate_percentage: 割合検証
4. google-calendar___get_events: カレンダーイベント取得

## コマンド形式
OA Lacco APP <日付> <案件ID> <区分ID> <割合>%

## 処理フロー
1. 日付表現を解析（「明日」→ YYYY-MM-DD）
2. プロジェクト名からIDを特定
3. 区分名からIDを特定
4. 割合を検証（合計100%）
5. コマンドを生成

## 注意事項
- 割合の合計は必ず100%にする
- 不明な案件は類似案件を提案
- 曖昧な入力は確認を求める
"""
```

## エラーハンドリング

```python
from strands_agents import AgentError

try:
    response = agent.run(user_input)
    
    if not response.success:
        # エラー処理
        print(f"Error: {response.error}")
        
    # 成功時の処理
    commands = response.data.get('commands', [])
    
except AgentError as e:
    # エージェントエラー
    print(f"Agent error: {e}")
    
except Exception as e:
    # その他のエラー
    print(f"Unexpected error: {e}")
```

## AgentCore Runtimeへのデプロイ

### 1. エージェントコードのパッケージング

```bash
# 依存関係を含めてパッケージ化
pip install -r requirements.txt -t ./package
cp -r kintai_agent ./package/
cd package && zip -r ../agent.zip .
```

### 2. CDKでのデプロイ

```python
from aws_cdk.aws_bedrock_agentcore_alpha import (
    Runtime,
    AgentRuntimeArtifact
)

runtime = Runtime(
    self, "KintaiRuntime",
    runtime_name="kintai-agent",
    agent_runtime_artifact=AgentRuntimeArtifact.from_asset("./agent.zip"),
    environment_variables={
        "GATEWAY_ID": gateway.gateway_id,
        "DATA_BUCKET": data_bucket.bucket_name
    }
)
```

## ベストプラクティス

### 1. ツール呼び出しの最適化

- 必要なツールのみを呼び出す
- キャッシュ可能なデータはキャッシュする
- 並列実行可能なツールは並列化

### 2. プロンプトエンジニアリング

- 具体的な例を含める
- エッジケースを明示
- 期待される出力形式を明確に

### 3. セッション管理

```python
# セッションIDを使用して会話履歴を保持
session_id = str(uuid.uuid4())

response1 = agent.run("明日はプロジェクトAで作業", session_id=session_id)
response2 = agent.run("割合は50%で", session_id=session_id)  # 前の文脈を保持
```

## トラブルシューティング

### ツールが呼び出されない

- ツール名が正しいか確認（プレフィックス含む）
- ツールの説明が明確か確認
- システムプロンプトでツールの使用方法を明示

### Gateway接続エラー

- Gateway ARNが正しいか確認
- IAM権限が付与されているか確認
- ネットワーク設定を確認（VPC/Public）

### レスポンスが遅い

- 不要なツール呼び出しを削減
- キャッシュを活用
- タイムアウト設定を調整

## 参考リンク

- [Strands Agents GitHub](https://github.com/awslabs/strands-agents)
- [Strands Agents Examples](https://github.com/awslabs/strands-agents/tree/main/examples)
- [AgentCore Runtime API](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_agent-runtime_InvokeAgent.html)
