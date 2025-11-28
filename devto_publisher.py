import json
import os
import sys
import re
import time
from pathlib import Path

import requests

ARTICLES_FILE = Path("articles.json")
DEVTO_API_URL = "https://dev.to/api/articles"

DEVTO_API_KEY = os.getenv("DEVTO_API_KEY")
MAX_PER_RUN = int(os.getenv("MAX_ARTICLES_PER_RUN", "3"))

# Retry settings for Dev.to 429 errors
MAX_RETRIES = 5
RETRY_DELAY = 20  # seconds


def load_articles():
    if not ARTICLES_FILE.exists():
        print("articles.json not found")
        sys.exit(1)
    with open(ARTICLES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_articles(articles):
    with open(ARTICLES_FILE, "w", encoding="utf-8") as f:
        json.dump(articles, f, indent=2, ensure_ascii=False)


def get_next_unpublished_devto(articles):
    for article in articles:
        if not article.get("devto_published", False):
            return article
    return None


def clean_tag(tag: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]", "", tag)
    return cleaned if cleaned else "nlp"


def publish_to_devto(article):

    if not DEVTO_API_KEY:
        print("DEVTO_API_KEY environment variable is not set.")
        sys.exit(1)

    raw_tags = article.get("tags", [])
    clean_tags = [clean_tag(t) for t in raw_tags][:4]

    payload = {
        "article": {
            "title": article["title"],
            "published": True,
            "body_markdown": article["body_markdown"],
            "canonical_url": article.get("canonical_url"),
            "tags": clean_tags,
            "series": article.get("series"),
        }
    }

    headers = {
        "Content-Type": "application/json",
        "api-key": DEVTO_API_KEY,
    }

    # Retry loop for 429 rate limits
    for attempt in range(1, MAX_RETRIES + 1):

        response = requests.post(DEVTO_API_URL, json=payload, headers=headers)

        if response.status_code == 429:
            print(f"Dev.to rate limit hit (429). Waiting {RETRY_DELAY}s before retry {attempt}/{MAX_RETRIES}...")
            time.sleep(RETRY_DELAY)
            continue

        if response.status_code not in (200, 201):
            print("Failed to publish to Dev.to:", response.status_code, response.text)
            return None

        # Success
        data = response.json()
        print("Published to Dev.to:", data.get("url"))
        return data.get("url")

    print("Dev.to publishing failed after max retries.")
    return None


def main():
    articles = load_articles()
    published_count = 0

    while published_count < MAX_PER_RUN:
        article = get_next_unpublished_devto(articles)
        if not article:
            print("No unpublished Dev.to articles remaining.")
            break

        print(f"Publishing to Dev.to: {article['title']}")
        url = publish_to_devto(article)

        if url:
            article["devto_published"] = True
            article["devto_url"] = url
            published_count += 1
        else:
            print("Skipping this article due to errors.")
            break

    save_articles(articles)
    print(f"Dev.to publish run complete. Published {published_count} article(s).")


if __name__ == "__main__":
    main()
