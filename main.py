# main.py
from fastapi import FastAPI, Request
from slack_bolt.adapter.fastapi import SlackRequestHandler
from slack_bolt import App
import os
from dotenv import load_dotenv

load_dotenv()

slack_app = App(
    token=os.getenv("SLACK_BOT_TOKEN"),
    signing_secret=os.getenv("SLACK_SIGNING_SECRET")
)

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
