# main.py
import os
import threading
from slack_bolt.adapter.socket_mode import SocketModeHandler
from app.slack_app import slack_app, app  # import FastAPI app
import uvicorn

# Load environment variables
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN")  

if not SLACK_BOT_TOKEN or not SLACK_SIGNING_SECRET or not SLACK_APP_TOKEN:
    raise ValueError(
        "⚠️ Slack tokens not found in environment. Make sure SLACK_BOT_TOKEN, "
        "SLACK_SIGNING_SECRET, and SLACK_APP_TOKEN are set."
    )

# Start Slack Socket Mode in a background thread
def run_slack_bot():
    SocketModeHandler(slack_app, SLACK_APP_TOKEN).start()

threading.Thread(target=run_slack_bot, daemon=True).start()

# Start FastAPI server for Render to detect a port
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))  # Render sets PORT automatically
    uvicorn.run(app, host="0.0.0.0", port=port)
