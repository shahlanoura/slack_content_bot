import os
from fastapi import FastAPI
from slack_bolt.adapter.fastapi import SlackRequestHandler
from slack_bolt import App

# Slack Bolt App
slack_app = App(token=os.environ["SLACK_BOT_TOKEN"], signing_secret=os.environ["SLACK_SIGNING_SECRET"])
app = FastAPI()
handler = SlackRequestHandler(slack_app)

@app.post("/slack/events")
async def slack_events(req):
    return await handler.handle(req)

@app.get("/")
def root():
    return {"message": "Slack bot is running!"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))  # Render provides this PORT variable
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port)
