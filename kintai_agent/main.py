"""
Kintai Agent - AgentCore Runtime エントリーポイント

このモジュールは、AgentCore Runtimeからエージェントを起動するための
エントリーポイントです。

使用方法:
    python main.py
"""
from agent import app

if __name__ == "__main__":
    # AgentCore Runtimeサーバーを起動
    app.run(port=8080)
