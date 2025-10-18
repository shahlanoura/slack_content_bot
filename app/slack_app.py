# slack_app.py
import threading
import pandas as pd
import ast
import requests
from app.pipeline import (
    clean_keywords,
    cluster_keywords,
    fetch_top_results,
    generate_post_idea,
    generate_pdf_report
)
from app.email_service import send_pdf_via_email

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

    # Normalize commas/newlines
    text = text.replace("\r", "\n").replace(",", "\n")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    keywords = [kw for kw in lines if kw.lower() != "keyword"]

    # Deduplicate
    return list(dict.fromkeys(keywords))


def process_keywords_async(command, respond, slack_app, file_content=None):
    """
    Process keywords asynchronously:
      1. Parse & clean
      2. Cluster
      3. Fetch outlines
      4. Generate post ideas
      5. Generate PDF
      6. Send DM & email
    """
    try:
        # Parse keywords
        if file_content:
            keywords_list = parse_keywords_from_text(file_content.decode("utf-8", errors="ignore"))
        else:
            keywords_list = parse_keywords_from_text(command.get("text", ""))

        if not keywords_list:
            respond(text="⚠️ No valid keywords found.")
            return

        # Pipeline
        cleaned = clean_keywords(keywords_list)
        clusters = cluster_keywords(cleaned)
        outlines = fetch_top_results(clusters)
        ideas = generate_post_idea(clusters)
        pdf_path = generate_pdf_report(
            raw_keywords=keywords_list,
            cleaned=cleaned,
            clusters=clusters,
            outlines=outlines,
            ideas=ideas
        )

        # Respond in Slack
        respond(blocks=[
            {"type": "section", "text": {"type": "mrkdwn", "text": "*✅ Keyword Processing Completed*"}},
            {"type": "divider"},
            {"type": "section", "text": {"type": "mrkdwn", "text": f"📦 *Cleaned Keywords:* {len(cleaned)}"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": f"🔹 *Clusters Formed:* {len(clusters)}"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": f"🧠 *Post Ideas Generated:* {len(ideas)}"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": f"📄 PDF report has been sent to your DM."}}
        ])

        # Upload PDF to user DM
        dm_response = slack_app.client.conversations_open(users=command["user_id"])
        dm_channel_id = dm_response["channel"]["id"]
        with open(pdf_path, "rb") as f:
            slack_app.client.files_upload_v2(
                channel=dm_channel_id,
                file=f,
                filename="content_pipeline_report.pdf",
                title="Content Pipeline Report"
            )

        # Send PDF via email (optional)
        user_email = get_user_email(slack_app, command["user_id"])
        if user_email:
            email_sent = send_pdf_via_email(user_email, pdf_path, "User")
            if email_sent:
                slack_app.client.chat_postMessage(
                    channel=dm_channel_id,
                    text=f"📧 Report also sent to your email: {user_email}"
                )

    except Exception as e:
        respond(text=f"❌ Something went wrong:\n```{e}```")


def get_user_email(slack_app, user_id):
    """
    Retrieve email of a Slack user
    """
    try:
        response = slack_app.client.users_info(user=user_id)
        if response["ok"]:
            return response["user"]["profile"].get("email")
    except Exception as e:
        print(f"Error retrieving user email: {e}")
    return None


def register_handlers(slack_app):
    """
    Register all Slack event handlers
    """

    # Respond to app mentions
    @slack_app.event("app_mention")
    def mention_handler(body, say):
        user = body["event"]["user"]
        say(f"Hello <@{user}>! I'm running on Render!")

    # Handle plain "keyword ..." messages
    @slack_app.event("message")
    def handle_keyword_messages(event, say):
        try:
            text = event.get("text", "")
            user_id = event.get("user")
            channel_id = event.get("channel")

            # Ignore bot messages
            if "bot_id" in event:
                return

            if text.lower().startswith("keyword"):
                say(f"✅ Received keywords. Processing...")
                command_like = {"user_id": user_id, "text": text}

                threading.Thread(
                    target=process_keywords_async,
                    args=(command_like, lambda **kwargs: slack_app.client.chat_postMessage(channel=channel_id, **kwargs), slack_app)
                ).start()

        except Exception as e:
            say(f"❌ Error: {e}")

    # Handle file uploads
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
                file_content = r.content
                command_like = {"user_id": user_id, "text": ""}
                threading.Thread(
                    target=process_keywords_async,
                    args=(command_like, lambda **kwargs: slack_app.client.chat_postMessage(channel=user_id, **kwargs), slack_app, file_content)
                ).start()
                say(f"✅ File received. Processing keywords in background...")
            else:
                say("❌ Failed to download the file from Slack servers.")

        except Exception as e:
            say(f"⚠️ Error processing uploaded file: {e}")
