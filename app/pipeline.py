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
from collections import Counter
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
def parse_keywords_from_text(text):
    """
    Parse keywords from various input formats
    """
    keywords = []
    text = text.strip()
    
    print(f"DEBUG: Parsing text: '{text}'")
    
    # Try Python list format first
    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = ast.literal_eval(text)
            if isinstance(parsed, list):
                keywords = [str(item).strip() for item in parsed if item]
                print(f"DEBUG: Parsed as Python list: {keywords}")
        except:
            print("DEBUG: Failed to parse as Python list")
    
    # If no keywords from list parsing, try comma separation
    if not keywords and ',' in text:
        keywords = [kw.strip().strip('\"\'') for kw in text.split(',') if kw.strip()]
        print(f"DEBUG: Parsed as comma-separated: {keywords}")
    
    # If still no keywords, try space separation
    if not keywords:
        keywords = [kw.strip() for kw in text.split() if kw.strip()]
        print(f"DEBUG: Parsed as space-separated: {keywords}")
    
    return [kw for kw in keywords if kw]

def clean_keywords(raw_keywords):
    """
    Keep all keywords including fruits, just clean basic formatting
    """
    cleaned = []
    seen = set()
    for kw in raw_keywords:
        if not kw:
            continue
        kw = kw.strip().lower()
        kw = re.sub(r'[^a-zA-Z\s-]', '', kw)
        kw = ' '.join([w for w in kw.split() if w not in STOPWORDS and not w.isdigit()])
        kw = kw.strip()
        
        # Keep all keywords including fruits, just remove duplicates
        if kw and kw not in seen and len(kw) > 1:
            seen.add(kw)
            cleaned.append(kw)
    return cleaned

def detect_cluster_category(keywords):
    """
    Better category detection based on cluster content with scoring
    """
    keyword_text = ' '.join(keywords).lower()
    
    # Define categories with weighted indicators
    categories = {
        "Technology": {
            'indicators': ['python', 'javascript', 'react', 'vue', 'programming', 'coding', 
                          'software', 'cloud', 'data', 'natural language', 'processing',
                          'deep', 'tutorials', 'frameworks', 'computing', 'algorithm',
                          'development', 'code'],
            'score': 0
        },
        "Digital Marketing": {
            'indicators': ['seo', 'marketing', 'social media', 'content', 'strategy', 
                          'campaign', 'email', 'advertising', 'affiliate', 'optimization',
                          'keyword', 'clustering', 'outline', 'generation', 'ranking',
                          'google', 'blog', 'post', 'ideas', 'trends', 'factors'],
            'score': 0
        },
        "Tech Devices": {
            'indicators': ['laptop', 'smartphone', 'tablet', 'device', 'hardware', 
                          'gadget', 'smartwatch', 'earbuds', 'monitor', 'keyboard', 'mouse',
                          'printer', 'wireless', 'bluetooth', 'speaker', 'console', 'gaming',
                          'external', 'drive', 'computer'],
            'score': 0
        },
        "AI & Data Science": {
            'indicators': ['ai', 'machine learning', 'deep learning', 'data', 'visualization',
                          'natural language processing', 'automation', 'neural', 'intelligence',
                          'machine', 'learning'],
            'score': 0
        },
        "Food & Health": {
            'indicators': ['apple', 'banana', 'orange', 'mango', 'grape', 'pineapple', 
                          'strawberry', 'watermelon', 'kiwi', 'blueberry', 'raspberry',
                          'fruit', 'food', 'nutrition', 'health', 'diet', 'fitness'],
            'score': 0
        },
        "Cybersecurity": {
            'indicators': ['cybersecurity', 'security', 'network', 'monitoring', 'tools', 'firewall'],
            'score': 0
        }
    }
    
    # Score each category
    for category, data in categories.items():
        for indicator in data['indicators']:
            if indicator in keyword_text:
                data['score'] += 1
        # Bonus for exact matches
        for kw in keywords:
            if kw.lower() in data['indicators']:
                data['score'] += 2
    
    # Find best category
    best_category = "General"
    best_score = 0
    
    for category, data in categories.items():
        if data['score'] > best_score:
            best_score = data['score']
            best_category = category
    
    return best_category if best_score > 0 else "General"

