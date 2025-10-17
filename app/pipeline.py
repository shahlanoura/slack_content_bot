import re
import os
import tempfile
import random
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib import colors
from sentence_transformers import SentenceTransformer
from sklearn.cluster import KMeans

load_dotenv()


# Keyword cleaning
def clean_keywords(raw_keywords):
    cleaned = []
    seen = set()
    
    for kw in raw_keywords:
        if not kw:
            continue
            
        # Convert to lowercase and strip
        kw = kw.strip().lower()
        
        # Remove extra whitespace
        kw = re.sub(r'\s+', ' ', kw)
        
        # Remove ALL numbers and special characters
        kw = re.sub(r'[^a-zA-Z\s-]', '', kw)
        
        # Remove words that are just numbers
        kw = ' '.join([word for word in kw.split() if not word.isdigit()])
        
        # Remove trailing/leading hyphens and spaces
        kw = kw.strip('-').strip()
        
        # Final cleanup - remove any remaining special characters
        kw = re.sub(r'[^\w\s-]', '', kw)
        
        if kw and kw not in seen and len(kw) > 1:
            seen.add(kw)
            cleaned.append(kw)
            
    return cleaned


# Keyword clustering

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


# Post ideas generation

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


# Extract headings from URL

def extract_headings(url):
    try:
        r = requests.get(url, timeout=10, headers={'User-Agent':'Mozilla/5.0'})
        r.encoding = 'utf-8'  # Force UTF-8 encoding
        soup = BeautifulSoup(r.text, 'html.parser')
        headings = []
        for h in soup.select('h1,h2,h3')[:10]:
            text = h.get_text(strip=True)
            # Clean up the text - remove numbers/symbols at start and fix encoding
            text = re.sub(r'^[\d\.#\s]+', '', text)
            # Remove common unwanted patterns
            text = re.sub(r'[\+\-\*\.\/\\]+$', '', text)
            # Fix encoding issues by keeping only printable characters
            text = ''.join(char for char in text if char.isprintable())
            if text and len(text) > 5 and len(text) < 200:  # Filter out very short
                headings.append(text)
        return headings
    except Exception as e:
        print(f"Error extracting headings from {url}: {e}")
        return []



def fetch_top_search(keyword, top_n=5):  
    api_key = os.getenv("SERPER_API_KEY")
    url = "https://google.serper.dev/search"
    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    payload = {
        "q": keyword,
        "num": top_n,
        "gl": "us"  
    }

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=15)
        data = r.json()
        
        results = []
        for item in data.get("organic", [])[:top_n]:
            # Only include high-quality results
            if item.get("title") and item.get("link"):
                results.append({
                    "title": item.get("title"),
                    "link": item.get("link"),
                    "snippet": item.get("snippet", "")
                })
        return results
    except Exception as e:
        print(f"Error fetching search results for '{keyword}': {e}")
        return []


# Fetch outlines for clusters

def fetch_top_results(clusters, top_n_results=3):
    """
    Generate outlines for each cluster by fetching top search results
    and extracting headings.
    """
    outlines = []

    for cluster in clusters:
        keyword = cluster["keywords"][0]  
        serp_results = fetch_top_search(keyword)[:top_n_results]

        headings = []
        sources = []

        for result in serp_results:
            url = result.get("link")
            if url:
                page_headings = extract_headings(url)
                if page_headings:
                    headings.extend(page_headings)
                sources.append(url)

        outlines.append({
            "cluster": cluster["cluster_name"],
            "outline": headings if headings else ["Intro", "Main points", "Conclusion"],
            "sources": sources
        })

    return outlines


# PDF report generation
def generate_pdf_report(raw_keywords, cleaned, clusters, outlines, ideas):
    path = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name
    c = canvas.Canvas(path, pagesize=A4)
    width, height = A4

    def section_title(title, y_pos):
        c.setFont("Helvetica-Bold", 14)
        c.setFillColor(colors.darkblue)
        c.drawString(50, y_pos, title)
        c.setFillColor(colors.black)
        return y_pos - 25

    # Start position
    y = height - 60
    
    # Title
    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, y, "AI Content Pipeline Report")
    c.setFont("Helvetica", 12)
    y -= 30
    c.drawString(50, y, f"Total Raw Keywords: {len(raw_keywords)}")
    y -= 15
    c.drawString(50, y, f"Total Cleaned Keywords: {len(cleaned)}")
    y -= 15
    c.drawString(50, y, f"Clusters Formed: {len(clusters)}")

    # Section 1: Uploaded Keywords
    y = section_title("1. Uploaded Keywords", y - 40)
    for kw in raw_keywords:
        if y < 100: 
            c.showPage()
            y = height - 60
        c.drawString(60, y, f"- {kw}")
        y -= 15

    # Section 2: Cleaned Keywords
    y = section_title("2. Cleaned Keywords", y - 30)
    for kw in cleaned:
        if y < 100: 
            c.showPage()
            y = height - 60
        c.drawString(60, y, f"- {kw}")
        y -= 15

    # Section 3: Keyword Clusters
    y = section_title("3. Keyword Clusters", y - 30)
    for cluster in clusters:
        if y < 100: 
            c.showPage()
            y = height - 60
        c.setFont("Helvetica-Bold", 12)
        c.drawString(60, y, f"{cluster['cluster_name']}:")
        c.setFont("Helvetica", 11)
        y -= 15
        if y < 100: 
            c.showPage()
            y = height - 60
        c.drawString(70, y, ", ".join(cluster["keywords"]))
        y -= 20

    # Section 4: Suggested Post Ideas
    y = section_title("4. Suggested Post Ideas", y - 30)
    for idea in ideas:
        if y < 100: 
            c.showPage()
            y = height - 60
        c.drawString(60, y, f"{idea['cluster']}: {idea['idea']}")
        y -= 15

    # Section 5: Generated Outlines
    y = section_title("5. Generated Outlines", y - 30)
    for outline in outlines:
        if y < 100: 
            c.showPage()
            y = height - 60
        c.setFont("Helvetica-Bold", 12)
        c.drawString(60, y, outline["cluster"])
        y -= 15
        
        c.setFont("Helvetica", 11)
        headings = outline.get("outline") or ["Intro", "Main points", "Conclusion"]
        for h in headings:
            if y < 100: 
                c.showPage()
                y = height - 60
            c.drawString(70, y, f"- {h}")
            y -= 12

        # Sources
        c.setFont("Helvetica-Oblique", 10)
        for src in outline.get("sources", []):
            if y < 100: 
                c.showPage()
                y = height - 60
            c.drawString(70, y, f"Source: {src}")
            y -= 10
        
        y -= 15

    c.save()
    return path