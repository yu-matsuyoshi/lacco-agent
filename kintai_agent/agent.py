"""
Kintai Agent - HTTP Version
AgentCore Runtime エントリーポイント（HTTP プロトコル）
"""
from typing import Dict, Any
import os

from bedrock_agentcore.runtime import BedrockAgentCoreApp

from core import KintaiAgentCore, MCP_AVAILABLE, GATEWAY_OAUTH_PROVIDER_NAME

# MCP imports for debug action
try:
    from strands.tools.mcp.mcp_client import MCPClient
    from mcp.client.streamable_http import streamable_http_client
except ImportError:
    MCPClient = None
    streamable_http_client = None


# AgentCore Runtimeアプリケーションを初期化
app = BedrockAgentCoreApp()

# エージェントインスタンスを作成
agent_instance = KintaiAgentCore(
    gateway_url=os.getenv("GATEWAY_URL"),
    model_id=os.getenv("MODEL_ID", "jp.anthropic.claude-sonnet-4-6"),
    region=os.getenv("AWS_REGION", "ap-northeast-1"),
)


@app.entrypoint
def handle_request(payload: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    """
    AgentCore Runtimeのエントリーポイント（HTTP版）

    Args:
        payload: リクエストペイロード
            - action: "generate_from_text" / "generate_from_calendar" / "debug"
            - text: 自然言語入力（action="generate_from_text"の場合）
            - date: 対象日付（action="generate_from_calendar"の場合）
            - session_id: セッションID（Memory統合用、オプション）
            - actor_id: アクターID（ユーザーID、オプション）
        context: リクエストコンテキスト

    Returns:
        レスポンス辞書（JSON形式）
    """
    try:
        action = payload.get("action", "generate_from_text")
        session_id = payload.get("session_id")
        actor_id = payload.get("actor_id", "default-actor")

        # デバッグ用
        if action == "debug":
            return _handle_debug(context)

        if action == "generate_from_text":
            text = payload.get("text", "")
            if not text:
                return {
                    "success": False,
                    "error": "テキスト入力が必要です",
                    "commands": [],
                    "explanation": "",
                    "warnings": [],
                    "suggestions": [],
                    "entries": []
                }

            result = agent_instance.generate_from_text(text, session_id, actor_id)
            return _format_result(result)

        elif action == "generate_from_calendar":
            date = payload.get("date", "")
            if not date:
                return {
                    "success": False,
                    "error": "日付が必要です（YYYY-MM-DD形式）",
                    "commands": [],
                    "explanation": "",
                    "warnings": [],
                    "suggestions": [],
                    "entries": []
                }

            result = agent_instance.generate_from_calendar(date)
            return _format_result(result)

        else:
            return {
                "success": False,
                "error": f"不明なアクション: {action}",
                "commands": [],
                "explanation": "",
                "warnings": [],
                "suggestions": [],
                "entries": []
            }

    except Exception as e:
        return {
            "success": False,
            "error": f"エラーが発生しました: {str(e)}",
            "commands": [],
            "explanation": "",
            "warnings": [],
            "suggestions": [],
            "entries": []
        }


def _format_result(result) -> Dict[str, Any]:
    """CommandResultをJSON形式に変換"""
    return {
        "success": result.success,
        "commands": result.commands,
        "explanation": result.explanation,
        "warnings": result.warnings,
        "suggestions": result.suggestions,
        "entries": [
            {
                "date": e.date,
                "project_id": e.project_id,
                "project_name": e.project_name,
                "category_id": e.category_id,
                "category_name": e.category_name,
                "percentage": e.percentage,
                "confidence": e.confidence,
                "reason": e.reason
            }
            for e in result.entries
        ]
    }


def _handle_debug(context: Any) -> Dict[str, Any]:
    """デバッグ情報を返す"""
    context_info = {}
    headers_dict = {}

    if context and hasattr(context, 'request') and context.request:
        for key, value in context.request.headers.items():
            if "authorization" in key.lower() and len(value) > 30:
                headers_dict[key] = value[:30] + "..."
            else:
                headers_dict[key] = value
        context_info["headers"] = headers_dict

    # M2M OAuth2トークン取得テスト
    oauth2_test_result = "NOT_TESTED"
    oauth2_error = None
    mcp_test_result = "NOT_TESTED"
    mcp_tools_count = 0
    mcp_error = None

    try:
        gateway_token = agent_instance.get_gateway_token_sync()
        if gateway_token:
            oauth2_test_result = f"SUCCESS (token length: {len(gateway_token)})"

            # MCPClient接続テスト
            if MCP_AVAILABLE and agent_instance.gateway_url:
                try:
                    mcp_client = agent_instance.create_mcp_client(gateway_token)
                    with mcp_client:
                        tools = mcp_client.list_tools_sync()
                        mcp_tools_count = len(tools)
                        mcp_test_result = f"SUCCESS ({mcp_tools_count} tools)"
                except Exception as e:
                    mcp_test_result = "EXCEPTION"
                    mcp_error = str(e)
        else:
            oauth2_test_result = "FAILED (token is None)"
    except Exception as e:
        oauth2_test_result = "EXCEPTION"
        oauth2_error = str(e)

    return {
        "gateway_url": os.getenv("GATEWAY_URL", "NOT SET"),
        "workload_name": os.getenv("WORKLOAD_NAME", "NOT SET"),
        "aws_region": os.getenv("AWS_REGION", "NOT SET"),
        "mcp_available": MCP_AVAILABLE,
        "oauth2_provider_name": GATEWAY_OAUTH_PROVIDER_NAME,
        "oauth2_test_result": oauth2_test_result,
        "oauth2_error": oauth2_error,
        "mcp_test_result": mcp_test_result,
        "mcp_tools_count": mcp_tools_count,
        "mcp_error": mcp_error,
        "context_info": context_info,
    }


# ローカル開発用サーバー
if __name__ == "__main__":
    print("Starting Kintai Agent (HTTP) on http://localhost:8080")
    print("Press Ctrl+C to stop")
    app.run(port=8080)
