import os
from fastapi import FastAPI, Request
from slack_bolt.adapter.fastapi import SlackRequestHandler
from app.slack_app import slack_app

app = FastAPI()
handler = SlackRequestHandler(slack_app)

@app.get("/")
def home():
    return {"status": "Slackbot Content Pipeline is running 🚀"}

@app.post("/slack/events")
async def slack_events(req: Request):
    return await handler.handle(req)
