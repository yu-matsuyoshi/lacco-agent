import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as s3deploy from 'aws-cdk-lib/aws-s3-deployment';
import * as s3assets from 'aws-cdk-lib/aws-s3-assets';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as lambdaNodejs from 'aws-cdk-lib/aws-lambda-nodejs';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as path from 'path';
import * as agentcore from '@aws-cdk/aws-bedrock-agentcore-alpha';

export class KintaiAgentStack extends cdk.Stack {
  public readonly dataBucket: s3.Bucket;
  public readonly tokenCacheTable: dynamodb.Table;
  public readonly getProjectsFn: lambdaNodejs.NodejsFunction;
  public readonly getCategoriesFn: lambdaNodejs.NodejsFunction;
  public readonly validatePercentageFn: lambdaNodejs.NodejsFunction;
  public readonly userPool: cognito.UserPool;
  public readonly userPoolClient: cognito.UserPoolClient;
  public readonly gateway: agentcore.Gateway;
  public readonly runtime: agentcore.Runtime;
  public readonly runtimeA2A: agentcore.Runtime;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // S3バケット - マスタデータ保存用
    this.dataBucket = new s3.Bucket(this, 'DataBucket', {
      bucketName: `kintai-agent-data-v2-${this.account}-${this.region}`,
      removalPolicy: cdk.RemovalPolicy.DESTROY, // 開発用。本番環境ではRETAINに変更
      autoDeleteObjects: true, // 開発用。本番環境ではfalseに変更
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      versioned: false,
    });

    // マスタデータ（CSV）をS3にデプロイ
    new s3deploy.BucketDeployment(this, 'DeployMasterData', {
      sources: [s3deploy.Source.asset(path.join(__dirname, '../../data'))],
      destinationBucket: this.dataBucket,
      destinationKeyPrefix: 'master-data/',
      prune: false, // 既存ファイルを削除しない
    });

    // DynamoDB テーブル - M2Mトークンキャッシュ用
    // 全コンテナでトークンを共有し、Cognitoへのリクエスト数を削減
    this.tokenCacheTable = new dynamodb.Table(this, 'TokenCacheTable', {
      tableName: `kintai-agent-token-cache-${this.account}-${this.region}`,
      partitionKey: {
        name: 'cache_key',
        type: dynamodb.AttributeType.STRING,
      },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,  // オンデマンド（低コスト）
      removalPolicy: cdk.RemovalPolicy.DESTROY,  // 開発用
      timeToLiveAttribute: 'ttl',  // 自動削除用TTL
    });

    // Lambda関数 - get_projects
    this.getProjectsFn = new lambdaNodejs.NodejsFunction(this, 'GetProjectsFunction', {
      functionName: 'kintai-agent-get-projects',
      runtime: lambda.Runtime.NODEJS_20_X,
      handler: 'handler',
      entry: path.join(__dirname, '../lambda/get_projects/index.ts'),
      timeout: cdk.Duration.seconds(30),
      memorySize: 256,
      environment: {
        DATA_BUCKET: this.dataBucket.bucketName,
      },
      bundling: {
        minify: true,
        sourceMap: true,
      },
    });

    // S3読み込み権限を付与
    this.dataBucket.grantRead(this.getProjectsFn);

    // Lambda関数 - get_categories
    this.getCategoriesFn = new lambdaNodejs.NodejsFunction(this, 'GetCategoriesFunction', {
      functionName: 'kintai-agent-get-categories',
      runtime: lambda.Runtime.NODEJS_20_X,
      handler: 'handler',
      entry: path.join(__dirname, '../lambda/get_categories/index.ts'),
      timeout: cdk.Duration.seconds(30),
      memorySize: 256,
      environment: {
        DATA_BUCKET: this.dataBucket.bucketName,
      },
      bundling: {
        minify: true,
        sourceMap: true,
      },
    });

    // S3読み込み権限を付与
    this.dataBucket.grantRead(this.getCategoriesFn);

    // Lambda関数 - validate_percentage
    this.validatePercentageFn = new lambdaNodejs.NodejsFunction(this, 'ValidatePercentageFunction', {
      functionName: 'kintai-agent-validate-percentage',
      runtime: lambda.Runtime.NODEJS_20_X,
      handler: 'handler',
      entry: path.join(__dirname, '../lambda/validate_percentage/index.ts'),
      timeout: cdk.Duration.seconds(30),
      memorySize: 256,
      bundling: {
        minify: true,
        sourceMap: true,
      },
    });

