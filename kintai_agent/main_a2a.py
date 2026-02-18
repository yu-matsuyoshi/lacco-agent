"""
Kintai Agent - A2A エントリーポイント

AgentCore Runtime (A2Aプロトコル) 用のエントリーポイント
ポート9000で起動
"""
import uvicorn
from agent_a2a import app

if __name__ == "__main__":
    # A2AサーバーをFastAPI/uvicornで起動
    uvicorn.run(app, host="0.0.0.0", port=9000)
