# main.py
import os
import threading
from fastapi import FastAPI, Request
from slack_bolt.adapter.fastapi import SlackRequestHandler

# Import your Slack app
from app.slack_app import slack_app
from slack_bolt.adapter.socket_mode import SocketModeHandler

app = FastAPI()
handler = SlackRequestHandler(slack_app)

@app.get("/")
def home():
    return {"status": "Slackbot Content Pipeline is running 🚀"}

@app.post("/slack/events")
async def slack_events(req: Request):
    return await handler.handle(req)

@app.get("/health")
def health_check():
    return {"status": "healthy"}

# Start Socket Mode in background thread
def start_socket_mode():
    try:
        print("🔄 Starting Socket Mode connection...")
        socket_handler = SocketModeHandler(slack_app, os.environ["SLACK_APP_TOKEN"])
        socket_handler.start()
        print("✅ Socket Mode connected successfully!")
    except Exception as e:
        print(f"❌ Socket Mode failed: {e}")

# Start socket mode when app loads
if os.environ.get("SLACK_APP_TOKEN"):
    print("🚀 Initializing Socket Mode...")
    socket_thread = threading.Thread(target=start_socket_mode, daemon=True)
    socket_thread.start()
else:
    print("⚠️ SLACK_APP_TOKEN not found - Socket Mode disabled")

# Only run for local development
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)