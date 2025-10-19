# main.py
import os
import threading
import uvicorn
from slack_bolt.adapter.socket_mode import SocketModeHandler
from app.slack_app import slack_app, app  # Your FastAPI app

# -----------------------------
# Load environment variables
# -----------------------------
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN")
PORT = int(os.environ.get("PORT", 10000))

if not SLACK_BOT_TOKEN or not SLACK_SIGNING_SECRET or not SLACK_APP_TOKEN:
    raise ValueError(
        "⚠️ Slack tokens not found. Make sure SLACK_BOT_TOKEN, "
        "SLACK_SIGNING_SECRET, and SLACK_APP_TOKEN are set."
    )

# -----------------------------
# Run Slack Socket Mode in a background thread
# -----------------------------
def run_slack_bot():
    print("⚡️ Starting Slack Socket Mode bot...")
    SocketModeHandler(slack_app, SLACK_APP_TOKEN).start()

# Start Slack bot in a daemon thread
threading.Thread(target=run_slack_bot, daemon=True).start()

# -----------------------------
# FastAPI health check endpoints
# -----------------------------
@app.get("/")
def home():
    return {"status": "Slack Content Bot is live on Render!"}

@app.get("/health")
def health():
    return {"status": "ok"}

# -----------------------------
# Run FastAPI on Render port
# -----------------------------
if __name__ == "__main__":
    print(f"🌐 Starting FastAPI server on port {PORT} (Render health check)...")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=PORT,
        log_level="info",
        access_log=True
    )
