# main.py
import os
from fastapi import FastAPI, Request
from slack_bolt.adapter.fastapi import SlackRequestHandler
from app.slack_app import slack_app
from dotenv import load_dotenv

load_dotenv()  

app = FastAPI()
handler = SlackRequestHandler(slack_app)
import os
import sys

print("Current directory:", os.getcwd())
print("Files in directory:", os.listdir('.'))
if os.path.exists('app'):
    print("App directory contents:", os.listdir('app'))

try:
    from app.slack_app import slack_app
    from slack_bolt.adapter.fastapi import SlackRequestHandler
    print("✅ Successfully imported slack_app")
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Python path:", sys.path)
    raise

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