    // Cognito User Pool - ユーザー認証用
    this.userPool = new cognito.UserPool(this, 'KintaiUserPool', {
      userPoolName: 'kintai-agent-users',
      selfSignUpEnabled: true,  // セルフサインアップを有効化
      signInAliases: {
        email: true,  // メールアドレスでログイン
        username: true,  // ユーザー名でもログイン可能
      },
      autoVerify: {
        email: true,  // メールアドレスを自動検証
      },
      standardAttributes: {
        email: {
          required: true,
          mutable: true,
        },
        fullname: {
          required: false,
          mutable: true,
        },
      },
      passwordPolicy: {
        minLength: 8,
        requireLowercase: true,
        requireUppercase: true,
        requireDigits: true,
        requireSymbols: false,
      },
      accountRecovery: cognito.AccountRecovery.EMAIL_ONLY,
      removalPolicy: cdk.RemovalPolicy.DESTROY,  // 開発用。本番環境ではRETAINに変更
    });

    // Cognito User Pool Client - Streamlit UI用
    this.userPoolClient = new cognito.UserPoolClient(this, 'KintaiUserPoolClient', {
      userPool: this.userPool,
      userPoolClientName: 'kintai-streamlit-client',
      authFlows: {
        userPassword: true,  // ユーザー名/パスワード認証
        userSrp: true,  // SRP（Secure Remote Password）認証
      },
      generateSecret: false,  // クライアントシークレット不要（パブリッククライアント）
      preventUserExistenceErrors: true,
      refreshTokenValidity: cdk.Duration.days(30),
      accessTokenValidity: cdk.Duration.hours(1),
      idTokenValidity: cdk.Duration.hours(1),
    });

    // Cognito User Pool Domain - M2Mトークンエンドポイント用
    // リージョンコードを追加してマルチリージョンデプロイをサポート
    const regionCode = this.region.replace(/-/g, '').substring(0, 6); // e.g., "apnort" or "useast"
    const userPoolDomain = this.userPool.addDomain('KintaiUserPoolDomain', {
      cognitoDomain: {
        domainPrefix: `kintai-agent-${this.account}-${regionCode}`,
      },
    });

    // Resource Server - Gateway用スコープ定義
    const gatewayResourceServer = this.userPool.addResourceServer('GatewayResourceServer', {
      identifier: 'gateway',
      scopes: [
        { scopeName: 'invoke', scopeDescription: 'Invoke Gateway MCP tools' },
      ],
    });

    // M2M用クライアント - Runtime→Gateway認証用
    const m2mClient = new cognito.UserPoolClient(this, 'KintaiM2MClient', {
      userPool: this.userPool,
      userPoolClientName: 'kintai-gateway-m2m',
      generateSecret: true,  // M2Mにはクライアントシークレット必要
      oAuth: {
        flows: {
          clientCredentials: true,  // M2M認証フロー
        },
        scopes: [
          cognito.OAuthScope.custom('gateway/invoke'),
        ],
      },
    });
    // Resource Serverへの依存関係を追加
    m2mClient.node.addDependency(gatewayResourceServer);

    // AgentCore Gateway - ツールとMCPサーバーの統合（Cognito認証）
    this.gateway = new agentcore.Gateway(this, 'KintaiGateway', {
      gatewayName: 'kintai-gateway',
      description: 'Gateway for Kintai Agent tools and MCP servers',
      protocolConfiguration: new agentcore.McpProtocolConfiguration({
        instructions: 'Use these tools to access project/category data, validate percentages, and access Google Calendar',
      }),
      authorizerConfiguration: agentcore.GatewayAuthorizer.usingCognito({
        userPool: this.userPool,
        allowedClients: [this.userPoolClient, m2mClient],  // M2Mクライアントも許可
      }),
    });

    // Lambda Target - get_projects
    this.gateway.addLambdaTarget('GetProjectsTarget', {
      gatewayTargetName: 'get-projects',
      description: 'Get all available projects from S3',
      lambdaFunction: this.getProjectsFn,
      toolSchema: agentcore.ToolSchema.fromInline([
        {
          name: 'get_projects',
          description: 'Get all available projects with their IDs and names',
          inputSchema: {
            type: agentcore.SchemaDefinitionType.OBJECT,
            properties: {},
          },
        },
      ]),
    });

