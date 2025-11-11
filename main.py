import os
from slack_bolt.adapter.socket_mode import SocketModeHandler
from app.slack_app import slack_app  

if __name__ == "__main__":
    SocketModeHandler(slack_app, os.environ.get("SLACK_APP_TOKEN")).start()
