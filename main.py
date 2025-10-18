# main.py
import os
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from app.slack_app import register_handlers

# Load environment variables (Render automatically sets these)
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN")  # For Socket Mode

if not SLACK_BOT_TOKEN or not SLACK_SIGNING_SECRET or not SLACK_APP_TOKEN:
    raise ValueError(
        "⚠️ Slack tokens not found in environment. Make sure SLACK_BOT_TOKEN, "
        "SLACK_SIGNING_SECRET, and SLACK_APP_TOKEN are set."
    )

# Initialize Slack App
slack_app = App(token=SLACK_BOT_TOKEN, signing_secret=SLACK_SIGNING_SECRET)

# Register your event handlers
register_handlers(slack_app)

# Start Socket Mode (avoids HTTP public URL issues on Render)
if __name__ == "__main__":
    print("🚀 Slack Content Bot is starting in Socket Mode...")
    handler = SocketModeHandler(slack_app, SLACK_APP_TOKEN)
    handler.start()
