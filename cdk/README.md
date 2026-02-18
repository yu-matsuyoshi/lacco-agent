# Kintai Agent CDK

このディレクトリには、Kintai AgentをAWS AgentCore Runtimeにデプロイするためのインフラストラクチャコード（TypeScript）が含まれています。

## 前提条件

- AWS CLI設定済み
- Node.js 18以上
- AWS CDK CLI インストール済み (`npm install -g aws-cdk`)

## セットアップ

1. 依存関係をインストール:
```bash
cd cdk
npm install
```

2. TypeScriptをビルド:
```bash
npm run build
```

3. CDKをブートストラップ（初回のみ）:
```bash
cdk bootstrap
```

## デプロイ

```bash
cdk deploy
```

## スタック構成

- **S3 Bucket**: マスタデータ（CSV）の保存
- **Lambda Functions**: ツール実装（get_projects、get_categories、validate_percentage）
- **AgentCore Gateway**: ツールとMCPサーバーの統合
- **AgentCore Runtime**: Strands Agentのホスティング

## 開発

TypeScriptをウォッチモードでビルド:
```bash
npm run watch
```

スタックの差分を確認:
```bash
cdk diff
```

CloudFormationテンプレートを生成:
```bash
cdk synth
```

## クリーンアップ

```bash
cdk destroy
```
