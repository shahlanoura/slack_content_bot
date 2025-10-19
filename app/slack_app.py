import os
import ast
import requests
import threading
import io
import csv
import logging
from PyPDF2 import PdfReader
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
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

# ---------------------- Configuration ----------------------
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET")

if not SLACK_BOT_TOKEN or not SLACK_SIGNING_SECRET:
    raise ValueError("Slack tokens not found in environment variables.")

# ---------------------- Logging Setup ----------------------
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ---------------------- App Initialization ----------------------
# Initialize FastAPI app
app = FastAPI(title="Slack Content Bot", version="1.0.0")

# Initialize Slack app
slack_app = App(
    token=SLACK_BOT_TOKEN,
    signing_secret=SLACK_SIGNING_SECRET,
    logger=logger
)

handler = SlackRequestHandler(slack_app)

# ---------------------- FastAPI Routes ----------------------
@app.get("/")
async def root():
    return {
        "status": "online", 
        "service": "Slack Content Pipeline Bot",
        "version": "1.0.0"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "slack-content-bot"}

@app.post("/slack/events")
async def slack_events_endpoint(request: Request):
    return await handler.handle(request)

# ---------------------- Helper Functions ----------------------
def parse_keywords_from_text(raw_text: str) -> list:
    """Parse keywords from various input formats"""
    if not raw_text:
        return []
    
    text = raw_text.strip()
    logger.info(f"Parsing keywords from text: {text[:100]}...")
    
    # Remove 'keyword' prefix if present
    if text.lower().startswith("keyword"):
        text = text[len("keyword"):].strip()
    
    # Try to parse as Python list
    try:
        if text.startswith("[") and text.endswith("]"):
            lst = ast.literal_eval(text)
            if isinstance(lst, list):
                keywords = [str(x).strip() for x in lst if str(x).strip()]
                logger.info(f"Parsed as list: {keywords}")
                return keywords
    except Exception as e:
        logger.debug(f"Could not parse as list: {e}")
    
    # Parse as text with various separators
    text = text.replace("\r", "\n").replace(",", "\n")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    
    # Remove empty lines and duplicates while preserving order
    keywords = list(dict.fromkeys([line for line in lines if line]))
    logger.info(f"Parsed {len(keywords)} keywords: {keywords}")
    
    return keywords

def get_user_email(user_id: str) -> str:
    """Get user's email from Slack API"""
    try:
        logger.info(f"Fetching email for user: {user_id}")
        response = slack_app.client.users_info(user=user_id)
        if response["ok"]:
            email = response["user"]["profile"].get("email")
            logger.info(f"Found email: {email}")
            return email
        else:
            logger.warning(f"Failed to get user info: {response.get('error')}")
    except Exception as e:
        logger.error(f"Error fetching user email: {e}")
    return None

def extract_text_from_file(file_info: dict) -> str:
    """Extract text from uploaded files (CSV, PDF, TXT)"""
    try:
        file_url = file_info["url_private_download"]
        mimetype = file_info.get("mimetype", "")
        filename = file_info.get("name", "")
        
        logger.info(f"Processing file: {filename}, type: {mimetype}")
        
        # Download file
        headers = {"Authorization": f"Bearer {SLACK_BOT_TOKEN}"}
        response = requests.get(file_url, headers=headers)
        if response.status_code != 200:
            raise Exception(f"Failed to download file: {response.status_code}")
        
        file_text = ""
        
        # Process based on file type
        if "csv" in mimetype or filename.lower().endswith('.csv'):
            logger.info("Processing CSV file")
            decoded = response.content.decode("utf-8")
            reader = csv.reader(io.StringIO(decoded))
            for row in reader:
                for cell in row:
                    cell_clean = cell.strip()
                    if cell_clean and cell_clean.lower() != "keyword":
                        file_text += cell_clean + "\n"
                        
        elif "pdf" in mimetype or filename.lower().endswith('.pdf'):
            logger.info("Processing PDF file")
            reader = PdfReader(io.BytesIO(response.content))
            for page_num, page in enumerate(reader.pages):
                page_text = page.extract_text()
                if page_text:
                    file_text += f"Page {page_num + 1}:\n{page_text}\n\n"
                    
        else:  # Treat as text file
            logger.info("Processing text file")
            file_text = response.text
        
        logger.info(f"Extracted {len(file_text)} characters from file")
        return file_text.strip()
        
    except Exception as e:
        logger.error(f"Error extracting text from file: {e}")
        raise

