#!/bin/bash
# =============================================================================
# AgentCore Identity M2M Credential Provider セットアップスクリプト
# =============================================================================
#
# 使用方法:
#   ./setup-m2m-credential-provider.sh --profile <AWS_PROFILE> [--region <REGION>]
#
# 前提条件:
#   - CDKスタックがデプロイ済みであること
#   - AWS CLIがインストール・設定済みであること
#
# =============================================================================

set -e

# デフォルト値
REGION="us-east-1"
STACK_NAME="KintaiAgentStack"
PROVIDER_NAME="kintai-gateway-m2m"

# 引数のパース
while [[ $# -gt 0 ]]; do
  case $1 in
    --profile)
      AWS_PROFILE="$2"
      shift 2
      ;;
    --region)
      REGION="$2"
      shift 2
      ;;
    --stack-name)
      STACK_NAME="$2"
      shift 2
      ;;
    --help)
      echo "Usage: $0 --profile <AWS_PROFILE> [--region <REGION>] [--stack-name <STACK_NAME>]"
      echo ""
      echo "Options:"
      echo "  --profile     AWS profile name (required)"
      echo "  --region      AWS region (default: us-east-1)"
      echo "  --stack-name  CloudFormation stack name (default: KintaiAgentStack)"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# プロファイルのチェック
if [ -z "$AWS_PROFILE" ]; then
  echo "❌ Error: --profile is required"
  echo "Usage: $0 --profile <AWS_PROFILE>"
  exit 1
fi

echo "=============================================="
echo "AgentCore M2M Credential Provider Setup"
echo "=============================================="
echo "Profile: $AWS_PROFILE"
echo "Region: $REGION"
echo "Stack: $STACK_NAME"
echo ""

# Step 1: CloudFormation出力から必要な情報を取得
echo "📥 Step 1: Getting CloudFormation outputs..."

get_output() {
  aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" \
    --output text \
    --region "$REGION" \
    --profile "$AWS_PROFILE"
}

USER_POOL_ID=$(get_output "UserPoolId")
M2M_CLIENT_ID=$(get_output "M2MClientId")
COGNITO_DOMAIN=$(get_output "CognitoDomain")

if [ -z "$USER_POOL_ID" ] || [ -z "$M2M_CLIENT_ID" ] || [ -z "$COGNITO_DOMAIN" ]; then
  echo "❌ Error: Could not get required outputs from CloudFormation stack"
  echo "  USER_POOL_ID: $USER_POOL_ID"
  echo "  M2M_CLIENT_ID: $M2M_CLIENT_ID"
  echo "  COGNITO_DOMAIN: $COGNITO_DOMAIN"
  exit 1
fi

echo "  User Pool ID: $USER_POOL_ID"
echo "  M2M Client ID: $M2M_CLIENT_ID"
echo "  Cognito Domain: $COGNITO_DOMAIN"
echo ""

# Step 2: M2Mクライアントシークレットを取得
echo "🔐 Step 2: Getting M2M client secret..."

CLIENT_SECRET=$(aws cognito-idp describe-user-pool-client \
  --user-pool-id "$USER_POOL_ID" \
  --client-id "$M2M_CLIENT_ID" \
  --query "UserPoolClient.ClientSecret" \
  --output text \
  --region "$REGION" \
  --profile "$AWS_PROFILE")

if [ -z "$CLIENT_SECRET" ] || [ "$CLIENT_SECRET" == "None" ]; then
  echo "❌ Error: Could not get client secret"
  exit 1
fi

echo "  Client secret retrieved (length: ${#CLIENT_SECRET})"
echo ""

# Step 3: 既存のCredential Providerをチェック
echo "🔍 Step 3: Checking for existing credential provider..."

EXISTING_PROVIDER=$(aws bedrock-agentcore-control get-oauth2-credential-provider \
  --name "$PROVIDER_NAME" \
  --region "$REGION" \
  --profile "$AWS_PROFILE" 2>/dev/null || echo "")

if [ -n "$EXISTING_PROVIDER" ]; then
  echo "  ⚠️  Credential provider '$PROVIDER_NAME' already exists."
  read -p "  Do you want to update it? (y/N): " CONFIRM
  if [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ]; then
    echo "  Skipping credential provider creation."
    exit 0
  fi

  # 既存のプロバイダーを削除
  echo "  Deleting existing provider..."
  aws bedrock-agentcore-control delete-oauth2-credential-provider \
    --name "$PROVIDER_NAME" \
    --region "$REGION" \
    --profile "$AWS_PROFILE"

  # 削除が完了するまで少し待つ
  sleep 3
fi

# Step 4: Credential Providerを作成
echo "🚀 Step 4: Creating OAuth2 Credential Provider..."

# 新しいAPI形式: --credential-provider-vendor と --oauth2-provider-config-input を使用
# clientSecret は config 内に含める
OAUTH2_CONFIG=$(cat <<EOF
{
  "customOauth2ProviderConfig": {
    "oauthDiscovery": {
      "authorizationServerMetadata": {
        "issuer": "https://cognito-idp.${REGION}.amazonaws.com/${USER_POOL_ID}",
        "authorizationEndpoint": "${COGNITO_DOMAIN}/oauth2/authorize",
        "tokenEndpoint": "${COGNITO_DOMAIN}/oauth2/token",
        "tokenEndpointAuthMethods": ["client_secret_post"]
      }
    },
    "clientId": "${M2M_CLIENT_ID}",
    "clientSecret": "${CLIENT_SECRET}"
  }
}
EOF
)

RESULT=$(aws bedrock-agentcore-control create-oauth2-credential-provider \
  --name "$PROVIDER_NAME" \
  --credential-provider-vendor "CustomOauth2" \
  --oauth2-provider-config-input "$OAUTH2_CONFIG" \
  --region "$REGION" \
  --profile "$AWS_PROFILE" 2>&1)

if [ $? -eq 0 ]; then
  echo "✅ Credential Provider created successfully!"
  echo ""
  echo "=============================================="
  echo "Setup Complete!"
  echo "=============================================="
  echo ""
  echo "Credential Provider ARN:"
  echo "  arn:aws:bedrock-agentcore:${REGION}:$(aws sts get-caller-identity --profile $AWS_PROFILE --query Account --output text):token-vault/default/oauth2credentialprovider/${PROVIDER_NAME}"
  echo ""
  echo "Next steps:"
  echo "  1. Update frontend_a2a/config.py with the new account settings"
  echo "  2. Create Cognito user for testing"
  echo "  3. Test the agent"
else
  echo "❌ Error creating credential provider:"
  echo "$RESULT"
  exit 1
fi
