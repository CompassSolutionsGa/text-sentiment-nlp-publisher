import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

import requests

ARTICLES_FILE = Path("articles.json")               # pending queue
PUBLISHED_FILE = Path("articles_published.json")    # archive
DEVTO_API_URL = "https://dev.to/api/articles"

DEVTO_API_KEY = os.getenv("DEVTO_API_KEY")
MAX_PER_RUN = int(os.getenv("MAX_ARTICLES_PER_RUN", "3"))


# ---------- Helpers for JSON files ----------

def load_json_list(path: Path):
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
        # Make sure it is always a list
        if isinstance(data, list):
            return data
        raise ValueError(f"{path} does not contain a JSON list.")


def save_json_list(path: Path, data):
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_articles():
    if not ARTICLES_FILE.exists():
        print("articles.json not found")
        sys.exit(1)
    return load_json_list(ARTICLES_FILE)


def load_published():
    return load_json_list(PUBLISHED_FILE)


# ---------- Dev.to publishing ----------

def publish_to_devto(article):
    """
    Returns a tuple:
      (status, url_or_none, error_message_or_none)

    status is one of:
      "published"       – success
      "retry_later"     – rate limit / transient error
      "hard_error"      – permanent 4xx validation error
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
            # Dev.to allows up to 4 tags – we also assume they are already
            # simple lowercase slugs like "nlp", "ai", etc.
            "tags": article.get("tags", [])[:4],
            "series": article.get("series"),
        }
    }

    headers = {
        "Content-Type": "application/json",
        "api-key": DEVTO_API_KEY,
    }

    try:
        resp = requests.post(DEVTO_API_URL, json=payload, headers=headers, timeout=30)
    except Exception as e:
        msg = f"Network error when posting to Dev.to: {e}"
        print(msg)
        return "retry_later", None, msg

    # Transient rate-limit or server error
    if resp.status_code in (429, 500, 502, 503):
        print(f"Failed to publish to Dev.to: {resp.status_code} rate limited / server error. Stopping this run.")
        return "retry_later", None, f"{resp.status_code} rate limited or server error"

    # Other non-success responses – treat as hard validation errors
    if resp.status_code not in (200, 201):
        body_text = resp.text.strip()
        print(f"Failed to publish to Dev.to: {body_text}")
        return "hard_error", None, body_text

    try:
        data = resp.json()
    except json.JSONDecodeError:
        print("Dev.to response was not valid JSON.")
        return "hard_error", None, "Invalid JSON response from Dev.to"

    url = data.get("url")
    print("Published to Dev.to:", url)
    return "published", url, None


# ---------- Main loop ----------

def main():
    articles = load_articles()
    published_archive = load_published()

    if not articles:
        print("No articles in articles.json.")
        return

    published_count = 0
    index = 0  # we will walk through the list while possibly removing items

    while index < len(articles) and published_count < MAX_PER_RUN:
        article = articles[index]
        title = article.get("title", "(untitled)")
        print(f"Publishing to Dev.to: {title}")

        status, url, error_msg = publish_to_devto(article)

        now_iso = datetime.now(timezone.utc).isoformat()

        if status == "published":
            # enrich and move to archive
            article_record = dict(article)
            article_record["devto_status"] = "published"
            article_record["devto_url"] = url
            article_record["devto_published_at"] = now_iso

            published_archive.append(article_record)

            # remove from pending queue (do not increment index)
            articles.pop(index)
            published_count += 1
            continue  # go to next item at same index

        elif status == "hard_error":
            # move to archive but mark as error so it is not retried
            article_record = dict(article)
            article_record["devto_status"] = "error"
            article_record["devto_error"] = error_msg
            article_record["devto_checked_at"] = now_iso

            published_archive.append(article_record)

            # remove from pending queue (do not increment index)
            articles.pop(index)
            print("Skipping this article permanently due to validation error.")
            continue

        elif status == "retry_later":
            # Keep article in queue and stop the run
            print("Transient error / rate limit. Leaving article in queue for next run.")
            break

        else:
            # Should not happen, but be safe
            print("Unknown status from publish_to_devto:", status)
            break

    # Save updated files
    save_json_list(ARTICLES_FILE, articles)
    save_json_list(PUBLISHED_FILE, published_archive)

    print(f"Dev.to publish run complete. Published {published_count} article(s).")
    print(f"Remaining in queue: {len(articles)}")


if __name__ == "__main__":
    main()
