# 実装計画

- [x] 1. プロジェクトセットアップと基本構造
  - プロジェクトディレクトリ構造を作成
  - 依存関係（requirements.txt）を定義
  - 環境変数設定ファイル（.env.example）を作成
  - データディレクトリとサンプルCSVファイルを作成
  - _要件: 9.1, 9.2_

- [x] 2. データモデルとユーティリティの実装
  - データクラス（Project, Category, WorkEntry, CommandResult等）を実装
  - CSVローダーを実装してマスタデータを読み込む
  - _要件: 9.1, 9.2, 9.3, 9.4_

- [x] 3. CDKプロジェクトのセットアップ
  - CDKプロジェクト構造を作成（cdk/）
  - CDK依存関係を定義（requirements.txt）
  - CDKスタッククラスを作成（KintaiAgentStack）
  - _要件: 5.1, 5.2_

- [x] 4. S3バケットとマスタデータのデプロイ
  - CDKでS3バケットを定義
  - マスタデータ（CSV）をS3にアップロードする仕組みを実装
  - バケットポリシーとIAMロールを設定
  - _要件: 5.2, 5.6, 9.1, 9.2_

- [x] 5. Lambda関数の実装（ツール）
  - get_projects Lambda関数を実装（S3からprojects.csvを読み込み）
  - get_categories Lambda関数を実装（S3からcategories.csvを読み込み）
  - validate_percentage Lambda関数を実装
  - Lambda関数のIAMロール（S3読み込み権限）を設定
  - _要件: 5.3, 5.4, 9.3, 9.4_

- [x] 6. AgentCore Gatewayの実装
  - CDKでAgentCore Gatewayを定義
  - Lambda Targetを追加（get_projects、get_categories、validate_percentage）
  - MCP Server Targetを追加（google-calendar）
  - OAuth2認証設定（Google Calendar用）
  - _要件: 5.3, 5.4, 5.7_

- [x] 7. Strands Agentの実装
  - KintaiAgentクラスの基本構造を実装
  - Strands Agents SDKの初期化を実装
  - システムプロンプトを作成
  - Gateway経由でツールを呼び出す設定を実装
  - _要件: 1.1, 5.4_

- [x] 8. 自然言語処理機能の実装
  - generate_from_text()メソッドを実装
  - 日付表現の解析と変換を実装
  - 案件名・区分・割合の抽出を実装
  - LLMを使用した案件マッチングを実装（完全一致、部分一致、LLM推論）
  - LLMを使用した区分推測を実装
  - _要件: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3, 2.4_

- [x] 9. コマンド生成機能の実装
  - CommandGeneratorクラスを実装
  - コマンド形式検証機能を実装
  - 複数コマンド生成機能を実装
  - _要件: 1.5, 10.1, 10.2, 10.4_

- [x] 10. 割合検証機能の実装
  - validate_percentage関数を実装（Lambda内）
  - 合計100%チェックロジックを実装
  - 警告・エラーメッセージ生成を実装
  - 不足分・超過分の提案生成を実装
  - _要件: 3.1, 3.2, 3.3, 3.4, 3.5, 8.4_

- [x] 11. 複雑な自然言語パターンのサポート
  - 基本パターン（「プロジェクトA 50%」）の処理を実装
  - 時間ベース表現（「午前は会議」）の処理を実装
  - 日付範囲（「先週月曜から金曜まで」）の処理を実装
  - 複雑な時間単位表現の処理を実装
  - 曖昧な入力の処理を実装
  - _要件: 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 12. エラーハンドリングの実装
  - 無効入力のエラー処理を実装
  - 低信頼度マッチの警告を実装
  - マッチ失敗時の提案を実装
  - 成功時のステータス返却を実装
  - 統合説明の生成を実装
  - _要件: 8.1, 8.2, 8.3, 8.5, 10.5_

- [x] 13. チェックポイント - 自然言語処理の動作確認
  - すべてのテストが通ることを確認し、問題があればユーザーに質問する

- [x] 14. Google Calendar連携の実装
  - OAuth2 Credential Providerセットアップスクリプトを作成
  - CDKスタックにMCP Server Target設定を追加（コメントアウト状態）
  - _要件: 4.1, 4.2_

- [x] 15. カレンダーイベント分析の実装
  - generate_from_calendar()メソッドを実装
  - イベントタイトルから案件を推測する機能を実装
  - イベントタイトルから区分を推測する機能を実装
  - イベント時間から割合を計算する機能を実装
  - 不足分の提案機能を実装
  - カレンダー分析の説明生成を実装
  - _要件: 4.3, 4.4, 4.5, 4.6, 4.7_