def generate_descriptive_cluster_name(keywords, embeddings):
    """
    Generate meaningful cluster names based on content analysis
    """
    if not keywords:
        return "General Topics"
    
    # For single keyword clusters, just return the keyword titleized
    if len(keywords) == 1:
        return keywords[0].title()
    
    # For 2-3 keywords, combine them meaningfully
    if len(keywords) <= 3:
        category = detect_cluster_category(keywords)
        if category == "AI & Data Science":
            return "AI & Machine Learning"
        elif category == "Technology":
            if 'python' in keywords:
                return "Python Programming"
            elif any(js in keywords for js in ['javascript', 'react', 'vue', 'js']):
                return "Web Development"
            else:
                return "Technology & Development"
        elif category == "Digital Marketing":
            if any(seo in keywords for seo in ['seo', 'optimization']):
                return "SEO & Optimization"
            elif any(social in keywords for social in ['social', 'media']):
                return "Social Media Marketing"
            else:
                return "Digital Marketing"
        else:
            # Combine the keywords
            return " & ".join([kw.title() for kw in keywords[:2]])
    
    # Rest of your existing code for larger clusters...
    # Flatten and count all words in the cluster
    all_words = ' '.join(keywords).split()
    word_freq = Counter(all_words)
    
    # Remove common stopwords from consideration
    common_words = {'content', 'marketing', 'digital', 'online', 'web', 'guide', 
                   'tips', 'best', 'ways', 'how', 'what', 'why', 'get', 'use',
                   'like', 'know', 'time', 'good', 'new', 'way', 'make', 'using'}
    
    # Find the most representative words
    candidate_words = [word for word, count in word_freq.most_common(15) 
                      if word not in STOPWORDS and word not in common_words and len(word) > 2]
    
    if not candidate_words:
        # Fallback: use the keyword closest to centroid
        centroid = np.mean(embeddings, axis=0)
        distances = cdist([centroid], embeddings, metric='cosine')[0]
        return keywords[np.argmin(distances)].title()
    
    # Get category for better naming
    category = detect_cluster_category(keywords)
    
    # Build descriptive name based on category and content
    main_keywords = [kw for kw in keywords if kw not in common_words and kw not in STOPWORDS]
    
    if category == "Technology":
        if 'python' in keywords:
            return "Python Programming & Development"
        elif any(js in keywords for js in ['javascript', 'react', 'vue', 'js']):
            return "JavaScript Frameworks & Web Development"
        elif any(web in keywords for web in ['web', 'frontend', 'backend']):
            return "Web Development Technologies"
        else:
            return "Software Development"
    
    elif category == "Digital Marketing":
        if any(seo in keywords for seo in ['seo', 'ranking', 'google', 'optimization']):
            return "SEO & Search Optimization"
        elif any(social in keywords for social in ['social', 'media']):
            return "Social Media Marketing"
        elif any(content in keywords for content in ['content', 'blog', 'post']):
            return "Content Marketing & Strategy"
        else:
            return "Digital Marketing Strategies"
    
    elif category == "AI & Data Science":
        if any(ai in keywords for ai in ['ai', 'machine', 'learning']):
            return "AI & Machine Learning"
        elif any(data in keywords for data in ['data', 'visualization']):
            return "Data Science & Analytics"
        else:
            return "Artificial Intelligence"
    
    relevant_words = [w for w in candidate_words if w not in common_words][:2]
    if len(relevant_words) >= 2:
        return f"{relevant_words[0].title()} & {relevant_words[1].title()}"
    else:
        return f"{candidate_words[0].title()} Topics"

