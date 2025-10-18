import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
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

# Slack Events Endpoint
@app.post("/slack/events")
async def slack_events(req: Request):
    return await handler.handle(req)

# Root Endpoint: responds to GET and HEAD for Render health check
@app.api_route("/", methods=["GET", "HEAD"])
def root():
    return JSONResponse(content={"message": "Slack bot is running!"})

# -----------------------------
# 3. Run server (Render-ready)
# -----------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))  # Render assigns this
    uvicorn.run(app, host="0.0.0.0", port=port)
