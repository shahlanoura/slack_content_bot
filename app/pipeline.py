import re
import os
import random
import ast
import requests
import pandas as pd
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from sentence_transformers import SentenceTransformer
from sklearn.cluster import KMeans
from scipy.spatial.distance import cdist
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
import nltk
from nltk.corpus import stopwords
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from app.email_service import send_pdf_via_email  # Your existing email function

# Load environment variables
load_dotenv()

# Download stopwords
nltk.download('stopwords')
STOPWORDS = set(stopwords.words('english'))

# ---------------- Slack App ----------------
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))
session_keywords = []

# ---------------- Utility ----------------
def slack_input_to_dataframe(raw_input):
    """
    Convert Slack input (list string, multi-line text, or list) into DataFrame
    """
    keywords = []

    if isinstance(raw_input, str):
        raw_input = raw_input.strip()
        # Python list string
        if raw_input.startswith("[") and raw_input.endswith("]"):
            try:
                parsed = ast.literal_eval(raw_input)
                if isinstance(parsed, list):
                    keywords.extend([kw.strip() for kw in parsed if isinstance(kw, str)])
            except:
                keywords = [w.strip() for w in raw_input.strip('[]').replace("'", "").split(",")]
        else:
            # Multi-line or space-separated
            for line in raw_input.split("\n"):
                keywords.extend(line.strip().split())
    elif isinstance(raw_input, list):
        keywords.extend([kw.strip() for kw in raw_input if isinstance(kw, str)])

    return pd.DataFrame({"keyword": [kw for kw in keywords if kw]})

def clean_keywords(raw_keywords):
    cleaned = []
    seen = set()
    for kw in raw_keywords:
        if not kw:
            continue
        kw = kw.strip().lower()
        kw = re.sub(r'[^a-zA-Z\s-]', '', kw)
        kw = ' '.join([w for w in kw.split() if w not in STOPWORDS and not w.isdigit()])
        kw = kw.strip()
        if kw and kw not in seen and len(kw) > 1:
            seen.add(kw)
            cleaned.append(kw)
    return cleaned

def cluster_keywords(cleaned_keywords, max_clusters=5):
    if len(cleaned_keywords) < 2:
        return [{"cluster_name": cleaned_keywords[0] if cleaned_keywords else "Misc",
                 "keywords": cleaned_keywords}]
    
    model = SentenceTransformer("paraphrase-albert-small-v2")
    embeddings = model.encode(cleaned_keywords)
    n_clusters = min(max_clusters, max(1, len(cleaned_keywords) // 3))
    kmeans = KMeans(n_clusters=n_clusters, random_state=42)
    labels = kmeans.fit_predict(embeddings)

    clusters = {}
    for kw, label, emb in zip(cleaned_keywords, labels, embeddings):
        clusters.setdefault(label, []).append((kw, emb))

    final_clusters = []
    for label, kw_emb_list in clusters.items():
        keywords, embs = zip(*kw_emb_list)
        centroid = kmeans.cluster_centers_[label]
        filtered = [(kw, emb) for kw, emb in zip(keywords, embs) if kw not in STOPWORDS and len(kw) > 2]
        if not filtered:
            filtered = list(zip(keywords, embs))
        cluster_name = filtered[np.argmin(cdist([centroid], np.array([e for _, e in filtered]), metric='cosine'))][0]
        final_clusters.append({"cluster_name": cluster_name, "keywords": list(keywords)})

    return final_clusters

def generate_post_idea(clusters):
    ideas = []
    for cluster in clusters:
        keyword = cluster["cluster_name"]
        idea = random.choice([
            f"Top 10 tips for {keyword}",
            f"Beginner's guide to {keyword}",
            f"Why {keyword} matters in 2025",
            f"How to master {keyword}",
        ])
        ideas.append({"cluster": cluster["cluster_name"], "idea": idea})
    return ideas

def extract_headings(url):
    try:
        r = requests.get(url, timeout=5, headers={'User-Agent':'Mozilla/5.0'})
        soup = BeautifulSoup(r.text, 'html.parser')
        headings = []
        for h in soup.select('h1,h2,h3')[:10]:
            text = h.get_text(strip=True)
            text = re.sub(r'^[\d\.#\s]+', '', text)
            text = re.sub(r'[\+\-\*\.\/\\]+$', '', text)
            if 5 < len(text) < 200:
                headings.append(text)
        return headings
    except:
        return []

def fetch_top_search(keyword, top_n=3):
    api_key = os.getenv("SERPER_API_KEY")
    url = "https://google.serper.dev/search"
    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    payload = {"q": keyword, "num": top_n, "gl": "us"}
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=5)
        data = r.json()
        results = [{"title": i["title"], "link": i["link"], "snippet": i.get("snippet","")}
                   for i in data.get("organic", [])[:top_n] if i.get("title") and i.get("link")]
        return results
    except:
        return []

def fetch_top_results(clusters, top_n_results=3):
    outlines = []

    def process_cluster(cluster):
        keyword = cluster["cluster_name"]
        serp_results = fetch_top_search(keyword)[:top_n_results]
        headings, sources = [], []

        if serp_results:
            with ThreadPoolExecutor(max_workers=3) as executor:
                future_to_url = {executor.submit(extract_headings, r["link"]): r["link"] for r in serp_results}
                for future in as_completed(future_to_url):
                    headings.extend(future.result())
                    sources.append(future_to_url[future])

        if not headings:
            headings = [f"Introduction about {keyword}",
                        f"Key points / highlights for {keyword}",
                        "Examples or case studies", "Conclusion"]

        return {"cluster": cluster["cluster_name"], "outline": headings, "sources": sources}

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(process_cluster, c) for c in clusters]
        for f in as_completed(futures):
            outlines.append(f.result())

    return outlines

