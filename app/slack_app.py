import os
import io
import threading
import pandas as pd
import csv
import ast
from slack_bolt import App
from app.email_service import send_pdf_via_email
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk.errors import SlackApiError
from app.pipeline import (
    clean_keywords,
    cluster_keywords,
    fetch_top_results,
    generate_post_idea,
    generate_pdf_report
)
from dotenv import load_dotenv
import requests

load_dotenv()

slack_app = App(
    token=os.environ["SLACK_BOT_TOKEN"],
    signing_secret=os.environ["SLACK_SIGNING_SECRET"]
)

def parse_keywords_from_text(raw_text):
    """
    Extract keywords from Slack messages or files.
    Handles:
      - 'keyword' prefix on same or separate line
      - Python list format ["a", "b", "c"]
      - comma separated: a, b, c
      - newline separated
      - deduplication
    """
    if not raw_text:
        return []

    text = raw_text.strip()

    # Remove leading "keyword" prefix 
    if text.lower().startswith("keyword"):
        # remove only the first occurrence of "keyword"
        text = text[len("keyword"):].strip()

    # Handle Python list input
    try:
        if text.startswith("[") and text.endswith("]"):
            lst = ast.literal_eval(text)
            if isinstance(lst, list):
                keywords = [str(x).strip() for x in lst if str(x).strip()]
                return list(dict.fromkeys(keywords))
    except Exception:
        pass

    # --- 3️⃣ Normalize commas/newlines ---
    text = text.replace("\r", "\n").replace(",", "\n")

    # --- 4️⃣ Split and clean ---
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    keywords = [kw for kw in lines if kw.lower() != "keyword"]

    # --- 5️⃣ Deduplicate ---
    return list(dict.fromkeys(keywords))





# Async processing

