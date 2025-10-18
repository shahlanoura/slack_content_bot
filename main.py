# main.py
import threading
import os
from fastapi import FastAPI
from slack_bolt.adapter.socket_mode import SocketModeHandler
from app.slack_app import slack_app

app = FastAPI()

# Simple HTTP endpoints for Render / health checks
@app.get("/")
def home():
    return {"status": "Slackbot Content Pipeline is running 🚀"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

# Start Slack bot in Socket Mode on a separate thread
def start_slack_bot():
    handler = SocketModeHandler(slack_app, os.environ["SLACK_APP_TOKEN"].strip())
    print("Slack bot is starting in Socket Mode...")
    handler.start()

threading.Thread(target=start_slack_bot, daemon=True).start()

# Only run HTTP server for local dev
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
