"""
Kintai Agent Frontend 設定
"""
import os

# AWS設定
REGION = os.getenv("AWS_REGION", "us-east-1")

# Cognito設定
# USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID", "us-east-1_5ckVm3MF7")
# CLIENT_ID = os.getenv("COGNITO_CLIENT_ID", "3ggcb40g1f8svavtd8n2m4dqfn")
USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID", "us-east-1_R8D0VLFRU")
CLIENT_ID = os.getenv("COGNITO_CLIENT_ID", "36h6j4qe20ljlaj6a6pdk21d58i")

# AgentCore Runtime設定
# RUNTIME_ARN = os.getenv(
#     "RUNTIME_ARN",
#     "arn:aws:bedrock-agentcore:us-east-1:605664253368:runtime/kintai_agent-ugu56RD1EL"
# )
RUNTIME_ARN = os.getenv(
    "RUNTIME_ARN",
    "arn:aws:bedrock-agentcore:us-east-1:641963215484:runtime/kintai_agent_a2a"
)

# API設定
API_TIMEOUT = int(os.getenv("API_TIMEOUT", "120"))
