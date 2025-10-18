# main.py (now in root directory)
import os
from fastapi import FastAPI, Request
from slack_bolt.adapter.fastapi import SlackRequestHandler

# Import from app folder
from app.slack_app import slack_app

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

# Only run for local development
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)