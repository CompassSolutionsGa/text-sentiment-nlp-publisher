import json
import os
import sys
import time
from pathlib import Path
import requests

ARTICLES_FILE = Path("articles.json")
DEVTO_API_URL = "https://dev.to/api/articles"

DEVTO_API_KEY = os.getenv("DEVTO_API_KEY")
MAX_PER_RUN = int(os.getenv("MAX_ARTICLES_PER_RUN", "3"))
DELAY_BETWEEN_POSTS = 300  # 5 minutes


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


def publish_to_devto(article):
    if not DEVTO_API_KEY:
        print("DEVTO_API_KEY not set.")
        sys.exit(1)

    # Clean tags safely
    tags = article.get("tags", [])
    clean_tags = []
    for tag in tags:
        t = "".join(c for c in tag.lower().strip() if c.isalnum() or c == "-")
        if t:
            clean_tags.append(t)

    payload = {
        "article": {
            "title": article["title"],
            "published": True,
            "body_markdown": article["body_markdown"],
            "canonical_url": article.get("canonical_url"),
            "tags": clean_tags[:4],  # Dev.to allows max 4 tags
        }
    }

    headers = {
        "Content-Type": "application/json",
        "api-key": DEVTO_API_KEY,
    }

    response = requests.post(DEVTO_API_URL, json=payload, headers=headers)

    if response.status_code in (200, 201):
        data = response.json()
        print("Published to Dev.to:", data.get("url"))
        return data.get("url")

    print("Failed to publish to Dev.to:", response.text)
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

            print(f"Waiting 5 minutes before next Dev.to post...")
            time.sleep(DELAY_BETWEEN_POSTS)

        else:
            print("Skipping this article due to error.")
            article["devto_published"] = True  # mark invalid to avoid retries

    save_articles(articles)
    print(f"Dev.to publish run complete. Published {published_count} article(s).")


if __name__ == "__main__":
    main()
