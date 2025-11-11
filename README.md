# AI Content Pipeline Slack Bot

**Version:** 1.0  
**Author:** Shahla Noura  

---

## Overview

Slack bot that takes keywords (text or CSV file) and generates a content pipeline report:
- Cleans and clusters keywords
- Generates content ideas
- Fetches top search results and headings
- Generates PDF report
- Sends report via Slack DM and email

---

## Features

- Keyword parsing from text & files
- Deduplication & cleaning
- Clustering using embeddings
- Post idea generation
- Outline generation from top search results
- PDF report creation
- Email integration

---

## Requirements

- Python >= 3.10  
- Slack App (Bot Token & Signing Secret)  
- Serper API Key  

Install dependencies:

```bash
pip install -r requirements.txt
