# AgentCore Runtime用Dockerイメージ (ARM64)
FROM --platform=linux/arm64 python:3.12-slim

# 作業ディレクトリを設定
WORKDIR /app

# 依存関係をインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコードをコピー
COPY . .

# __pycache__を削除
RUN find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# ポート8080で待ち受け（AgentCore Runtimeの要件）
EXPOSE 8080

# エントリーポイント
CMD ["python", "main.py"]