def cluster_keywords(cleaned_keywords, max_clusters=8):
    """
    Improved clustering with better separation and no duplicates
    """
    if len(cleaned_keywords) < 2:
        # For single keyword, just return it as a cluster
        if len(cleaned_keywords) == 1:
            return [{
                "cluster_name": cleaned_keywords[0].title(), 
                "keywords": cleaned_keywords,
                "category": detect_cluster_category(cleaned_keywords)
            }]
        return [{"cluster_name": "General Topics", "keywords": cleaned_keywords, "category": "General"}]
    
    model = SentenceTransformer("paraphrase-albert-small-v2")
    embeddings = model.encode(cleaned_keywords)
    
    # For small number of keywords, use fewer clusters
    if len(cleaned_keywords) <= 5:
        n_clusters = min(2, len(cleaned_keywords))
    else:
        n_clusters = min(max_clusters, max(2, len(cleaned_keywords) // 8))
    
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = kmeans.fit_predict(embeddings)

    clusters = {}
    for kw, label, emb in zip(cleaned_keywords, labels, embeddings):
        clusters.setdefault(label, []).append((kw, emb))

    final_clusters = []
    used_keywords = set()
    
    for label, kw_emb_list in clusters.items():
        if len(kw_emb_list) < 1:  # Allow single keyword clusters for small datasets
            continue
            
        keywords, embs = zip(*kw_emb_list)
        
        # Skip if all keywords are already used (avoid duplicates)
        if all(kw in used_keywords for kw in keywords):
            continue
            
        cluster_name = generate_descriptive_cluster_name(keywords, embs)
        category = detect_cluster_category(keywords)
        
        # Check if we already have a cluster with same name
        existing_names = [c["cluster_name"] for c in final_clusters]
        if cluster_name in existing_names:
            # Append a number to make it unique
            counter = 1
            new_name = f"{cluster_name} {counter}"
            while new_name in existing_names:
                counter += 1
                new_name = f"{cluster_name} {counter}"
            cluster_name = new_name
        
        final_clusters.append({
            "cluster_name": cluster_name, 
            "keywords": list(keywords),
            "category": category
        })
        
        # Mark these keywords as used
        used_keywords.update(keywords)

    # Handle any leftover keywords - create individual clusters for them
    leftover_keywords = [kw for kw in cleaned_keywords if kw not in used_keywords]
    for kw in leftover_keywords:
        final_clusters.append({
            "cluster_name": kw.title(),
            "keywords": [kw],
            "category": detect_cluster_category([kw])
        })

    return final_clusters

def generate_post_idea(clusters):
    ideas = []
    
    # Enhanced templates with better specificity
    templates = {
        "Technology": [
            "Getting Started with {keyword}: A Complete Beginner's Guide",
            "Advanced {keyword} Techniques for Experienced Developers",
            "The Future of {keyword}: Trends and Predictions for 2025",
            "Common {keyword} Mistakes and How to Avoid Them",
            "Building Your First Project with {keyword}",
            "Mastering {keyword}: From Basics to Advanced Concepts",
            "{keyword} Best Practices Every Developer Should Know"
        ],
        "Digital Marketing": [
            "{keyword} Strategy That Actually Converts in 2025",
            "How to Master {keyword} for Business Growth",
            "The Complete Guide to {keyword} Best Practices", 
            "5 {keyword} Tactics That Will Boost Your Traffic",
            "Avoid These Common {keyword} Mistakes",
            "Data-Driven {keyword} Strategies for 2025",
            "The Ultimate {keyword} Checklist for Success",
            "{keyword} Trends You Can't Ignore This Year"
        ],
        "Tech Devices": [
            "The Ultimate {keyword} Buying Guide for 2025",
            "Top 5 {keyword} for Productivity and Performance", 
            "{keyword} Comparison: Which One Should You Choose?",
            "Essential {keyword} Accessories You Need",
            "How to Get the Most Out of Your {keyword}",
            "{keyword} Maintenance and Troubleshooting Guide",
            "Expert Reviews: The Best {keyword} on the Market"
        ],
        "AI & Data Science": [
            "Getting Started with {keyword}: A Practical Guide",
            "How {keyword} is Transforming Industries in 2025",
            "{keyword} Applications for Business Growth", 
            "The Future of {keyword}: What to Expect",
            "Implementing {keyword} in Your Projects",
            "{keyword} Tools and Frameworks Comparison"
        ],
        "Food & Health": [
            "Health Benefits of {keyword} You Need to Know",
            "The Complete Guide to {keyword} Nutrition",
            "How to Incorporate {keyword} into Your Diet",
            "Top 10 Facts About {keyword}",
            "{keyword} Recipes and Preparation Tips",
            "Why {keyword} is Essential for Healthy Living"
        ],
        "Cybersecurity": [
            "Essential {keyword} Practices Every Business Needs",
            "How to Protect Your Systems with {keyword}",
            "The Complete {keyword} Checklist for 2025", 
            "Common {keyword} Threats and Prevention",
            "Building a Robust {keyword} Strategy",
            "{keyword} Tools for Small Businesses"
        ],
        "General": [
            "The Complete Guide to Understanding {keyword}",
            "How {keyword} is Changing the Industry", 
            "Beginner's Roadmap to {keyword}",
            "5 Innovative Ways to Use {keyword}",
            "Why {keyword} Matters in 2025",
            "Expert Insights on {keyword}"
        ]
    }

    for cluster in clusters:
        keyword = cluster["cluster_name"]
        category = cluster.get("category", "General")
        template_group = templates.get(category, templates["General"])
        template = random.choice(template_group)
        idea = template.format(keyword=keyword)
        
        ideas.append({
            "cluster": keyword,
            "idea": idea,
            "category": category
        })

    return ideas

def extract_headings(url):
    try:
        r = requests.get(url, timeout=8, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(r.text, 'html.parser')
        headings = []
        for h in soup.select('h1,h2,h3'):
            text = h.get_text(strip=True)
            text = re.sub(r'^[\d\.\#\s]+', '', text)
            if not text or len(text) < 5 or len(text) > 120:
                continue
            if any(x in text.lower() for x in ["login", "cookie", "policy", "subscribe", "copyright", "terms"]):
                continue
            headings.append(text)
        return headings[:10]
    except Exception:
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

def generate_adaptive_outline(keyword, category=None, keywords_list=None):
    category = (category or "General").strip().capitalize()
    cluster_keywords = keywords_list or []

    # Specific outline for fruits
    if "Fruits" in keyword or any(fruit in cluster_keywords for fruit in ['apple', 'banana', 'orange', 'mango', 'grape', 'pineapple', 'strawberry', 'watermelon', 'kiwi', 'blueberry']):
        return [
            "Introduction to Fresh Fruits: Nutritional Powerhouses",
            "Top 10 Health Benefits of Eating Fresh Fruits Daily",
            "Seasonal Fruit Guide: What to Eat When",
            "How to Select and Store Fruits for Maximum Freshness",
            "Nutritional Comparison: Different Types of Fruits",
            "Delicious Fruit Recipes and Serving Ideas",
            "Organic vs Conventional Fruits: Making the Right Choice",
            "Incorporating Fruits into a Balanced Diet"
        ]
    
    elif "Mobile Devices" in keyword:
        return [
            f"Introduction to {keyword}: Current Market Overview",
            f"Top {keyword} Brands and Models for 2025",
            f"Key Features to Consider When Buying {keyword}",
            f"Performance Comparison: {keyword} Specifications",
            f"Accessories and Must-Have Add-ons for {keyword}",
            f"Maintenance and Care Tips for {keyword}",
            f"Future Trends in {keyword} Technology",
            f"Expert Recommendations and User Reviews"
        ]
    
    elif "JavaScript" in keyword or "Web Development" in keyword:
        return [
            f"Understanding {keyword}: Core Concepts Explained",
            f"Popular {keyword} Tools and Frameworks",
            f"Getting Started with {keyword}: Setup Guide",
            f"Best Practices for {keyword} Development",
            f"Common Challenges and Solutions in {keyword}",
            f"Advanced {keyword} Techniques and Patterns",
            f"Performance Optimization for {keyword}",
            f"Future of {keyword}: Emerging Trends"
        ]
    
    elif "SEO" in keyword:
        return [
            f"What is {keyword} and Why It Matters in 2025",
            f"Core Principles of Effective {keyword}",
            f"Technical {keyword}: Website Optimization",
            f"Content Strategy for {keyword} Success",
            f"Keyword Research and Analysis for {keyword}",
            f"Measuring {keyword} Performance: Analytics & KPIs",
            f"Local vs. Global {keyword} Strategies",
            f"Future Trends in {keyword} and Algorithm Updates"
        ]
    
    elif "Social Media Marketing" in keyword:
        return [
            f"Understanding {keyword} in the Digital Age",
            f"Platform-Specific {keyword} Strategies",
            f"Content Creation for {keyword} Success",
            f"Audience Engagement and Community Building",
            f"Analytics and Measuring {keyword} ROI",
            f"Paid Advertising vs Organic {keyword}",
            f"Influencer Collaboration in {keyword}",
            f"Emerging Trends in {keyword} for 2025"
        ]
    
    elif category == "Technology":
        return [
            f"Introduction to {keyword}: Core Concepts",
            f"Key Technologies and Tools in {keyword}",
            f"Getting Started with {keyword}: Beginner's Guide",
            f"Best Practices and Methodologies in {keyword}",
            f"Real-World Applications of {keyword}",
            f"Career Opportunities in {keyword}",
            f"Future Trends and Innovations in {keyword}",
            f"Resources for Learning {keyword}"
        ]
    
    else:
        return [
            f"Overview and Significance of {keyword}",
            f"Key Concepts and Principles of {keyword}",
            f"Practical Applications of {keyword}",
            f"Getting Started with {keyword}",
            f"Best Practices and Expert Tips for {keyword}",
            f"Future Outlook and Trends in {keyword}",
            f"Resources for Further Learning about {keyword}"
        ]

def fetch_top_results(clusters, top_n_results=3):
    outlines = []

    def process_cluster(cluster):
        keyword = cluster["cluster_name"]
        category = cluster.get("category", "General")
        cluster_keywords = cluster["keywords"]

        serp_results = fetch_top_search(keyword)[:top_n_results]

        useful_results = [
            r for r in serp_results
            if re.search(
                r"(wikipedia|medium|towardsdatascience|geeksforgeeks|tutorialspoint|ibm|microsoft|coursera|udemy|hubspot|forbes|techcrunch|moz|semrush|ahrefs|healthline|medicalnewstoday|webmd)",
                r["link"], re.I)
        ]

        headings, sources = [], []
        if useful_results:
            with ThreadPoolExecutor(max_workers=3) as executor:
                future_to_url = {executor.submit(extract_headings, r["link"]): r["link"] for r in useful_results}
                for future in as_completed(future_to_url):
                    result = future.result()
                    if result:
                        headings.extend(result)
                        sources.append(future_to_url[future])

        # Remove duplicates while preserving order
        seen_headings = set()
        unique_headings = []
        for h in headings:
            if h not in seen_headings:
                seen_headings.add(h)
                unique_headings.append(h)

        # If still no headings found or too few, use adaptive outline
        if not unique_headings or len(unique_headings) < 4:
            unique_headings = generate_adaptive_outline(keyword, category, cluster_keywords)

        return {
            "cluster": cluster["cluster_name"], 
            "outline": unique_headings[:8],
            "sources": sources[:3],
            "category": category
        }

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(process_cluster, c) for c in clusters]
        for f in as_completed(futures):
            outlines.append(f.result())

    return outlines

def generate_pdf_report(raw_keywords, cleaned, clusters, outlines, ideas, filename="content_report.pdf"):
    temp = os.path.join(os.getcwd(), "reports")
    os.makedirs(temp, exist_ok=True)
    path = os.path.join(temp, filename)
    c = canvas.Canvas(path, pagesize=A4)
    width, height = A4

    def title(text, size=18, color=colors.darkblue, y_offset=30):
        nonlocal y
        c.setFont("Helvetica-Bold", size)
        c.setFillColor(color)
        c.drawString(50, y, text)
        y -= y_offset
        c.setFillColor(colors.black)

    def paragraph(text, size=11, line_gap=14):
        nonlocal y
        c.setFont("Helvetica", size)
        # Simple text wrapping
        words = text.split()
        lines = []
        current_line = []
        
        for word in words:
            test_line = ' '.join(current_line + [word])
            if c.stringWidth(test_line, "Helvetica", size) < 500:
                current_line.append(word)
            else:
                lines.append(' '.join(current_line))
                current_line = [word]
        if current_line:
            lines.append(' '.join(current_line))
        
        for line in lines:
            if y < 100:
                c.showPage()
                y = height - 60
            c.drawString(50, y, line.strip())
            y -= line_gap

    # ----- Header -----
    y = height - 60
    title("AI Content Pipeline Report")
    paragraph(f"Total Raw Keywords: {len(raw_keywords)}")
    paragraph(f"Total Cleaned Keywords: {len(cleaned)}")
    paragraph(f"Clusters Formed: {len(clusters)}")
    y -= 20

    # ----- Uploaded Keywords -----
    title("1. Uploaded Keywords", 14)
    paragraph("These are the original keywords provided as input:")
    paragraph(", ".join(raw_keywords))
    y -= 15

    # ----- Cleaned Keywords -----
    title("2. Cleaned Keywords", 14)
    paragraph("After removing duplicates, punctuation, and stopwords:")
    paragraph(", ".join(cleaned))
    y -= 15

    # ----- Clusters -----
    title("3. Keyword Clusters", 14)
    paragraph("Keywords were grouped into meaningful clusters based on semantic similarity:")
    for c_obj in clusters:
        cluster_kw = ", ".join(c_obj["keywords"][:10])
        category = c_obj.get("category", "General")
        paragraph(f"• {c_obj['cluster_name']} ({category}): {cluster_kw}" + 
                 ("..." if len(c_obj["keywords"]) > 10 else ""))
    y -= 15

    # ----- Post Ideas -----
    title("4. Suggested Post Ideas", 14)
    paragraph("Here are AI-generated blog post ideas for each cluster:")
    for i in ideas:
        paragraph(f"- {i['cluster']}: {i['idea']}")
    y -= 15

    # ----- Outlines -----
    title("5. Generated Outlines", 14)
    paragraph("Below are content outlines and reference sources for each topic:")
    for outline in outlines:
        title(f"• {outline['cluster']} ({outline.get('category', 'General')})", 
              12, color=colors.darkgreen, y_offset=20)
        
        for i, h in enumerate(outline.get("outline", [])[:6], 1):
            paragraph(f"{i}. {h}", size=10, line_gap=12)
        
        if outline.get("sources"):
            paragraph("Reference Sources:", size=9, line_gap=10)
            for src in outline.get("sources", [])[:2]:
                display_src = src[:80] + "..." if len(src) > 80 else src
                paragraph(f"• {display_src}", size=8, line_gap=8)
        y -= 15

    c.save()
    return path

# ---------------- Slack Slash Command Handler ----------------
@app.command("/keyword")
def handle_keyword_command(ack, respond, command, logger):
    # Acknowledge the command request
    ack()
    
    text = command.get('text', '').strip()
    
    if not text:
        respond("❌ Please provide keywords after the command. Example: `/keyword ai,machine,learning` or `/keyword ['ai','machine','learning']`")
        return
    
    respond(f"🔹 Processing your keywords: `{text}`")
    
    # Parse keywords
    keywords = parse_keywords_from_text(text)
    
    if not keywords:
        respond("""
❌ I couldn't find any keywords to process. Please use one of these formats:

• *List format:* `/keyword ['ai','machine','learning']`
• *Comma-separated:* `/keyword ai,machine,learning`  
• *Space-separated:* `/keyword ai machine learning`

Try: `/keyword ['ai','machine','learning']`
""")
        return

    respond(f"✅ Found {len(keywords)} keywords: {', '.join(keywords)}")
    
    try:
        # Process pipeline
        cleaned = clean_keywords(keywords)
        respond(f"🔹 Cleaning complete: {len(cleaned)} keywords")
        
        clusters = cluster_keywords(cleaned)
        respond(f"🔹 Clustering complete: {len(clusters)} meaningful clusters formed")
        
        ideas = generate_post_idea(clusters)
        outlines = fetch_top_results(clusters)
        
        pdf_path = generate_pdf_report(keywords, cleaned, clusters, outlines, ideas)

        respond("✅ Pipeline complete! PDF generated and sent via email.")
        respond("📊 Report Summary:")
        respond(f"   • Cleaned Keywords: {len(cleaned)}")
        respond(f"   • Content Clusters: {len(clusters)}")
        for cluster in clusters:
            respond(f"   • {cluster['cluster_name']} ({cluster['category']}): {len(cluster['keywords'])} keywords")

        # Send email
        try:
            send_pdf_via_email(pdf_path, "shahlanoura02@gmail.com")
            respond("✅ Email sent successfully!")
        except Exception as e:
            logger.error(f"Email error: {e}")
            respond(f"⚠️ PDF generated but email failed: {e}")

    except Exception as e:
        logger.error(f"Pipeline error: {e}")
        respond(f"❌ Pipeline failed: {str(e)}")

# ---------------- Slack Message Handler (fallback) ----------------
@app.event("message")
def handle_message_events(body, say, logger):
    text = body.get("event", {}).get("text", "")
    if not text:
        return

    say("👋 I see you sent a message! To process keywords, please use the slash command: `/keyword your_keywords_here`")
    say("Example: `/keyword ai,machine,learning`")

