# app/slack_app.py
import os
import ast
import requests
from fastapi import FastAPI, Request, BackgroundTasks
from slack_bolt import App
import threading
from slack_bolt.adapter.fastapi import SlackRequestHandler
from app.pipeline import (
    clean_keywords,
    cluster_keywords,
    fetch_top_results,
    generate_post_idea,
    generate_pdf_report
)
from app.email_service import send_pdf_via_email

# ------------------- Initialize Slack Bolt App -------------------

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET")

if not SLACK_BOT_TOKEN or not SLACK_SIGNING_SECRET:
    raise ValueError("Slack tokens not found in environment variables.")

# ✅ Define App before decorators
slack_app = App(token=SLACK_BOT_TOKEN, signing_secret=SLACK_SIGNING_SECRET)

# FastAPI setup
app = FastAPI()
handler = SlackRequestHandler(slack_app)

# ------------------- Helpers -------------------

import ast
import re

def parse_keywords_from_text(raw_text):
    """
    Parse raw text input from Slack into a list of keywords.

    Handles:
    - 'keyword' prefix
    - Python-style lists: [ ... ]
    - Comma-separated keywords
    - Multiple keywords in one line (split by space or comma)
    - Removes duplicates
    """
    if not raw_text:
        return []

    text = raw_text.strip()

    # Remove 'keyword' prefix if present
    if text.lower().startswith("keyword"):
        text = text[len("keyword"):].strip()

    # Handle Python-style list input
    try:
        if text.startswith("[") and text.endswith("]"):
            lst = ast.literal_eval(text)
            if isinstance(lst, list):
                return [str(x).strip() for x in lst if str(x).strip()]
    except Exception:
        pass

    # Replace carriage returns and commas with newlines
    text = text.replace("\r", "\n").replace(",", "\n")

    lines = [line.strip() for line in text.splitlines() if line.strip()]

    keywords = []
    for line in lines:
        # Split each line by spaces or any remaining commas
        parts = re.split(r'[,\s]+', line)
        keywords.extend([p.strip() for p in parts if p.strip()])

    # Remove duplicates while preserving order
    return list(dict.fromkeys(keywords))


def get_user_email(slack_app, user_id):
    try:
        response = slack_app.client.users_info(user=user_id)
        if response["ok"]:
            return response["user"]["profile"].get("email")
    except Exception as e:
        print(f"[Email Fetch Error] {e}")
    return None

# ------------------- Main Processing -------------------

def process_keywords_async(command, slack_app, channel_id=None):
    try:
        print("🔹 Starting keyword processing...")
        text = command.get("text", "")
        user_id = command.get("user_id")

        keywords_list = parse_keywords_from_text(text)
        if not keywords_list:
            slack_app.client.chat_postMessage(
                channel=channel_id or user_id,
                text="⚠️ No valid keywords found."
            )
            return

        print(f"🔹 Keywords parsed: {keywords_list}")

        cleaned = clean_keywords(keywords_list)
        clusters = cluster_keywords(cleaned)
        outlines = fetch_top_results(clusters)
        ideas = generate_post_idea(clusters)

        print("🔹 Pipeline complete. Generating PDF...")
        pdf_path = generate_pdf_report(
            raw_keywords=keywords_list,
            cleaned=cleaned,
            clusters=clusters,
            outlines=outlines,
            ideas=ideas
        )
        print(f"🔹 PDF generated at {pdf_path}")

        slack_app.client.chat_postMessage(
            channel=channel_id or user_id,
            text=f"✅ Keyword processing completed! PDF report will be uploaded shortly."
        )

        dm_response = slack_app.client.conversations_open(users=user_id)
        dm_channel_id = dm_response["channel"]["id"]
        with open(pdf_path, "rb") as f:
            slack_app.client.files_upload_v2(
                channel=dm_channel_id,
                file=f,
                filename="content_pipeline_report.pdf",
                title="Content Pipeline Report"
            )

        print("🔹 PDF uploaded to Slack DM")

        user_email = get_user_email(slack_app, user_id)
        if user_email:
            if send_pdf_via_email(user_email, pdf_path, "User"):
                slack_app.client.chat_postMessage(
                    channel=dm_channel_id,
                    text=f"📧 Report also sent to your email: {user_email}"
                )

    except Exception as e:
        print(f"[Processing Error] {e}")
        slack_app.client.chat_postMessage(
            channel=channel_id or command.get("user_id"),
            text=f"❌ Something went wrong:\n```{e}```"
        )

# ------------------- Slack Event Handlers -------------------

@slack_app.event("app_mention")
def handle_app_mention(body, say):
    user = body["event"]["user"]
    say(f"Hello <@{user}>! I'm running on Render! 🚀")

@slack_app.event("message")
def handle_keyword_messages(event, say):
    text = event.get("text", "")
    user_id = event.get("user")
    channel_id = event.get("channel")

    if "bot_id" in event:
        return

    if text.lower().startswith("keyword"):
        say("✅ Received keywords. Processing...")
        command_like = {"user_id": user_id, "text": text}
        threading.Thread(
    target=process_keywords_async,
    args=(command_like, slack_app, channel_id),
    daemon=True
    ).start()

@slack_app.event("file_shared")
def handle_file_shared(event, say):
    try:
        file_id = event["file"]["id"]
        file_info = slack_app.client.files_info(file=file_id)
        file_url = file_info["file"]["url_private_download"]
        user_id = file_info["file"]["user"]

        headers = {"Authorization": f"Bearer {slack_app.client.token}"}
        r = requests.get(file_url, headers=headers)
        if r.status_code == 200:
            text_content = r.content.decode("utf-8")  # decode CSV as text
            # Convert CSV lines to newline-separated text
            keywords_text = "\n".join([line.strip() for line in text_content.splitlines() if line.strip()])

            say("✅ File received. Processing in background...")

            command_like = {"user_id": user_id, "text": keywords_text}
            threading.Thread(
                target=process_keywords_async,
                args=(command_like, slack_app, None),
                daemon=True
            ).start()
        else:
            say("❌ Failed to download the file.")
    except Exception as e:
        say(f"⚠️ Error processing uploaded file: {e}")