# ---------------------- Main Processing Function ----------------------
def process_keywords_async(command: dict, channel_id: str = None):
    """Main keyword processing pipeline - runs in background thread"""
    user_id = command.get("user_id")
    text = command.get("text", "")
    
    try:
        logger.info(f"🔹 Step 1: Starting keyword processing for user {user_id}")
        
        # Parse keywords
        keywords_list = parse_keywords_from_text(text)
        logger.info(f"🔹 Step 2: Parsed {len(keywords_list)} keywords: {keywords_list}")
        
        if not keywords_list:
            slack_app.client.chat_postMessage(
                channel=channel_id or user_id,
                text="⚠️ No valid keywords found in your input."
            )
            return
        
        # Send initial processing message
        slack_app.client.chat_postMessage(
            channel=channel_id or user_id,
            text=f"🔍 Processing {len(keywords_list)} keywords through the content pipeline..."
        )
        
        # Execute pipeline steps
        logger.info("🔹 Step 3: Cleaning keywords...")
        cleaned = clean_keywords(keywords_list)
        logger.info(f"🔹 Cleaned keywords: {cleaned}")
        
        logger.info("🔹 Step 4: Clustering keywords...")
        clusters = cluster_keywords(cleaned)
        logger.info(f"🔹 Created {len(clusters)} clusters")
        
        logger.info("🔹 Step 5: Fetching top results...")
        outlines = fetch_top_results(clusters)
        logger.info(f"🔹 Generated {len(outlines)} outlines")
        
        logger.info("🔹 Step 6: Generating post ideas...")
        ideas = generate_post_idea(clusters)
        logger.info(f"🔹 Generated {len(ideas)} ideas")
        
        logger.info("🔹 Step 7: Generating PDF report...")
        pdf_path = generate_pdf_report(
            raw_keywords=keywords_list,
            cleaned=cleaned,
            clusters=clusters,
            outlines=outlines,
            ideas=ideas
        )
        logger.info(f"🔹 PDF generated at: {pdf_path}")
        
        # Send completion message
        logger.info("🔹 Step 8: Sending completion message...")
        slack_app.client.chat_postMessage(
            channel=channel_id or user_id,
            text=f"✅ Keyword processing completed! Generated report with {len(clusters)} content clusters."
        )
        
        # Open DM channel for file upload
        logger.info("🔹 Step 9: Opening DM channel...")
        dm_response = slack_app.client.conversations_open(users=user_id)
        dm_channel_id = dm_response["channel"]["id"]
        
        # Upload PDF to DM
        logger.info("🔹 Step 10: Uploading PDF to Slack...")
        with open(pdf_path, "rb") as f:
            upload_result = slack_app.client.files_upload_v2(
                channel=dm_channel_id,
                file=f,
                filename="content_pipeline_report.pdf",
                title="Content Pipeline Report",
                initial_comment="Here's your content pipeline report! 📊"
            )
        logger.info("🔹 Step 11: PDF uploaded successfully")
        
        # Send email if available
        user_email = get_user_email(user_id)
        if user_email:
            logger.info(f"🔹 Step 12: Sending email to: {user_email}")
            email_sent = send_pdf_via_email(user_email, pdf_path, "Content Pipeline User")
            if email_sent:
                slack_app.client.chat_postMessage(
                    channel=dm_channel_id,
                    text=f"📧 Report also sent to your email: {user_email}"
                )
                logger.info("🔹 Step 13: Email sent successfully")
        
        logger.info("🎉 Keyword processing completed successfully")
        
    except Exception as e:
        logger.error(f"❌ Error in keyword processing: {e}")
        error_message = f"❌ Sorry, I encountered an error while processing your keywords."
        
        try:
            slack_app.client.chat_postMessage(
                channel=channel_id or user_id,
                text=error_message
            )
        except Exception as slack_error:
            logger.error(f"Failed to send error message to Slack: {slack_error}")

# ---------------------- Slack Event Handlers ----------------------
@slack_app.event("app_mention")
def handle_app_mention(body, say, logger):
    """Handle when the bot is mentioned"""
    try:
        event = body["event"]
        user = event["user"]
        
        logger.info(f"Bot mentioned by user {user}")
    except Exception as slack_error:
            logger.error(f"Failed to send error message to Slack: {slack_error}")   
    help_text = f"""
Hello <@{user}>! 👋 I'm your Content Pipeline Bot!

Here's how to use me:

📝 *Text Input:*
• Start with `keyword` followed by your keywords:"""