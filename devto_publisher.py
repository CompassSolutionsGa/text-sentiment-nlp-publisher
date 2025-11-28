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


def publish_to_devto(article):
    """
    Publish a single article to Dev.to.

    We intentionally do NOT send tags, because their validation rules are
    picky and are currently rejecting several of your tag values.
    """

    if not DEVTO_API_KEY:
        print("DEVTO_API_KEY environment variable is not set.")
        sys.exit(1)

    payload = {
        "article": {
            "title": article["title"],
            "published": True,
            "body_markdown": article["body_markdown"],
            "canonical_url": article.get("canonical_url"),
            # "tags": article.get("tags", []),  # disabled on purpose
            "series": article.get("series"),
        }
    }

    headers = {
        "Content-Type": "application/json",
        "api-key": DEVTO_API_KEY,
    }

    response = requests.post(DEVTO_API_URL, json=payload, headers=headers)
    text = response.text

    # Success
    if response.status_code in (200, 201):
        data = response.json()
        url = data.get("url")
        print("Published to Dev.to:", url)
        return "ok", url

    print(f"Failed to publish to Dev.to: {text}")

    # Rate-limit or generic "Retry later"
    if response.status_code == 429 or "Retry later" in text:
        print("Dev.to rate limit hit. Will retry this article on the next run.")
        return "rate_limit", None

    # Canonical URL already used (permanent)
    if "Canonical url has already been taken" in text:
        print("Canonical URL already used on Dev.to. "
              "Marking this article as permanently failed so we do not retry.")
        return "permanent", None

    # Validation / tag / other 422 errors – treat as permanent
    if response.status_code == 422:
        print("Dev.to validation error. Treating as permanent failure.")
        return "permanent", None

    # Any other errors – also treat as permanent
    print("Unexpected Dev.to error. Treating as permanent failure.")
    return "permanent", None


def main():
    articles = load_articles()
    published_count = 0

    while published_count < MAX_PER_RUN:
        article = get_next_unpublished_devto(articles)
        if not article:
            print("No unpublished Dev.to articles remaining.")
            break

        print(f"Publishing to Dev.to: {article['title']}")
        status, url = publish_to_devto(article)

        if status == "ok":
            article["devto_published"] = True
            if url:
                article["devto_url"] = url
            published_count += 1

            if published_count < MAX_PER_RUN:
                # wait 5 minutes between successful posts to avoid limits
                print("Sleeping 300 seconds before next Dev.to publish...")
                time.sleep(300)

        elif status == "permanent":
            # Mark as published so we do not retry this broken article
            print("Skipping this article permanently due to Dev.to error.")
            article["devto_published"] = True

        elif status == "rate_limit":
            # Do NOT mark as published; we will retry next run
            print("Stopping Dev.to run because of rate limiting.")
            break

    save_articles(articles)
    print(f"Dev.to publish run complete. Published {published_count} article(s).")


if __name__ == "__main__":
    main()
