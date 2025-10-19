# main.py
import os
import uvicorn
from app.slack_app import app, slack_app
from slack_bolt.adapter.socket_mode import SocketModeHandler
import threading

# Load environment variables
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN")

if not all([SLACK_BOT_TOKEN, SLACK_SIGNING_SECRET, SLACK_APP_TOKEN]):
    raise ValueError("Missing Slack tokens")

def start_socket_handler():
    """Start Slack Socket Mode"""
    try:
        print("⚡️ Starting Slack Socket Mode...")
        handler = SocketModeHandler(slack_app, SLACK_APP_TOKEN)
        handler.start()
    except Exception as e:
        print(f"Error starting Socket Mode: {e}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    
    # Start Socket Mode in background thread
    socket_thread = threading.Thread(target=start_socket_handler, daemon=True)
    socket_thread.start()
    
    print(f"🚀 Starting FastAPI server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)