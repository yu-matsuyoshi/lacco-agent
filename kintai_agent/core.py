"""
Kintai Agent - Core Logic
共通ロジック（HTTP版・A2A版両方で使用）
"""
from typing import Optional, List, Dict, Any
import os
import json
import re
import asyncio
from datetime import datetime
from strands import Agent
from strands.models import BedrockModel

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

from models import (
    CommandResult,
    WorkEntry,
)
from command_generator import CommandGenerator

# Credential Provider名（CLIで作成したもの）
GATEWAY_OAUTH_PROVIDER_NAME = "kintai-gateway-m2m"


def build_system_prompt() -> str:
    """システムプロンプトを構築"""
    return """あなたは工数管理システム（OA Lacco APP）のコマンド生成アシスタントです。

## 役割
- ユーザーの自然言語入力を解析
- 適切なプロジェクト（案件）と区分を特定
- OA Lacco APPのコマンド形式で出力

## 利用可能なツール
1. get_projects: プロジェクト一覧取得
2. get_categories: 区分一覧取得
3. validate_percentage: 割合検証
4. get_calendar_events: カレンダーイベント取得（Task 14で実装予定）

## コマンド形式
OA Lacco APP add <日付> <案件ID> <区分ID> <割合>%

例: OA Lacco APP add 2026/01/27 12345 1 50%

## 処理フロー
1. 日付表現を解析（「明日」→ YYYY/MM/DD）
2. get_projectsツールでプロジェクト一覧を取得
3. プロジェクト名からIDを特定
4. get_categoriesツールで区分一覧を取得
5. 区分名からIDを特定
6. validate_percentageツールで割合を検証（合計100%）
7. コマンドを生成

## 案件マッチングの優先順位
1. 完全一致（confidence: high）
2. 部分一致（1件のみ: high、複数: medium）
3. LLMで候補から選択（複数部分一致: medium）
4. LLMで全検索（類似度: low）

## 出力形式
必ず以下のJSON形式で出力してください：

```json
{
  "success": true,
  "commands": [
    "OA Lacco APP add 2026/01/27 12345 1 50%",
    "OA Lacco APP add 2026/01/27 67890 2 50%"
  ],
  "explanation": "プロジェクトAで開発作業を50%、メンテナンス業務で保守作業を50%実施",
  "warnings": [],
  "suggestions": [],
  "entries": [
    {
      "date": "2026/01/27",
      "project_id": 12345,
      "project_name": "プロジェクトA本体開発",
      "category_id": 1,
      "category_name": "開発",
      "percentage": 50,
      "confidence": "high",
      "reason": "部分一致（1件のみ）"
    },
    {
      "date": "2026/01/27",
      "project_id": 67890,
      "project_name": "メンテナンス業務システム",
      "category_id": 2,
      "category_name": "保守",
      "percentage": 50,
      "confidence": "high",
      "reason": "完全一致"
    }
  ]
}
```

## 注意事項
- 割合の合計は必ず100%にする
- 不明な案件は類似案件を提案
- 曖昧な入力は確認を求める
- 日付は必ずYYYY/MM/DD形式に変換
- 複数の案件がある場合は、それぞれ個別のコマンドを生成
- 必ずJSON形式で出力する

## エラーハンドリング
エラーの場合も以下のJSON形式で出力：

```json
{
  "success": false,
  "commands": [],
  "explanation": "エラーの説明",
  "warnings": ["警告メッセージ"],
  "suggestions": ["提案メッセージ"],
  "entries": []
}
```

- 無効な入力: 問題を説明するエラーメッセージ
- 低信頼度マッチ: 警告を含める
- マッチ失敗: 有効な案件名を提案
- 割合不一致: 具体的な警告と修正提案
"""


class KintaiAgentCore:
    """
    工数管理エージェント - コアロジック

    HTTP版・A2A版で共通して使用するロジックを提供します。
    """

    def __init__(
        self,
        gateway_url: Optional[str] = None,
        model_id: str = "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
        region: str = "us-east-1",
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

        # Bedrockモデルを初期化
        self.model = BedrockModel(
            model_id=self.model_id,
            region_name=self.region,
            temperature=0.3,
            max_tokens=4096,
        )

        # システムプロンプト
        self.system_prompt = build_system_prompt()

    async def get_gateway_token(self) -> Optional[str]:
        """
        @requires_access_tokenデコレータを使用してGateway用アクセストークンを取得
        M2M認証でAgentCore IdentityのCredential Providerと通信
        """
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

    def create_agent_with_tools(self, tools: list) -> Agent:
        """
        ツール付きでAgentを作成

        Args:
            tools: ツールのリスト

        Returns:
            Agent インスタンス
        """
        return Agent(
            model=self.model,
            system_prompt=self.system_prompt,
            tools=tools
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

    def run_with_mcp_context(self, text: str) -> str:
        """
        MCPClientコンテキスト内でAgentを実行

        Args:
            text: ユーザーの自然言語入力

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

        mcp_client = self.create_mcp_client(gateway_token)

        with mcp_client:
            tools = mcp_client.list_tools_sync()
            print(f"✅ Loaded {len(tools)} tools from Gateway")

            agent = self.create_agent_with_tools(tools)
            response = agent(text)
            return str(response)

    def generate_from_text(self, text: str) -> CommandResult:
        """
        自然言語からコマンドを生成

        Args:
            text: ユーザーの自然言語入力

        Returns:
            CommandResult: コマンド生成結果
        """
        try:
            response_str = self.run_with_mcp_context(text)
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
