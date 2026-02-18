#!/usr/bin/env python3
"""
Google Calendar OAuth2 Credential Provider セットアップスクリプト

このスクリプトは、AgentCore IdentityにGoogle Calendar用のOAuth2 Credential Providerを作成します。
CDKデプロイ前に一度実行してください。

========================================
OAuth2認証フロー（A2A対応）
========================================

このOAuth2設定は、A2Aサーバーとしても利用可能です：

1. 初回のみ: ユーザーがブラウザでGoogleにログインして承認
2. AgentCore IdentityのToken Vaultにアクセストークンとリフレッシュトークンを保存
3. 以降: エージェントが自動的にToken Vaultからトークンを取得
4. トークン期限切れ時: 自動的にリフレッシュトークンで更新
5. A2Aサーバーとして動作: ユーザーIDを指定してトークン取得

利点:
- Google Workspaceの中央管理下でも利用可能
- Service Accountやドメイン全体の委任が不要
- 管理者権限不要（ユーザー自身が承認）
- 複数ユーザーのカレンダーに対応可能（ユーザーIDごとにトークン管理）

========================================
前提条件
========================================

1. Google Cloud Consoleでプロジェクトを作成済み
2. Google Calendar APIを有効化済み
3. OAuth 2.0クライアントIDを作成済み（Webアプリケーション）
4. リダイレクトURIを設定済み: 
   https://bedrock-agentcore.{region}.amazonaws.com/oauth/callback
5. AWS Secrets ManagerにOAuth2シークレットを保存済み
   形式: {"clientId": "xxx", "clientSecret": "yyy"}

========================================
使用方法
========================================

python3 setup-google-calendar-oauth.py \\
    --region us-east-1 \\
    --provider-name google-calendar \\
    --secret-arn arn:aws:secretsmanager:us-east-1:123456789012:secret:kintai-agent-google-calendar-oauth-abc123

========================================
出力
========================================

OAuth2 Credential Provider ARNが表示されます。
このARNをCDKスタックのコメント部分に設定してください。
"""

import argparse
import boto3
import json
import sys
from typing import Dict, Any


def get_secret(secret_arn: str, region: str) -> Dict[str, str]:
    """
    Secrets ManagerからOAuth2シークレットを取得
    
    Args:
        secret_arn: Secrets Manager ARN
        region: AWSリージョン
        
    Returns:
        clientIdとclientSecretを含む辞書
    """
    client = boto3.client('secretsmanager', region_name=region)
    
    try:
        response = client.get_secret_value(SecretId=secret_arn)
        secret = json.loads(response['SecretString'])
        
        if 'clientId' not in secret or 'clientSecret' not in secret:
            raise ValueError("Secret must contain 'clientId' and 'clientSecret' keys")
        
        return secret
    except Exception as e:
        print(f"Error retrieving secret: {e}", file=sys.stderr)
        sys.exit(1)


