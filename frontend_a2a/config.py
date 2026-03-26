"""
Kintai Agent Frontend 設定 (A2A版)

環境変数で設定してください:
  AWS_REGION: AWSリージョン (デフォルト: ap-northeast-1)
  COGNITO_USER_POOL_ID: Cognito User Pool ID (必須)
  COGNITO_CLIENT_ID: Cognito Client ID (必須)
  RUNTIME_ARN: AgentCore Runtime ARN (必須)
  API_TIMEOUT: APIタイムアウト秒数 (デフォルト: 300)
"""
import os
import sys

# AWS設定
REGION = os.getenv("AWS_REGION", "ap-northeast-1")

# Cognito設定（必須）
USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID")
CLIENT_ID = os.getenv("COGNITO_CLIENT_ID")

# AgentCore A2A Runtime設定（必須）
RUNTIME_ARN = os.getenv("RUNTIME_ARN")

# API設定
API_TIMEOUT = int(os.getenv("API_TIMEOUT", "300"))

# 必須環境変数のチェック
_required = {
    "COGNITO_USER_POOL_ID": USER_POOL_ID,
    "COGNITO_CLIENT_ID": CLIENT_ID,
    "RUNTIME_ARN": RUNTIME_ARN,
}
_missing = [k for k, v in _required.items() if not v]
if _missing:
    print(f"エラー: 以下の環境変数が設定されていません: {', '.join(_missing)}")
    print("例: export COGNITO_USER_POOL_ID=ap-northeast-1_XXXXX")
    sys.exit(1)