def generate_pdf_report(raw_keywords, cleaned, clusters, outlines, ideas, filename="report.pdf"):
    temp = os.path.join(os.getcwd(), "reports")
    os.makedirs(temp, exist_ok=True)
    path = os.path.join(temp, filename)
    c = canvas.Canvas(path, pagesize=A4)
    width, height = A4

    def section_title(title, y_pos):
        c.setFont("Helvetica-Bold", 14)
        c.setFillColor(colors.darkblue)
        c.drawString(50, y_pos, title)
        c.setFillColor(colors.black)
        return y_pos - 25

    y = height - 60
    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, y, "AI Content Pipeline Report")
    y -= 30
    c.setFont("Helvetica", 12)
    c.drawString(50, y, f"Total Raw Keywords: {len(raw_keywords)}")
    y -= 15
    c.drawString(50, y, f"Total Cleaned Keywords: {len(cleaned)}")
    y -= 15
    c.drawString(50, y, f"Clusters Formed: {len(clusters)}")

    sections = [
        ("1. Uploaded Keywords", raw_keywords),
        ("2. Cleaned Keywords", cleaned),
        ("3. Keyword Clusters", [", ".join(c["keywords"]) for c in clusters]),
        ("4. Suggested Post Ideas", [f"{i['cluster']}: {i['idea']}" for i in ideas])
    ]

    for title, items in sections:
        y = section_title(title, y - 30)
        for item in items:
            if y < 100:
                c.showPage()
                y = height - 60
            c.drawString(60, y, f"- {item}")
            y -= 15

    y = section_title("5. Generated Outlines", y - 30)
    for outline in outlines:
        if y < 100:
            c.showPage()
            y = height - 60
        c.setFont("Helvetica-Bold", 12)
        c.drawString(60, y, outline["cluster"])
        y -= 15
        c.setFont("Helvetica", 11)
        for h in outline.get("outline", []):
            if y < 100:
                c.showPage()
                y = height - 60
            c.drawString(70, y, f"- {h}")
            y -= 12
        for src in outline.get("sources", []):
            if y < 100:
                c.showPage()
                y = height - 60
            c.setFont("Helvetica-Oblique", 10)
            c.drawString(70, y, f"Source: {src}")
            y -= 10
        y -= 15

    c.save()
    return path

# ---------------- Slack Message Handler ----------------
@app.event("message")
def handle_message_events(body, say, logger):
    text = body.get("event", {}).get("text", "")
    if not text:
        return

    df = slack_input_to_dataframe(text)
    keywords = df['keyword'].tolist()
    if not keywords:
        say("⚠️ No valid keywords found.")
        return

    session_keywords.clear()
    session_keywords.extend(keywords)

    say(f"🔹 Keywords parsed: {session_keywords}")
    say("🔹 Starting keyword processing...")

    cleaned = clean_keywords(session_keywords)
    clusters = cluster_keywords(cleaned)
    ideas = generate_post_idea(clusters)
    outlines = fetch_top_results(clusters)
    pdf_path = generate_pdf_report(session_keywords, cleaned, clusters, outlines, ideas)

    say(f"✅ Pipeline complete. PDF generated at `{pdf_path}`")
    try:
        send_pdf_via_email(pdf_path, "shahlanoura02@gmail.com")
        say("✅ Email sent successfully.")
    except Exception as e:
        logger.error(e)
        say(f"⚠️ Failed to send email: {e}")