def create_oauth2_provider(
    region: str,
    provider_name: str,
    client_id: str,
    client_secret: str
) -> str:
    """
    OAuth2 Credential Providerを作成
    
    このProviderは以下の機能を提供：
    - 初回: ユーザーがブラウザで承認
    - Token Vaultにアクセストークンとリフレッシュトークンを保存
    - 以降: 自動的にトークンを取得・リフレッシュ
    - A2Aサーバーとして動作可能（ユーザーIDを指定）
    
    Args:
        region: AWSリージョン
        provider_name: Provider名
        client_id: Google OAuth2 Client ID
        client_secret: Google OAuth2 Client Secret
        
    Returns:
        作成されたProvider ARN
    """
    # 注: bedrock_agentcore SDKはまだ正式リリースされていないため、
    # boto3のbedrock-agentcore APIを使用します
    client = boto3.client('bedrock-agentcore', region_name=region)
    
    try:
        # Google用のOAuth2 Credential Providerを作成
        response = client.create_oauth2_credential_provider(
            credentialProviderName=provider_name,
            provider='GOOGLE',  # ビルトインプロバイダー
            clientId=client_id,
            clientSecret=client_secret,
            scopes=[
                'https://www.googleapis.com/auth/calendar.readonly'
            ]
        )
        
        provider_arn = response['credentialProviderArn']
        print(f"✓ OAuth2 Credential Provider created successfully!")
        print(f"  ARN: {provider_arn}")
        print(f"  Type: OAuth2 with Token Vault (A2A compatible)")
        print(f"  Scopes: calendar.readonly")
        
        return provider_arn
        
    except client.exceptions.ConflictException:
        print(f"✓ OAuth2 Credential Provider '{provider_name}' already exists")
        # 既存のProviderを取得
        response = client.get_oauth2_credential_provider(
            credentialProviderName=provider_name
        )
        provider_arn = response['credentialProviderArn']
        print(f"  ARN: {provider_arn}")
        return provider_arn
        
    except Exception as e:
        print(f"Error creating OAuth2 provider: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description='Setup Google Calendar OAuth2 Credential Provider for AgentCore Identity (A2A compatible)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
  python3 setup-google-calendar-oauth.py \\
      --region us-east-1 \\
      --provider-name google-calendar \\
      --secret-arn arn:aws:secretsmanager:...:secret:oauth-credentials

Note:
  This OAuth2 setup works for A2A servers:
  - Initial user authorization via browser (one-time)
  - Tokens stored in AgentCore Identity Token Vault
  - Automatic token refresh
  - Agent can access tokens by user ID
        """
    )
    parser.add_argument(
        '--region',
        required=True,
        help='AWS region (e.g., us-east-1)'
    )
    parser.add_argument(
        '--provider-name',
        default='google-calendar',
        help='OAuth2 Credential Provider name (default: google-calendar)'
    )
    parser.add_argument(
        '--secret-arn',
        required=True,
        help='AWS Secrets Manager ARN containing clientId and clientSecret'
    )
    
    args = parser.parse_args()
    
    print(f"Setting up Google Calendar OAuth2 Credential Provider...")
    print(f"  Region: {args.region}")
    print(f"  Provider Name: {args.provider_name}")
    print(f"  Secret ARN: {args.secret_arn}")
    print()
    
    # Secretを取得
    print("Retrieving OAuth2 credentials from Secrets Manager...")
    secret = get_secret(args.secret_arn, args.region)
    print("✓ Credentials retrieved successfully")
    print()
    
    # OAuth2 Providerを作成
    print("Creating OAuth2 Credential Provider...")
    provider_arn = create_oauth2_provider(
        region=args.region,
        provider_name=args.provider_name,
        client_id=secret['clientId'],
        client_secret=secret['clientSecret']
    )
    print()
    
    # 次のステップを表示
    print("=" * 80)
    print("Next Steps:")
    print("=" * 80)
    print()
    print("OAuth2 Setup (A2A Compatible):")
    print("  ✓ No Service Account or Domain-Wide Delegation required")
    print("  ✓ Works with centrally managed Google Workspace accounts")
    print("  ✓ Users authorize once, then agent works automatically")
    print("  ✓ Tokens stored securely in AgentCore Identity Token Vault")
    print("  ✓ Automatic token refresh")
    print()
    print("1. Update cdk/lib/kintai-agent-stack.ts:")
    print(f"   - Uncomment the Google Calendar MCP Server Target section")
    print(f"   - Set googleCalendarOAuthArn = '{provider_arn}'")
    print(f"   - Set googleCalendarSecretArn = '{args.secret_arn}'")
    print(f"   - Use GatewayCredentialProvider.fromOauthIdentityArn(...)")
    print()
    print("2. Deploy CDK stack:")
    print("   cd cdk && npm run build && cdk deploy")
    print()
    print("3. Initial user authorization (one-time per user):")
    print("   - User accesses the agent via Streamlit UI")
    print("   - Agent requests calendar access")
    print("   - User authorizes via Google OAuth consent screen")
    print("   - Token stored in Token Vault")
    print()
    print("4. Subsequent usage (A2A mode):")
    print("   - Agent automatically retrieves token from Token Vault")
    print("   - No user interaction required")
    print("   - Works as A2A server")
    print()


if __name__ == '__main__':
    main()
