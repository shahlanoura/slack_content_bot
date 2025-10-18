import os
from fastapi import FastAPI, Request
from slack_bolt import App
from slack_bolt.adapter.fastapi import SlackRequestHandler

# -----------------------------
# 1. Slack App Initialization
# -----------------------------
slack_app = App(
    token=os.environ["SLACK_BOT_TOKEN"],
    signing_secret=os.environ["SLACK_SIGNING_SECRET"]
)

# Example Slack command or event
@slack_app.event("app_mention")
def handle_mention(event, say):
    user = event.get("user")
    say(f"Hello <@{user}>! I'm running on Render!")

# -----------------------------
# 2. FastAPI Setup
# -----------------------------
app = FastAPI()
handler = SlackRequestHandler(slack_app)

@app.post("/slack/events")
async def endpoint(req: Request):
    return await handler.handle(req)

@app.get("/")
def root():
    return {"message": "Slack bot is running!"}

# -----------------------------
# 3. Run server (Render-ready)
# -----------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))  # Render assigns this
    uvicorn.run(app, host="0.0.0.0", port=port)


