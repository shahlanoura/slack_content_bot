# main.py
import os
import asyncio
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

# Async function to start Socket Mode
async def start_socket_mode():
    try:
        print("🔄 Starting Socket Mode connection...")
        if os.environ.get("SLACK_APP_TOKEN"):
            socket_handler = SocketModeHandler(slack_app, os.environ["SLACK_APP_TOKEN"])
            # Start in background without blocking
            await socket_handler.start_async()
            print("✅ Socket Mode connected successfully!")
        else:
            print("⚠️ SLACK_APP_TOKEN not found")
    except Exception as e:
        print(f"❌ Socket Mode failed: {e}")

# Start socket mode when app starts
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(start_socket_mode())

# Only run for local development
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)