def process_keywords_async(command, respond, file_content=None):
    try:
        if file_content:
            df_keywords = pd.DataFrame({"keyword": parse_keywords_from_text(file_content.decode("utf-8", errors="ignore"))})
        else:
            df_keywords = pd.DataFrame({"keyword": parse_keywords_from_text(command.get("text",""))})

        if df_keywords.empty:
            respond(text="⚠️ No valid keywords found in your input.")
            return

        raw_keywords = df_keywords["keyword"].tolist()
        raw_keywords = df_keywords["keyword"].tolist()
       

        cleaned = clean_keywords(raw_keywords)
        clusters = cluster_keywords(cleaned)
        outlines = fetch_top_results(clusters)
        ideas = generate_post_idea(clusters)
        
        pdf_path = generate_pdf_report(
            raw_keywords=raw_keywords,
            cleaned=cleaned,
            clusters=clusters,
            outlines=outlines,
            ideas=ideas
            )

        respond(blocks=[
            {"type": "section", "text": {"type": "mrkdwn", "text": "*Keyword Processing Completed ✅*"}},
            {"type": "divider"},
            {"type": "section", "text": {"type": "mrkdwn", "text": f"📦 *Cleaned Keywords:* {len(cleaned)}"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": f"🔹 *Clusters Formed:* {len(clusters)}"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": f"🧠 *Post Ideas Generated:* {len(ideas)}"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": f"📄 PDF report has been sent to your DM."}}
        ])

        # Upload PDF to DM
        dm_response = slack_app.client.conversations_open(users=command["user_id"])
        dm_channel_id = dm_response["channel"]["id"]
        with open(pdf_path, "rb") as f:
            slack_app.client.files_upload_v2(
                channel=dm_channel_id,
                file=f,
                filename="report.pdf",
                title="Content Pipeline Report"
            )
        user_email = get_user_email(command["user_id"])
        if user_email:
            user_info = slack_app.client.users_info(user=command["user_id"])
            user_name = user_info["user"]["real_name"] if user_info["ok"] else "User"
            
            email_sent = send_pdf_via_email(user_email, pdf_path, user_name)
            if email_sent:
                slack_app.client.chat_postMessage(
                    channel=dm_channel_id,
                    text=f"📧 Report also sent to your email: {user_email}"
                )
        else:
            slack_app.client.chat_postMessage(
                channel=dm_channel_id,
                text="📧 Could not retrieve your email address from Slack profile."
            )
    except Exception as e:
        respond(text=f"❌ Something went wrong while processing your keywords:\n```{e}```")


@slack_app.command("/keywords")
def handle_keywords(ack, respond, command):
    ack("✅ Received your keywords. Processing in background...")
    file_content = None
    if "files" in command and command["files"]:
        file_id = command["files"][0]["id"]
        result = slack_app.client.files_info(file=file_id)
        url_private = result["file"]["url_private_download"]
        headers = {"Authorization": f"Bearer {os.environ['SLACK_BOT_TOKEN']}"}
        r = requests.get(url_private, headers=headers)
        file_content = r.content

    threading.Thread(target=process_keywords_async, args=(command, respond, file_content)).start()


@slack_app.event("file_shared")
@slack_app.event("file_shared")
def handle_file_shared(event, say):
    try:
        file_id = event["file"]["id"]
        file_info = slack_app.client.files_info(file=file_id)
        file_url = file_info["file"]["url_private_download"]
        user_id = file_info["file"]["user"]  

        headers = {"Authorization": f"Bearer {os.environ['SLACK_BOT_TOKEN']}"}
        response = requests.get(file_url, headers=headers)

        if response.status_code == 200:
            df_keywords = pd.DataFrame({
                "keyword": parse_keywords_from_text(response.content.decode("utf-8", errors="ignore"))
            })
            if df_keywords.empty:
                say("⚠️ No valid keywords found in the uploaded file.")
                return

            raw_keywords = df_keywords["keyword"].tolist()
            cleaned = clean_keywords(raw_keywords)
            clusters = cluster_keywords(cleaned)
            outlines = fetch_top_results(clusters)
            ideas = generate_post_idea(clusters)
            pdf_path = generate_pdf_report(raw_keywords, cleaned, clusters, outlines, ideas)

            # 🟢 Public confirmation message
            say(f"✅ CSV processed successfully with {len(cleaned)} keywords!\n📩 Report sent privately to <@{user_id}>.")

            # 🟢 DM the user their PDF report
            user_id = event["user_id"]
            dm = slack_app.client.conversations_open(users=user_id)
            dm_channel = dm["channel"]["id"]

            with open(pdf_path, "rb") as f:
                slack_app.client.files_upload_v2(
                    channel=dm_channel,
                    file=f,
                    filename="content_pipeline_report.pdf",
                    title="Content Pipeline Report",
                    initial_comment=":page_facing_up: Here’s your content pipeline report 📊"
                )

        else:
            say("❌ Failed to download the file from Slack servers.")

    except Exception as e:
        say(f"⚠️ Error processing uploaded file: {e}")



# Plain text message handler
@slack_app.event("message")
def handle_keyword_messages(event, say):
    try:
        text = event.get("text", "")
        user_id = event.get("user", "")
        channel_id = event.get("channel", "")

        if "bot_id" in event:
            return

        if text.lower().startswith("keyword"):
            command_like = {"user_id": user_id, "text": text}

            def send_message(channel_id, text=None, blocks=None):
                slack_app.client.chat_postMessage(channel=channel_id, text=text or " ", blocks=blocks)

            threading.Thread(
                target=process_keywords_async,
                args=(command_like, lambda **kwargs: send_message(channel_id, **kwargs), None)
            ).start()

            df_keywords = pd.DataFrame({"keyword": parse_keywords_from_text(text)})
            say(channel=channel_id, text=f"✅ Received {len(df_keywords)} keywords. Processing in background...")

    except Exception as e:
        say(channel=channel_id, text=f"❌ Something went wrong: {e}")



def get_user_email(user_id):
    """
    Get user's email address from Slack
    """
    try:
        response = slack_app.client.users_info(user=user_id)
        if response["ok"]:
            user_profile = response["user"]["profile"]
            return user_profile.get("email")
    except Exception as e:
        print(f"Error getting user email: {e}")
    return None
# Start app

if __name__ == "__main__":
    handler = SocketModeHandler(slack_app, os.environ["SLACK_APP_TOKEN"])
    handler.start()
