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

# Standard CTA snippet with SEO-friendly hyperlinks
CTA_SNIPPET = """
---

## Try the Text Sentiment & NLP Insights API

If you want to work with production-ready sentiment and text intelligence, you can integrate this API directly into your stack:

- Visit the official landing page: [Text Sentiment & NLP Insights API landing page](https://compasssolutionsga.github.io/text-sentiment-nlp-insights-landing/)
- Explore the hosted version on RapidAPI: [Text Sentiment & NLP Insights API on RapidAPI](https://rapidapi.com/CompassSolutionsGa/api/text-sentiment-nlp-insights-api)
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
    We detect by checking for either the landing or RapidAPI URL.
    """
    body = (raw_body or "").rstrip()

    if (
        "text-sentiment-nlp-insights-landing" in body
        or "text-sentiment-nlp-insights-api" in body
    ):
        # Links already present; just return the body
        return body

    # Append CTA, separated by a blank line
    if body:
        return body + "\n\n" + CTA_SNIPPET
    else:
        return CTA_SNIPPET


def publish_to_devto(article):
    """
    Try to publish one article to Dev.to.

    Returns dict with:
      {"status": "published", "url": "..."}            # success
      {"status": "canonical_taken"}                    # already exists on Dev.to
      {"status": "rate_limited"}                       # 429
      {"status": "validation_error", "error": "..."}   # 422 other
      {"status": "error", "error": "..."}              # anything else
    """
    if not DEVTO_API_KEY:
        print("DEVTO_API_KEY environment variable is not set.")
        sys.exit(1)

    headers = {
        "api-key": DEVTO_API_KEY,
        "Content-Type": "application/json",
    }

    # Build bodies with CTA + hyperlinks injected
    body_with_cta = build_body_with_cta(article.get("body_markdown", ""))
    content_source = article.get("content_markdown") or article.get("body_markdown", "")
    content_with_cta = build_body_with_cta(content_source)

    payload = {
        "article": {
            "title": article["title"],
            "published": True,
            "canonical_url": article["canonical_url"],
            "series": article.get("series"),
            "tags": article.get("tags", []),
            "body_markdown": body_with_cta,
            "content_markdown": content_with_cta,
        }
    }

    response = requests.post(DEVTO_API_URL, headers=headers, json=payload)

    # Success
    if response.status_code == 201:
        data = response.json()
        url = data.get("url")
        print("Published →", url)
        return {"status": "published", "url": url}

    # Rate limited
    if response.status_code == 429:
        print("Rate limited. Retry later.")
        return {"status": "rate_limited"}

    # Validation / canonical issues
    if response.status_code == 422:
        text = response.text
        if "Canonical url has already been taken" in text:
            print(
                "Canonical URL has already been used on Dev.to; "
                "marking as published and skipping this article."
            )
            return {"status": "canonical_taken"}
        else:
            print("Validation error from Dev.to:", text)
            return {"status": "validation_error", "error": text}

    # Other unexpected errors
    print("Failed to publish to Dev.to:", response.status_code, response.text)
    return {"status": "error", "error": response.text}


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

        result = publish_to_devto(article)
        status = result["status"]

        if status in ("published", "canonical_taken"):
            # Treat both as "done" so we never retry this canonical again
            articles[idx]["devto_published"] = True
            if status == "published" and result.get("url"):
                articles[idx]["devto_url"] = result["url"]
            save_articles(articles)
            published_count += 1

            # Be polite to Dev.to and avoid rate limiting
            time.sleep(60)
            continue

        if status == "rate_limited":
            print("Stopping run due to rate limiting; will retry later.")
            break

        # For any other error, stop so you can inspect the logs
        print("Publish failed with status:", status)
        break

    print(f"Dev.to publish run complete. Published {published_count} article(s).")


if __name__ == "__main__":
    main()
