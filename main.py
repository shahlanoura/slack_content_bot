# main.py
from fastapi import FastAPI, Request
from slack_bolt.adapter.fastapi import SlackRequestHandler
from slack_bolt import App
import os
from dotenv import load_dotenv

load_dotenv()
from slack_bolt import App

slack_app = App(token=os.getenv("SLACK_BOT_TOKEN"), signing_secret=os.getenv("SLACK_SIGNING_SECRET"))
from app.slack_app import register_handlers
register_handlers(slack_app)

app = FastAPI()
handler = SlackRequestHandler(slack_app)

@app.get("/")
def root():
    return {"status": "Slack Content Bot is live on Render!"}

@app.post("/slack/events")
async def slack_events(req: Request):
    return await handler.handle(req)
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))  # Render provides this
    uvicorn.run("main:app", host="0.0.0.0", port=port, log_level="info")