- [ ] 16. AgentCore Runtimeへのデプロイ
- [ ] 16.1 Google Calendar OAuth2設定（オプション・PoC用）
  - 個人のGoogle Cloudアカウントでプロジェクトを作成
  - Google Calendar APIを有効化
  - OAuth 2.0クライアントIDを作成（Webアプリケーション）
  - リダイレクトURI設定: https://bedrock-agentcore.{region}.amazonaws.com/oauth/callback
  - AWS Secrets Managerにclient IDとsecretを保存
  - setup-google-calendar-oauth.pyスクリプトを実行
  - CDKスタックのGoogle Calendar MCP Server Targetセクションのコメントを解除
  - 注: 本番化時は会社のGoogle Workspaceアカウントに切り替え
  - _要件: 4.1, 4.2_

- [x] 16.2 CDKでAgentCore Runtimeを定義
  - CDKでAgentCore Runtimeを定義
  - Strands AgentをRuntimeにデプロイ
  - Gateway接続を設定
  - IAMロール（Gateway呼び出し権限）を設定
  - デプロイされたエージェントの動作確認
  - エージェントARNを記録
  - _要件: 5.1, 5.2, 5.5_

- [ ] 17. Streamlit UIの実装
  - Streamlitアプリの基本構造を実装
  - boto3でAgentCore Runtime APIを呼び出す機能を実装
  - 自然言語入力タブを実装
  - カレンダー連携タブを実装
  - コマンド表示とコピー機能を実装
  - 詳細な推論情報の表示を実装
  - _要件: 6.1, 6.2, 6.3, 6.4, 6.5_

- [ ] 18. 統合とドキュメント作成
  - README.mdを更新（CDKデプロイ手順を追加）
  - 環境変数の説明を追加
  - S3へのマスタデータ配置手順を追加
  - AgentCore Gateway設定ガイドを作成
  - Streamlit UIの使用方法を追加

- [ ] 19. 最終チェックポイント
  - すべての機能が正常に動作することを確認し、問題があればユーザーに質問する

---

## A2Aプロトコル対応（追加実装）

- [x] 20. A2Aプロトコル基盤の実装
  - A2A Runtimeの定義（CDK: `ProtocolType.A2A`）
  - KintaiA2AExecutorクラスの実装（リクエストごとにAgent作成）
  - KintaiA2AServerクラスの実装（カスタムExecutor対応）
  - MCPClient経由でGatewayツールを動的ロード
  - _実装ファイル: kintai_agent/agent_a2a.py_

- [x] 21. A2Aフロントエンドの実装
  - Streamlit UIのA2A対応版を作成
  - A2A ClientでAgentCard取得・メッセージ送信
  - context_idによる会話コンテキスト管理
  - 「新規会話」ボタンでコンテキストリセット機能
  - _実装ファイル: frontend_a2a/app.py_

- [x] 22. AgentCore Memory統合の実装
  - CDKでMemoryリソースを定義（`MemoryStrategy.usingBuiltInSummarization()`）
  - Runtime環境変数にMEMORY_IDを設定
  - `bedrock_agentcore.memory.integrations.strands`を使用
  - AgentCoreMemorySessionManagerでセッション管理
  - context_id（A2Aプロトコル）をsession_idとして使用
  - Agent作成時にsession_manager引数で自動履歴管理
  - _実装ファイル: kintai_agent/agent_a2a.py, cdk/lib/kintai-agent-stack.ts_

- [x] 23. プロジェクト/区分データの整理
  - プロジェクト名を区分名と混同しにくい名前に変更
  - 区分に「その他」（ID: 9）を追加
  - システムプロンプトにプロジェクトと区分の区別を明記
  - 曖昧な入力時はユーザーに確認するよう指示追加
  - _実装ファイル: data/projects.csv, data/categories.csv, kintai_agent/agent_a2a.py_

- [x] 24. Cognito認証の実装
  - CDKでCognito User PoolとApp Clientを定義
  - Frontend用設定ファイル（config.py）を作成
  - Streamlit UIにログイン画面を実装
  - Cognitoアクセストークンでランタイム認証
  - _実装ファイル: cdk/lib/kintai-agent-stack.ts, frontend_a2a/config.py, frontend_a2a/app.py_

- [x] 25. M2Mトークンキャッシュの最適化（DynamoDB）
  - CDKでDynamoDBテーブル（`kintai-agent-token-cache-*`）を作成
  - TTL属性による自動削除を設定
  - RuntimeにDynamoDB読み書き権限を付与
  - core.pyにDynamoDBベースの共有トークンキャッシュを実装
  - コンテナ間でトークンを共有し、Cognito M2Mコスト削減
  - _実装ファイル: cdk/lib/kintai-agent-stack.ts, kintai_agent/core.py_
  - _背景: AgentCore Runtimeはコンテナが頻繁に入れ替わるため、インメモリキャッシュでは効果が限定的_
