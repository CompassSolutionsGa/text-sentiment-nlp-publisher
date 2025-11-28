import json
import os
import sys
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
    """Return the next article where devto_published is not True."""
    for article in articles:
        if not article.get("devto_published", False):
            return article
    return None


def publish_to_devto(article):
    """
    Try to publish one article to Dev.to.

    Returns:
      - url (str) on success
      - None if we hit a hard error and should skip this article
      - "RATE_LIMIT" if we hit 429 and should stop this run
    """
    if not DEVTO_API_KEY:
        print("DEVTO_API_KEY environment variable is not set.")
        sys.exit(1)

    tags = article.get("tags") or []
    # Dev.to allows max 4 tags, all alphanumeric with hyphens.
    tags = [t for t in tags if t]           # drop empty
    tags = tags[:4]                         # cap at 4
    article["tags"] = tags                  # keep cleaned tags in memory

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
        url = data.get("url") or data.get("canonical_url") or article.get("canonical_url")
        print("Published to Dev.to:", url)
        return url

    # Rate limit
    if response.status_code == 429:
        print("Failed to publish to Dev.to: 429 rate limited. Stopping this run.")
        return "RATE_LIMIT"

    # 422 – often canonical_url already taken or validation issue
    if response.status_code == 422:
        text = response.text.lower()
        print("Failed to publish to Dev.to: 422", response.text)

        # If canonical URL already exists on Dev.to, consider it "published"
        if "canonical url has already been taken" in text:
            print(
                "Dev.to: Article already exists with this canonical URL. "
                "Marking as published and skipping."
            )
            # Treat as success; use canonical_url as the reference
            return article.get("canonical_url")

        # Other 422 – just skip this article but do NOT kill the whole workflow
        print("Skipping this article due to Dev.to validation error.")
        return None

    # Any other error: log and skip this article
    print("Unexpected Dev.to error:", response.status_code, response.text)
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
        result = publish_to_devto(article)

        if result == "RATE_LIMIT":
            # Stop immediately; we'll continue next day / next run
            break

        if result is None:
            # Hard error on this article, mark it as "failed" so we do not loop forever.
            # If you prefer to keep retrying, comment out the next line.
            article["devto_published"] = True
            article["devto_url"] = article.get("devto_url")
            print("Marking article as devto_published to avoid re-trying this invalid entry.")
        else:
            # Success or canonical already taken
            article["devto_published"] = True
            article["devto_url"] = result
            published_count += 1

    save_articles(articles)
    print(f"Dev.to publish run complete. Published {published_count} article(s).")


if __name__ == "__main__":
    main()
