# app/slack_app.py
import os
import ast
import requests
from fastapi import FastAPI, Request,BackgroundTasks
import threading
import io
import csv
from PyPDF2 import PdfReader
from slack_bolt import App
from slack_bolt.adapter.fastapi import SlackRequestHandler
from app.pipeline import (
    clean_keywords,
    cluster_keywords,
    fetch_top_results,
    generate_post_idea,
    generate_pdf_report
)
from app.email_service import send_pdf_via_email

#  Initialize Slack Bolt App 

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET")

if not SLACK_BOT_TOKEN or not SLACK_SIGNING_SECRET:
    raise ValueError("Slack tokens not found in environment variables.")

# ✅ Define App before decorators
slack_app = App(token=SLACK_BOT_TOKEN, signing_secret=SLACK_SIGNING_SECRET)

# FastAPI setup
app = FastAPI()
handler = SlackRequestHandler(slack_app)

# Helpers 

def parse_keywords_from_text(raw_text):
    if not raw_text:
        return []
    text = raw_text.strip()
    if text.lower().startswith("keyword"):
        text = text[len("keyword"):].strip()
    try:
        if text.startswith("[") and text.endswith("]"):
            lst = ast.literal_eval(text)
            if isinstance(lst, list):
                return [str(x).strip() for x in lst if str(x).strip()]
    except Exception:
        pass
    text = text.replace("\r", "\n").replace(",", "\n")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return list(dict.fromkeys(lines))

def get_user_email(slack_app, user_id):
    try:
        response = slack_app.client.users_info(user=user_id)
        if response["ok"]:
            return response["user"]["profile"].get("email")
    except Exception as e:
        print(f"[Email Fetch Error] {e}")
    return None

#  Main Processing 

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

# Slack Event Handler

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
        print("📂 Starting CSV/PDF/Text file event handler...")

        file_id = event["file"]["id"]
        print(f"📎 File ID received: {file_id}")

        file_info = slack_app.client.files_info(file=file_id)["file"]
        file_url = file_info["url_private_download"]
        user_id = file_info["user"]
        mimetype = file_info.get("mimetype", "")
        file_name = file_info.get("name", "unknown")

        print(f"✅ Received file: {file_name}")
        print(f"📄 MIME Type: {mimetype}")

        headers = {"Authorization": f"Bearer {slack_app.client.token}"}
        r = requests.get(file_url, headers=headers)
        if r.status_code != 200:
            print(f"❌ Failed to download file: {r.status_code}")
            say("❌ Failed to download the file.")
            return
        print("📥 File downloaded successfully.")

        # ----------------- Extract text -----------------
        file_text = ""
        if "csv" in mimetype:
            print("🧠 Detected CSV file, starting to parse...")
            try:
                decoded = r.content.decode("utf-8")
                reader = csv.reader(io.StringIO(decoded))
                for row in reader:
                    for cell in row:
                        if cell.strip().lower() != "keyword":
                            file_text += cell.strip() + "\n"
                print("✅ CSV parsing completed successfully.")
            except Exception as e:
                print(f"⚠️ CSV parsing failed: {e}")
                say(f"⚠️ Failed to parse CSV: {e}")
                return

        elif "pdf" in mimetype:
            print("📘 Detected PDF file, starting to extract text...")
            try:
                reader = PdfReader(io.BytesIO(r.content))
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        file_text += page_text + "\n"
                print("✅ PDF text extraction completed.")
            except Exception as e:
                print(f"⚠️ PDF parsing failed: {e}")
                say(f"⚠️ Failed to parse PDF: {e}")
                return

        else:
            print("📄 Treating file as plain text.")
            try:
                file_text = r.text
                print("✅ Text file read successfully.")
            except Exception as e:
                print(f"⚠️ Text file read failed: {e}")
                say(f"⚠️ Failed to read file: {e}")
                return

        if not file_text.strip():
            print("⚠️ No text content found in file.")
            say("⚠️ No text found in the uploaded file.")
            return

        say("✅ File received. Processing in background...")
        print("🧠 Running keyword clustering and idea generation in background...")

        command_like = {"user_id": user_id, "text": file_text}
        threading.Thread(
            target=process_keywords_async,
            args=(command_like, slack_app, user_id),
            daemon=True
        ).start()

        print("🎉 CSV processing thread started successfully!")

    except Exception as e:
        print(f"⚠️ Error in file_shared event handler: {e}")
        say(f"⚠️ Error processing uploaded file: {e}")


# FastAPI Endpoint 

@app.post("/slack/events")
async def endpoint(req: Request):
    return await handler.handle(req)

@app.get("/")
def home():
    return {"status": "Slack Content Bot is live on Render!"}

from fastapi import Request
from fastapi.responses import JSONResponse

@app.api_route("/", methods=["GET", "HEAD"])
async def root(request: Request):
    # For HEAD requests, return an empty content
    if request.method == "HEAD":
        return JSONResponse(status_code=200, content={})
    
    # For GET requests, return a small message
    return JSONResponse(status_code=200, content={"status": "Slack Content Bot is live on Render!"})

