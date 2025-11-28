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


def clean_tags(raw_tags):
    """
    Dev.to is picky about tags. To be safe:
    - Only allow a–z and 0–9
    - Lowercase everything
    - Truncate to 20 chars
    - Max 4 tags
    """
    cleaned = []
    for t in raw_tags:
        slug = "".join(ch.lower() for ch in t if ch.isalnum())
        if not slug:
            continue
        cleaned.append(slug[:20])
        if len(cleaned) >= 4:
            break
    return cleaned


def publish_to_devto(article):
    if not DEVTO_API_KEY:
        print("DEVTO_API_KEY environment variable is not set.")
        sys.exit(1)

    raw_tags = article.get("tags", [])
    tags = clean_tags(raw_tags)

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
        return url, "ok"

    text = response.text
    print(f"Failed to publish to Dev.to: {text}")

    # Rate limit – do NOT mark as published, just stop and retry next run
    if response.status_code == 429 or "Retry later" in text:
        print("Dev.to is rate limiting us. Will retry this article on a future run.")
        return None, "rate_limit"

    # Canonical URL already used – permanent error
    if "Canonical url has already been taken" in text:
        print("Canonical URL already used on Dev.to. "
              "Marking this article as permanently failed so we do not retry.")
        return None, "permanent"

    # Tag / validation issues – permanent error
    if response.status_code == 422:
        print("Validation error (likely tags or other fields). "
              "Marking as permanently failed.")
        return None, "permanent"

    # Anything else – treat as permanent to avoid infinite retries
    print("Unexpected Dev.to error. Marking as permanently failed.")
    return None, "permanent"


def main():
    articles = load_articles()
    published_count = 0

    while published_count < MAX_PER_RUN:
        article = get_next_unpublished_devto(articles)
        if not article:
            print("No unpublished Dev.to articles remaining.")
            break

        print(f"Publishing to Dev.to: {article['title']}")
        url, status = publish_to_devto(article)

        if status == "ok":
            # Successful publish
            article["devto_published"] = True
            if url:
                article["devto_url"] = url
            published_count += 1

            # Wait 5 minutes between successful publishes
            if published_count < MAX_PER_RUN:
                print("Sleeping 300 seconds to avoid rate limits...")
                time.sleep(300)

        elif status == "permanent":
            # Mark as published so we don't retry this broken article
            print("Skipping this article due to permanent error.")
            article["devto_published"] = True

        elif status == "rate_limit":
            # Do NOT mark as published; retry on next run
            print("Stopping this run because of Dev.to rate limiting.")
            break

    save_articles(articles)
    print(f"Dev.to publish run complete. Published {published_count} article(s).")


if __name__ == "__main__":
    main()
