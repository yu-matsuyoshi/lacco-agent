---
title: Testing and Debugging Guide
inclusion: fileMatch
fileMatchPattern: '**/*test*.{py,ts}'
---

# テストとデバッグガイド

## テスト戦略

### 1. Lambda関数のテスト

#### ローカルテスト

```typescript
// Lambda関数のユニットテスト
import { handler } from '../lambda/get_projects/index';

describe('get_projects', () => {
  it('should return projects from S3', async () => {
    const event = {};
    const result = await handler(event);
    
    expect(result.statusCode).toBe(200);
    expect(JSON.parse(result.body)).toHaveLength(8);
  });
});
```

#### AWS上でのテスト

```bash
# Lambda関数を直接呼び出し
aws lambda invoke \
  --function-name kintai-agent-get-projects \
  --payload '{}' \
  response.json

cat response.json
```

### 2. AgentCore Gatewayのテスト

#### Gateway経由でのツール呼び出し

```python
import boto3

client = boto3.client('bedrock-agent-runtime')

response = client.invoke_agent(
    agentId='AGENT_ID',
    agentAliasId='AGENT_ALIAS_ID',
    sessionId='test-session',
    inputText='get_projectsツールを使ってプロジェクト一覧を取得してください'
)

print(response)
```

### 3. Strands Agentのテスト

#### ユニットテスト

```python
import pytest
from kintai_agent import KintaiAgent

def test_date_parsing():
    """日付解析のテスト"""
    agent = KintaiAgent()
    
    # 「明日」の解析
    result = agent.parse_date("明日")
    assert result == (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    # 「来週月曜」の解析
    result = agent.parse_date("来週月曜")
    # 期待される日付を検証

def test_project_matching():
    """プロジェクトマッチングのテスト"""
    agent = KintaiAgent()
    
    # 完全一致
    result = agent.match_project("プロジェクトA")
    assert result['project_id'] == 1
    assert result['confidence'] == 1.0
    
    # 部分一致
    result = agent.match_project("プロA")
    assert result['project_id'] == 1
    assert result['confidence'] > 0.8

def test_percentage_validation():
    """割合検証のテスト"""
    agent = KintaiAgent()
    
    # 合計100%
    entries = [
        {"percentage": 50},
        {"percentage": 50}
    ]
    result = agent.validate_percentage(entries)
    assert result['valid'] == True
    
    # 合計が100%でない
    entries = [
        {"percentage": 60},
        {"percentage": 30}
    ]
    result = agent.validate_percentage(entries)
    assert result['valid'] == False
    assert result['shortage'] == 10
```

#### 統合テスト

```python
def test_end_to_end():
    """エンドツーエンドテスト"""
    agent = KintaiAgent()
    
    # 自然言語入力
    input_text = "明日はプロジェクトAで開発作業を8時間、プロジェクトBで会議を2時間"
    
    # コマンド生成
    result = agent.generate_from_text(input_text)
    
    # 検証
    assert result['success'] == True
    assert len(result['commands']) == 2
    assert result['commands'][0].startswith("OA Lacco APP")
```

## デバッグ方法

### 1. Lambda関数のデバッグ

#### CloudWatch Logsの確認

```bash
# 最新のログを表示
aws logs tail /aws/lambda/kintai-agent-get-projects --follow

# エラーログのみフィルタ
aws logs filter-log-events \
  --log-group-name /aws/lambda/kintai-agent-get-projects \
  --filter-pattern "ERROR"
```

#### ローカルデバッグ

```typescript
// Lambda関数にデバッグログを追加
export const handler = async (event: any) => {
  console.log('Event:', JSON.stringify(event, null, 2));
  
  try {
    const result = await processEvent(event);
    console.log('Result:', JSON.stringify(result, null, 2));
    return result;
  } catch (error) {
    console.error('Error:', error);
    throw error;
  }
};
```

### 2. AgentCore Gatewayのデバッグ

#### Gateway呼び出しのトレース

```python
import boto3
import json

client = boto3.client('bedrock-agent-runtime')

# トレース有効化
response = client.invoke_agent(
    agentId='AGENT_ID',
    agentAliasId='AGENT_ALIAS_ID',
    sessionId='debug-session',
    inputText='test input',
    enableTrace=True  # トレース有効化
)

# トレース情報の表示
for event in response['completion']:
    if 'trace' in event:
        print(json.dumps(event['trace'], indent=2))
```

### 3. Strands Agentのデバッグ

#### ログレベルの設定

```python
import logging

# デバッグログを有効化
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('strands_agents')
logger.setLevel(logging.DEBUG)

# エージェント実行
agent = KintaiAgent()
response = agent.run("test input")
```

#### ツール呼び出しのトレース

```python
from strands_agents import Agent

class DebugAgent(Agent):
    def call_tool(self, tool_name: str, parameters: dict):
        print(f"Calling tool: {tool_name}")
        print(f"Parameters: {parameters}")
        
        result = super().call_tool(tool_name, parameters)
        
        print(f"Result: {result}")
        return result
```

## パフォーマンステスト

### レスポンスタイムの測定

```python
import time

def measure_performance():
    agent = KintaiAgent()
    
    test_inputs = [
        "明日はプロジェクトAで8時間",
        "来週月曜から金曜までプロジェクトBで作業",
        "今日の午前は会議、午後は開発"
    ]
    
    for input_text in test_inputs:
        start = time.time()
        result = agent.generate_from_text(input_text)
        elapsed = time.time() - start
        
        print(f"Input: {input_text}")
        print(f"Time: {elapsed:.2f}s")
        print(f"Success: {result['success']}")
        print("---")
```

## トラブルシューティング

### よくある問題と解決方法

#### 1. Lambda関数がS3にアクセスできない

**症状**: `AccessDenied` エラー

**解決方法**:
```typescript
// CDKでIAM権限を確認
this.dataBucket.grantRead(this.getProjectsFn);
```

#### 2. Gatewayツールが呼び出されない

**症状**: エージェントがツールを使用しない

**解決方法**:
- ツール名のプレフィックスを確認（`ターゲット名___ツール名`）
- システムプロンプトでツールの使用方法を明示
- ツールの説明を具体的に記述

#### 3. 割合の合計が100%にならない

**症状**: `validate_percentage`が失敗

**解決方法**:
```python
# 浮動小数点の丸め誤差を考慮
def validate_percentage(entries):
    total = sum(e['percentage'] for e in entries)
    # 0.01の誤差を許容
    return abs(total - 100.0) < 0.01
```

#### 4. 日付解析が失敗する

**症状**: 「明日」「来週」などが正しく解析されない

**解決方法**:
```python
from datetime import datetime, timedelta
import dateparser

def parse_date(date_str: str) -> str:
    # dateparserライブラリを使用
    parsed = dateparser.parse(date_str, languages=['ja'])
    if parsed:
        return parsed.strftime("%Y-%m-%d")
    
    # フォールバック処理
    # ...
```

## CI/CDでのテスト

### GitHub Actionsの例

```yaml
name: Test

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-cov
    
    - name: Run tests
      run: |
        pytest --cov=kintai_agent tests/
    
    - name: Build CDK
      run: |
        cd cdk
        npm install
        npm run build
        npm test
```

## 参考リンク

- [pytest Documentation](https://docs.pytest.org/)
- [AWS Lambda Testing](https://docs.aws.amazon.com/lambda/latest/dg/testing-functions.html)
- [Strands Agents Testing](https://github.com/awslabs/strands-agents/tree/main/tests)
