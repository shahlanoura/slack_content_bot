# main.py
import os
import threading
import uvicorn
from slack_bolt.adapter.socket_mode import SocketModeHandler
from app.slack_app import slack_app, app  # FastAPI + Slack Bolt

# Load environment variables
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN")

if not SLACK_APP_TOKEN:
    raise ValueError("⚠️ SLACK_APP_TOKEN not found in environment.")

# ------------------------------
# Run Slack bot in background
# ------------------------------
def run_slack_bot():
    print("⚡ Starting Slack Socket Mode bot...")
    handler = SocketModeHandler(slack_app, SLACK_APP_TOKEN)
    handler.start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    print(f"🌐 Starting FastAPI server on port {port} (Render health check)...")

    # Only start Slack bot once
    if os.environ.get("RUN_MAIN") != "true":
        threading.Thread(target=run_slack_bot, daemon=True).start()

    uvicorn.run(app, host="0.0.0.0", port=port)
