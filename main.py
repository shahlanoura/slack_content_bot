# main.py
import os
import threading
from slack_bolt.adapter.socket_mode import SocketModeHandler
from app.slack_app import slack_app, app  # import FastAPI app
import uvicorn

# ------------------------------
# Load environment variables
# ------------------------------
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN")

if not all([SLACK_BOT_TOKEN, SLACK_SIGNING_SECRET, SLACK_APP_TOKEN]):
    raise ValueError(
        "⚠️ Missing Slack tokens. Make sure SLACK_BOT_TOKEN, "
        "SLACK_SIGNING_SECRET, and SLACK_APP_TOKEN are set."
    )


# ------------------------------
# Start Slack Socket Mode in background thread
# ------------------------------
def run_slack_bot():
    print("⚡ Starting Slack Socket Mode bot...")
    handler = SocketModeHandler(slack_app, SLACK_APP_TOKEN)
    handler.start()


# Start the Slack thread before running FastAPI
threading.Thread(target=run_slack_bot, daemon=True).start()


# ------------------------------
# Run FastAPI on Render-compatible port
# ------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))  # Render expects this
    print(f"🌐 Starting FastAPI server on port {port} (Render will check this port)...")
    t = threading.Thread(target=run_slack_bot, daemon=True)
    t.start()
    uvicorn.run(
        "app.slack_app:app",  
        host="0.0.0.0",
        port=port
    )



