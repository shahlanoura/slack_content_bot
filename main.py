# main.py
import os
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from app.slack_app import slack_app 
# Load environment variables
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN")  

if not SLACK_BOT_TOKEN or not SLACK_SIGNING_SECRET or not SLACK_APP_TOKEN:
    raise ValueError(
        "⚠️ Slack tokens not found in environment. Make sure SLACK_BOT_TOKEN, "
        "SLACK_SIGNING_SECRET, and SLACK_APP_TOKEN are set."
    )





if __name__ == "__main__":
    SocketModeHandler(slack_app, os.environ.get("SLACK_APP_TOKEN")).start()
