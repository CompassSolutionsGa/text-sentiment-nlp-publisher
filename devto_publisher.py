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

# Standard CTA snippet that will be added to every post if not present
CTA_SNIPPET = """

---

Try the Text Sentiment & NLP Insights API:

- Landing page: https://compasssolutionsga.github.io/text-sentiment-nlp-insights-landing/
- RapidAPI listing: https://rapidapi.com/CompassSolutionsGa/api/text-sentiment-nlp-insights-api
""".strip("\n")


def load_articles():
    if not ARTICLES_FILE.exists():
        print("articles.json not found")
        sys.exit(1)
    with open(ARTICLES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_articles(articles):
    with open(ARTICLES_FILE, "w", encoding="utf-8") as f:
        json.dump(articles, f, indent=2, ensure_ascii=False)


def get_next_unpublished_devto_index(articles):
    for idx, article in enumerate(articles):
        if not article.get("devto_published", False):
            return idx
    return None


def build_body_with_cta(raw_body: str) -> str:
    """
    Ensure the body contains the CTA block with your two links.
    We detect by checking for the landing or RapidAPI URL.
    """
    body = raw_body or ""

    if (
        "text-sentiment-nlp-insights-landing" in body
        or "text-sentiment-nlp-insights-api" in body
    ):
        # Links already present; just return the body
        return body

    # Append CTA, separated by a blank line
    return body.rstrip() + "\n\n" + CTA_SNIPPET


def publish_to_devto(article):
    if not DEVTO_API_KEY:
        print("DEVTO_API_KEY environment variable is not set.")
        sys.exit(1)

    body_markdown = build_body_with_cta(article.get("body_markdown", ""))

    payload = {
        "article": {
            "title": article["title"],
            "published": True,
            "body_markdown": body_markdown,
            "canonical_url": article.get("canonical_url"),
            "tags": article.get("tags", []),
            "series": article.get("series"),
        }
    }

    headers = {
        "Content-Type": "application/json",
        "api-key": DEVTO_API_KEY,
    }

    response = requests.post(DEVTO_API_URL, json=payload, headers=headers)

    # Dev.to may occasionally rate limit or reject; log details
    if response.status_code not in (200, 201):
        print("Failed to publish to Dev.to:", response.status_code, response.text)
        return None

    data = response.json()
    url = data.get("url")
    print("Published to Dev.to:", url)
    return url


def main():
    articles = load_articles()
    published_count = 0

    while published_count < MAX_PER_RUN:
        idx = get_next_unpublished_devto_index(articles)
        if idx is None:
            print("No unpublished Dev.to articles remaining.")
            break

        article = articles[idx]
        print(f"Publishing to Dev.to: {article['title']}")

        url = publish_to_devto(article)

        if url:
            # Mark as published and store URL
            articles[idx]["devto_published"] = True
            articles[idx]["devto_url"] = url
            published_count += 1
            save_articles(articles)
        else:
            # If publish fails, break out to avoid hammering Dev.to
            print("Publish failed; stopping this run.")
            break

        # Optional small delay between posts to be polite to the API
        time.sleep(5)

    print(f"Dev.to publish run complete. Published {published_count} article(s).")


if __name__ == "__main__":
    main()