    // Lambda Target - get_categories
    this.gateway.addLambdaTarget('GetCategoriesTarget', {
      gatewayTargetName: 'get-categories',
      description: 'Get all available categories from S3',
      lambdaFunction: this.getCategoriesFn,
      toolSchema: agentcore.ToolSchema.fromInline([
        {
          name: 'get_categories',
          description: 'Get all available work categories with their IDs and names',
          inputSchema: {
            type: agentcore.SchemaDefinitionType.OBJECT,
            properties: {},
          },
        },
      ]),
    });

    // Lambda Target - validate_percentage
    this.gateway.addLambdaTarget('ValidatePercentageTarget', {
      gatewayTargetName: 'validate-percentage',
      description: 'Validate that work entry percentages sum to 100',
      lambdaFunction: this.validatePercentageFn,
      toolSchema: agentcore.ToolSchema.fromInline([
        {
          name: 'validate_percentage',
          description: 'Validate that the sum of work entry percentages equals 100%',
          inputSchema: {
            type: agentcore.SchemaDefinitionType.OBJECT,
            properties: {
              entries: {
                type: agentcore.SchemaDefinitionType.ARRAY,
                description: 'Array of work entries to validate',
                items: {
                  type: agentcore.SchemaDefinitionType.OBJECT,
                  properties: {
                    date: { type: agentcore.SchemaDefinitionType.STRING },
                    project_id: { type: agentcore.SchemaDefinitionType.NUMBER },
                    project_name: { type: agentcore.SchemaDefinitionType.STRING },
                    category_id: { type: agentcore.SchemaDefinitionType.NUMBER },
                    category_name: { type: agentcore.SchemaDefinitionType.STRING },
                    percentage: { type: agentcore.SchemaDefinitionType.NUMBER },
                  },
                },
              },
            },
            required: ['entries'],
          },
        },
      ]),
    });

    // MCP Server Target - Google Calendar
    // 
    // 注意: AgentCore IdentityのL2 Constructは現時点で利用不可のため、
    // OAuth2 Credential Providerは以下のいずれかの方法で事前に作成する必要があります：
    // 
    // 方法1: AWSコンソールで手動作成
    //   - AgentCore Identity コンソール → Credential Providers → Create
    //   - Provider type: OAuth2
    //   - Provider: Google
    //   - Scopes: https://www.googleapis.com/auth/calendar.readonly
    // 
    // 方法2: Python SDKで作成（scripts/setup_google_calendar_oauth.py参照）
    //   - bedrock_agentcore.identity.IdentityClient を使用
    // 
    // 方法3: CDK L1 Constructで作成（将来的にL2が利用可能になるまでの暫定対応）
    //   - new agentcore.CfnOAuth2CredentialProvider(...)
    // 
    // 設定手順:
    // 1. Google Cloud Consoleでプロジェクトを作成
    // 2. Google Calendar APIを有効化
    // 3. OAuth 2.0クライアントIDを作成（Webアプリケーション）
    // 4. リダイレクトURIを設定: https://bedrock-agentcore.{region}.amazonaws.com/oauth/callback
    // 5. クライアントIDとシークレットを取得
    // 6. AWS Secrets ManagerにOAuth2シークレットを保存
    // 7. 上記いずれかの方法でOAuth2 Credential Providerを作成
    // 8. 作成されたCredential Provider ARNを以下のコードに設定
    // 
    // OAuth2 Credential Providerを作成後、以下のコメントを解除してARNを設定してください
    
    /*
    // Google Calendar OAuth2 Credential Provider ARN（事前に作成したもの）
    const googleCalendarOAuthArn = 'arn:aws:bedrock-agentcore:us-east-1:123456789012:token-vault/abc123/oauth2credentialprovider/google-calendar';
    const googleCalendarSecretArn = 'arn:aws:secretsmanager:us-east-1:123456789012:secret:kintai-agent-google-calendar-oauth-abc123';
    
    // MCP Server Targetを追加
    // 注: MCP Server URLは実際のデプロイ先に応じて変更してください
    // 例: AgentCore Runtimeにデプロイした場合は、そのRuntime URLを指定
    this.gateway.addMcpServerTarget('GoogleCalendarTarget', {
      gatewayTargetName: 'google-calendar',
      description: 'Google Calendar MCP server for event retrieval',
      url: 'https://your-mcp-server-url.com',  // 実際のMCPサーバーURL
      path: '/mcp',
      credentialProviderConfigurations: [
        agentcore.GatewayCredentialProvider.fromOauthIdentityArn(
          googleCalendarOAuthArn,
          googleCalendarSecretArn
        ),
      ],
    });
    */

