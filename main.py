# main.py
import os
import threading
from fastapi import FastAPI, Request
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_bolt.adapter.fastapi import SlackRequestHandler

# Load environment variables
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN")

if not SLACK_BOT_TOKEN or not SLACK_APP_TOKEN:
    raise ValueError("Slack tokens not set in environment variables")

# Initialize Bolt App
bolt_app = App(token=SLACK_BOT_TOKEN)
handler = SlackRequestHandler(bolt_app)

# Example event handler
@bolt_app.event("app_mention")
def handle_app_mention(event, say):
    user = event["user"]
    say(f"Hello <@{user}>! How can I help you today?")

# Initialize FastAPI
app = FastAPI()

# Slack Events endpoint (optional if using Socket Mode)
@app.post("/slack/events")
async def slack_events(req: Request):
    return await handler.handle(req)

# Root endpoint (optional)
@app.get("/")
async def root():
    return {"status": "Slack bot is running!"}

# Function to start Socket Mode in a separate thread
def start_socket_mode():
    SocketModeHandler(bolt_app, SLACK_APP_TOKEN).start()

# Only start Socket Mode if running directly
if __name__ == "__main__":
    # Start Socket Mode in background
    thread = threading.Thread(target=start_socket_mode)
    thread.daemon = True
    thread.start()

    # Start FastAPI on Render port
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
