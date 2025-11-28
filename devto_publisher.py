import json
import os
import sys
import re
from pathlib import Path

import requests

ARTICLES_FILE = Path("articles.json")
DEVTO_API_URL = "https://dev.to/api/articles"

DEVTO_API_KEY = os.getenv("DEVTO_API_KEY")
MAX_PER_RUN = int(os.getenv("MAX_ARTICLES_PER_RUN", "3"))


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


def clean_devto_tags(raw_tags):
    """
    Dev.to rules:
      - max 4 tags
      - lowercase
      - only [a-z0-9] (no hyphens, spaces, etc.)
    """
    if not raw_tags:
        return []

    cleaned = []
    for tag in raw_tags:
        t = re.sub(r"[^a-z0-9]", "", str(tag).lower())
        if t and t not in cleaned:
            cleaned.append(t)
        if len(cleaned) == 4:
            break
    return cleaned


def publish_to_devto(article):
    if not DEVTO_API_KEY:
        print("DEVTO_API_KEY environment variable is not set.")
        sys.exit(1)

    raw_tags = article.get("tags", [])
    tags = clean_devto_tags(raw_tags)
    if not tags:
        tags = ["nlp"]

    payload = {
        "article": {
            "title": article["title"],
            "published": True,
            "body_markdown": article["body_markdown"],
            "canonical_url": article.get("canonical_url"),
            "tags": tags,
            "series": article.get("series"),
        }
    }

    headers = {
        "Content-Type": "application/json",
        "api-key": DEVTO_API_KEY,
    }

    response = requests.post(DEVTO_API_URL, json=payload, headers=headers)

    # Success
    if response.status_code in (200, 201):
        data = response.json()
        url = data.get("url")
        print("Published to Dev.to:", url)
        return url, True

    # Rate limit — stop the whole run so GitHub Actions fails fast
    if response.status_code == 429:
        print("Failed to publish to Dev.to: 429 rate limited. Stopping this run.")
        sys.exit(1)

    # Parse error message if possible
    try:
        err_json = response.json()
        err_msg = err_json.get("error", str(err_json))
    except Exception:
        err_msg = response.text

    print("Failed to publish to Dev.to:", response.status_code, err_msg)

    # If canonical already used, mark as published so we skip next runs
    if "canonical url has already been taken" in err_msg.lower():
        print("Article already exists with this canonical URL. Marking as devto_published and skipping.")
        return None, True

    # For validation errors (tags, etc.) DO NOT mark as published
    print("Skipping this article due to Dev.to validation error without marking as published.")
    return None, False


def main():
    articles = load_articles()
    published_count = 0

    while published_count < MAX_PER_RUN:
        article = get_next_unpublished_devto(articles)
        if not article:
            print("No unpublished Dev.to articles remaining.")
            break

        print(f"Publishing to Dev.to: {article['title']}")
        url, mark_published = publish_to_devto(article)

        if mark_published:
            article["devto_published"] = True
            if url:
                article["devto_url"] = url
            published_count += 1
        else:
            # Leave devto_published = False so you can fix the article and rerun
            break

    save_articles(articles)
    print(f"Dev.to publish run complete. Published {published_count} article(s).")


if __name__ == "__main__":
    main()