    // ========================================================================
    // AgentCore Memory - 会話履歴の永続化
    // ========================================================================
    const memory = new agentcore.Memory(this, 'KintaiMemory', {
      memoryName: 'kintai_memory',
      description: 'Memory for Kintai Agent conversation history',
      memoryStrategies: [
        agentcore.MemoryStrategy.usingBuiltInSummarization(),
      ],
    });

    // AgentCore Runtime - Strands Agentのホスティング（ECRベースのデプロイ）
    // DockerイメージをビルドしてECRにプッシュ
    this.runtime = new agentcore.Runtime(this, 'KintaiRuntimeV2', {
      runtimeName: 'kintai_agent',  // ハイフンではなくアンダースコアを使用
      description: 'Kintai Agent Runtime for work hours management',
      agentRuntimeArtifact: agentcore.AgentRuntimeArtifact.fromAsset(
        path.join(__dirname, '../../kintai_agent'),
        {
          platform: cdk.aws_ecr_assets.Platform.LINUX_ARM64,  // AgentCore RuntimeはARM64を使用
        }
      ),
      networkConfiguration: agentcore.RuntimeNetworkConfiguration.usingPublicNetwork(),
      // === 認証設定 ===
      // Cognito認証（Access Token使用）
      // 共通A2Aクライアント対応時は、CDKコンテキストで共通Cognitoを参照可能
      // npx cdk deploy -c sharedUserPoolId=xxx -c sharedUserPoolClientId=yyy
      authorizerConfiguration: agentcore.RuntimeAuthorizerConfiguration.usingCognito(
        this.userPool,
        [this.userPoolClient]
      ),
      environmentVariables: {
        GATEWAY_URL: `https://${this.gateway.gatewayId}.gateway.bedrock-agentcore.${this.region}.amazonaws.com/mcp`,
        WORKLOAD_NAME: 'kintai_agent',  // ハイフンではなくアンダースコアを使用
        // ACCESS_TOKEN: AgentCore Runtimeが自動的に環境変数として設定
        DATA_BUCKET: this.dataBucket.bucketName,
        TOKEN_CACHE_TABLE: this.tokenCacheTable.tableName,
        AWS_REGION: this.region,
        MODEL_ID: 'jp.anthropic.claude-sonnet-4-6',
        // Force update timestamp
        DEPLOY_VERSION: '2026-04-01-ap-northeast-1',
      },
    });

    // Gateway読み込み権限を付与
    this.gateway.grantRead(this.runtime);

    // DynamoDBトークンキャッシュテーブルへの読み書き権限を付与
    this.tokenCacheTable.grantReadWriteData(this.runtime);

    // ========================================================================
    // AgentCore Runtime - A2Aプロトコル版（並行デプロイ）
    // ========================================================================

    // 共通A2Aクライアントの Cognito 設定
    // CDK context で上書き可能: npx cdk deploy -c sharedUserPoolId=xxx -c sharedClientId=yyy
    const sharedUserPoolId = this.node.tryGetContext('sharedUserPoolId') || 'ap-northeast-1_GrRuadOKV';
    const sharedClientId = this.node.tryGetContext('sharedClientId') || '4jbkr530emk6vbn1blv71llplv';

