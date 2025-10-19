# main.py
import os
import uvicorn
from app.slack_app import app, slack_app  # Import both apps
from slack_bolt.adapter.socket_mode import SocketModeHandler

# -----------------------------
# Load environment variables
# -----------------------------
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN")
PORT = int(os.environ.get("PORT", 10000))

if not all([SLACK_BOT_TOKEN, SLACK_SIGNING_SECRET, SLACK_APP_TOKEN]):
    raise ValueError("⚠️ Missing Slack tokens in environment variables")

# -----------------------------
# Start Slack Socket Mode
# -----------------------------
def start_slack_handler():
    """Start Slack Socket Mode in background"""
    try:
        print("⚡️ Starting Slack Socket Mode handler...")
        handler = SocketModeHandler(slack_app, SLACK_APP_TOKEN)
        handler.start()
    except Exception as e:
        print(f"❌ Failed to start Slack handler: {e}")

# -----------------------------
# FastAPI Routes
# -----------------------------
@app.get("/")
def home():
    return {"status": "Slack Content Bot is live on Render!"}

@app.get("/health")
def health():
    return {"status": "ok"}

# -----------------------------
# Main execution
# -----------------------------
if __name__ == "__main__":
    print(f"🚀 Starting application on port {PORT}")
    
    # Start Slack handler
    import threading
    slack_thread = threading.Thread(target=start_slack_handler, daemon=True)
    slack_thread.start()
    
    print("✅ Slack handler started in background")
    print("🌐 Starting FastAPI server...")
    
    # Start FastAPI
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=PORT,
        log_level="info"
    )