"""
Kintai Agent Frontend 設定 (A2A版)
"""
import os

# AWS設定
REGION = os.getenv("AWS_REGION", "ap-northeast-1")

# Cognito設定
USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID", "ap-northeast-1_6S5ZldelG")
CLIENT_ID = os.getenv("COGNITO_CLIENT_ID", "2gd77fh8l19dfa5otvoph086nb")

# AgentCore A2A Runtime設定
RUNTIME_ARN = os.getenv(
    "RUNTIME_ARN",
    "arn:aws:bedrock-agentcore:ap-northeast-1:641963215484:runtime/kintai_agent_a2a-Btpf399pqs"
)

# API設定
API_TIMEOUT = int(os.getenv("API_TIMEOUT", "300"))