    this.runtimeA2A = new agentcore.Runtime(this, 'KintaiRuntimeA2A', {
      runtimeName: 'kintai_agent_a2a',
      description: 'Kintai Agent Runtime (A2A Protocol) for work hours management',
      agentRuntimeArtifact: agentcore.AgentRuntimeArtifact.fromAsset(
        path.join(__dirname, '../../kintai_agent'),
        {
          platform: cdk.aws_ecr_assets.Platform.LINUX_ARM64,
          file: 'Dockerfile.a2a',  // A2A用Dockerfile
        }
      ),
      networkConfiguration: agentcore.RuntimeNetworkConfiguration.usingPublicNetwork(),
      // === 認証設定 ===
      // 共通A2Aクライアントの Cognito JWT を検証
      authorizerConfiguration: agentcore.RuntimeAuthorizerConfiguration.usingJWT(
        `https://cognito-idp.${this.region}.amazonaws.com/${sharedUserPoolId}/.well-known/openid-configuration`,
        [sharedClientId],  // allowedClients (Access Token の client_id クレームを検証)
      ),
      // 自前Cognito認証に戻す場合は以下を使用:
      // authorizerConfiguration: agentcore.RuntimeAuthorizerConfiguration.usingCognito(
      //   this.userPool,
      //   [this.userPoolClient]
      // ),
      protocolConfiguration: agentcore.ProtocolType.A2A,  // A2Aプロトコル
      environmentVariables: {
        GATEWAY_URL: `https://${this.gateway.gatewayId}.gateway.bedrock-agentcore.${this.region}.amazonaws.com/mcp`,
        WORKLOAD_NAME: 'kintai_agent_a2a',
        DATA_BUCKET: this.dataBucket.bucketName,
        TOKEN_CACHE_TABLE: this.tokenCacheTable.tableName,
        AWS_REGION: this.region,
        MODEL_ID: 'jp.anthropic.claude-sonnet-4-6',
        AGENTCORE_MEMORY_ID: memory.memoryId,  // Memory統合
        DEPLOY_VERSION: '2026-04-01-ap-northeast-1',
      },
    });
    // Note: AGENTCORE_RUNTIME_URLはAgentCoreが自動的にコンテナに提供する

    // A2A Runtime: Gateway読み込み権限を付与
    this.gateway.grantRead(this.runtimeA2A);

    // A2A Runtime: Memory読み書き権限を付与
    memory.grantWrite(this.runtimeA2A);
    memory.grantRead(this.runtimeA2A);

    // A2A Runtime: DynamoDBトークンキャッシュテーブルへの読み書き権限を付与
    this.tokenCacheTable.grantReadWriteData(this.runtimeA2A);

