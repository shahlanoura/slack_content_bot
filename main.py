# main.py
import os
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

# Slack tokens
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN")

if not SLACK_BOT_TOKEN or not SLACK_APP_TOKEN:
    raise ValueError("Slack tokens not set in environment variables")

app = App(token=SLACK_BOT_TOKEN)

# Example event handler
@app.event("app_mention")
def mention_handler(event, say):
    say(f"Hello <@{event['user']}>!")

# Run Socket Mode directly (no HTTP server needed)
if __name__ == "__main__":
    SocketModeHandler(app, SLACK_APP_TOKEN).start()
