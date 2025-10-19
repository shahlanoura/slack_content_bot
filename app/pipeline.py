import re
import os
import random
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from sentence_transformers import SentenceTransformer
from sklearn.cluster import KMeans
from concurrent.futures import ThreadPoolExecutor, as_completed

load_dotenv()

# Keyword Cleaning
def clean_keywords(raw_keywords):
    cleaned = []
    seen = set()
    for kw in raw_keywords:
        if not kw:
            continue
        kw = kw.strip().lower()
        kw = re.sub(r'\s+', ' ', kw)
        kw = re.sub(r'[^a-zA-Z\s-]', '', kw)
        kw = ' '.join([word for word in kw.split() if not word.isdigit()])
        kw = kw.strip('-').strip()
        kw = re.sub(r'[^\w\s-]', '', kw)
        if kw and kw not in seen and len(kw) > 1:
            seen.add(kw)
            cleaned.append(kw)
    return cleaned

#  Keyword Clustering 
def cluster_keywords(cleaned_keywords):
    if len(cleaned_keywords) < 2:
        return [{"cluster_name": "Misc", "keywords": cleaned_keywords}]
    model = SentenceTransformer("paraphrase-albert-small-v2")
    embeddings = model.encode(cleaned_keywords)
    n_clusters = min(5, max(1, len(cleaned_keywords) // 3))
    kmeans = KMeans(n_clusters=n_clusters, random_state=42).fit(embeddings)
    clusters = {}
    for kw, label in zip(cleaned_keywords, kmeans.labels_):
        clusters.setdefault(label, []).append(kw)
    return [{"cluster_name": f"Cluster {i+1}", "keywords": kws} for i, kws in enumerate(clusters.values())]

# Post Idea Generation 
def generate_post_idea(clusters):
    ideas = []
    for cluster in clusters:
        keyword = cluster["keywords"][0]
        idea = random.choice([
            f"Top 10 tips for {keyword}",
            f"Beginner's guide to {keyword}",
            f"Why {keyword} matters in 2025",
            f"How to master {keyword}",
        ])
        ideas.append({"cluster": cluster["cluster_name"], "idea": idea})
    return ideas

# Fetch & Parse 
def extract_headings(url):
    try:
        r = requests.get(url, timeout=5, headers={'User-Agent':'Mozilla/5.0'})
        r.encoding = 'utf-8'
        soup = BeautifulSoup(r.text, 'html.parser')
        headings = []
        for h in soup.select('h1,h2,h3')[:10]:
            text = h.get_text(strip=True)
            text = re.sub(r'^[\d\.#\s]+', '', text)
            text = re.sub(r'[\+\-\*\.\/\\]+$', '', text)
            text = ''.join(c for c in text if c.isprintable())
            if 5 < len(text) < 200:
                headings.append(text)
        return headings
    except Exception as e:
        print(f"[extract_headings] Error: {e} ({url})")
        return []

def fetch_top_search(keyword, top_n=3):
    api_key = os.getenv("SERPER_API_KEY")
    url = "https://google.serper.dev/search"
    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    payload = {"q": keyword, "num": top_n, "gl": "us"}
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=5)
        data = r.json()
        results = []
        for item in data.get("organic", [])[:top_n]:
            if item.get("title") and item.get("link"):
                results.append({"title": item["title"], "link": item["link"], "snippet": item.get("snippet","")})
        return results
    except Exception as e:
        print(f"[fetch_top_search] Error for '{keyword}': {e}")
        return []

#  Fetch Top Results 
def fetch_top_results(clusters, top_n_results=3):
    outlines = []

    def process_cluster(cluster):
        keyword = cluster["keywords"][0]
        serp_results = fetch_top_search(keyword)[:top_n_results]
        headings = []
        sources = []
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_to_url = {executor.submit(extract_headings, r["link"]): r["link"] for r in serp_results}
            for future in as_completed(future_to_url):
                headings.extend(future.result())
                sources.append(future_to_url[future])
        return {"cluster": cluster["cluster_name"], "outline": headings or ["Intro","Main points","Conclusion"], "sources": sources}

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(process_cluster, c) for c in clusters]
        for f in as_completed(futures):
            outlines.append(f.result())

    return outlines

# PDF Generation 
def generate_pdf_report(raw_keywords, cleaned, clusters, outlines, ideas):
    path = os.path.join("\temp", "report.pdf")
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

    # Sections
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

    # Outlines
    y = section_title("5. Generated Outlines", y - 30)
    for outline in outlines:
        if y < 100:
            c.showPage()
            y = height - 60
        c.setFont("Helvetica-Bold", 12)
        c.drawString(60, y, outline["cluster"])
        y -= 15
        c.setFont("Helvetica", 11)
        for h in outline.get("outline", ["Intro","Main points","Conclusion"]):
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