    // M2M OAuth2フロー用のIdentity権限を付与
    this.runtime.grantPrincipal.addToPrincipalPolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: [
        'bedrock-agentcore:GetResourceOauth2Token',
        'bedrock-agentcore:GetWorkloadAccessToken',
        'bedrock-agentcore:GetWorkloadAccessTokenForJWT',
        'bedrock-agentcore:GetWorkloadAccessTokenForUserId',
        'bedrock-agentcore:CreateWorkloadIdentity',
      ],
      resources: [
        `arn:aws:bedrock-agentcore:${this.region}:${this.account}:token-vault/*`,
        `arn:aws:bedrock-agentcore:${this.region}:${this.account}:workload-identity-directory/*`,
      ],
    }));

    // Secrets Manager権限（Credential Provider用）
    this.runtime.grantPrincipal.addToPrincipalPolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: [
        'secretsmanager:GetSecretValue',
      ],
      resources: [
        `arn:aws:secretsmanager:${this.region}:${this.account}:secret:bedrock-agentcore-identity*`,
      ],
    }));

    // Bedrockモデル呼び出し権限を付与（クロスリージョン対応）
    this.runtime.grantPrincipal.addToPrincipalPolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: [
        'bedrock:InvokeModel',
        'bedrock:InvokeModelWithResponseStream',
      ],
      resources: [
        'arn:aws:bedrock:*::foundation-model/*',
        `arn:aws:bedrock:*:${this.account}:inference-profile/*`,
      ],
    }));

    // ========================================================================
    // A2A Runtime用の権限設定
    // ========================================================================

    // A2A Runtime: M2M OAuth2フロー用のIdentity権限を付与
    this.runtimeA2A.grantPrincipal.addToPrincipalPolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: [
        'bedrock-agentcore:GetResourceOauth2Token',
        'bedrock-agentcore:GetWorkloadAccessToken',
        'bedrock-agentcore:GetWorkloadAccessTokenForJWT',
        'bedrock-agentcore:GetWorkloadAccessTokenForUserId',
        'bedrock-agentcore:CreateWorkloadIdentity',
      ],
      resources: [
        `arn:aws:bedrock-agentcore:${this.region}:${this.account}:token-vault/*`,
        `arn:aws:bedrock-agentcore:${this.region}:${this.account}:workload-identity-directory/*`,
      ],
    }));

    // A2A Runtime: Secrets Manager権限（Credential Provider用）
    this.runtimeA2A.grantPrincipal.addToPrincipalPolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: [
        'secretsmanager:GetSecretValue',
      ],
      resources: [
        `arn:aws:secretsmanager:${this.region}:${this.account}:secret:bedrock-agentcore-identity*`,
      ],
    }));

    // A2A Runtime: Bedrockモデル呼び出し権限を付与（クロスリージョン対応）
    this.runtimeA2A.grantPrincipal.addToPrincipalPolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: [
        'bedrock:InvokeModel',
        'bedrock:InvokeModelWithResponseStream',
      ],
      resources: [
        'arn:aws:bedrock:*::foundation-model/*',
        `arn:aws:bedrock:*:${this.account}:inference-profile/*`,
      ],
    }))

    // Outputs
    new cdk.CfnOutput(this, 'DataBucketName', {
      value: this.dataBucket.bucketName,
      description: 'S3 bucket name for master data',
      exportName: `${this.stackName}-DataBucketName`,
    });

    new cdk.CfnOutput(this, 'DataBucketArn', {
      value: this.dataBucket.bucketArn,
      description: 'S3 bucket ARN for master data',
      exportName: `${this.stackName}-DataBucketArn`,
    });

    new cdk.CfnOutput(this, 'GetProjectsFunctionArn', {
      value: this.getProjectsFn.functionArn,
      description: 'Get Projects Lambda function ARN',
      exportName: `${this.stackName}-GetProjectsFunctionArn`,
    });

    new cdk.CfnOutput(this, 'GetCategoriesFunctionArn', {
      value: this.getCategoriesFn.functionArn,
      description: 'Get Categories Lambda function ARN',
      exportName: `${this.stackName}-GetCategoriesFunctionArn`,
    });

    new cdk.CfnOutput(this, 'ValidatePercentageFunctionArn', {
      value: this.validatePercentageFn.functionArn,
      description: 'Validate Percentage Lambda function ARN',
      exportName: `${this.stackName}-ValidatePercentageFunctionArn`,
    });

    new cdk.CfnOutput(this, 'GatewayArn', {
      value: this.gateway.gatewayArn,
      description: 'AgentCore Gateway ARN',
      exportName: `${this.stackName}-GatewayArn`,
    });

    new cdk.CfnOutput(this, 'GatewayId', {
      value: this.gateway.gatewayId,
      description: 'AgentCore Gateway ID',
      exportName: `${this.stackName}-GatewayId`,
    });

    new cdk.CfnOutput(this, 'UserPoolId', {
      value: this.userPool.userPoolId,
      description: 'Cognito User Pool ID',
      exportName: `${this.stackName}-UserPoolId`,
    });

    new cdk.CfnOutput(this, 'UserPoolClientId', {
      value: this.userPoolClient.userPoolClientId,
      description: 'Cognito User Pool Client ID',
      exportName: `${this.stackName}-UserPoolClientId`,
    });

    new cdk.CfnOutput(this, 'M2MClientId', {
      value: m2mClient.userPoolClientId,
      description: 'M2M Client ID for Gateway authentication',
      exportName: `${this.stackName}-M2MClientId`,
    });

    new cdk.CfnOutput(this, 'CognitoDomain', {
      value: `https://${userPoolDomain.domainName}.auth.${this.region}.amazoncognito.com`,
      description: 'Cognito Domain URL for token endpoint',
      exportName: `${this.stackName}-CognitoDomain`,
    });

    new cdk.CfnOutput(this, 'RuntimeA2AName', {
      value: 'kintai_agent_a2a',
      description: 'A2A Runtime Name',
      exportName: `${this.stackName}-RuntimeA2AName`,
    });

    new cdk.CfnOutput(this, 'TokenCacheTableName', {
      value: this.tokenCacheTable.tableName,
      description: 'DynamoDB table for M2M token cache',
      exportName: `${this.stackName}-TokenCacheTableName`,
    });

    // Note: Runtime ARNはデプロイ後にAWSコンソールまたはCLIで確認してください
    // OAuth2 Credential Providerは手動で作成が必要:
    // aws bedrock-agentcore-control create-oauth2-credential-provider ...
  }
}
