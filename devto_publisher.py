import json
import os
import sys
import time
from pathlib import Path
import requests

QUEUE_FILE = Path("articles.json")
ARCHIVE_FILE = Path("articles_published.json")
DEVTO_API_URL = "https://dev.to/api/articles"
DEVTO_API_KEY = os.getenv("DEVTO_API_KEY")
MAX_PER_RUN = int(os.getenv("MAX_ARTICLES_PER_RUN", "3"))
WAIT_SECONDS = 5  # wait between posts


def load_json(path, default=None):
    if not path.exists():
        return default if default is not None else []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def safe_tags(tags):
    """Dev.to only allows alphanumeric and hyphens; max 4 tags."""
    cleaned = []
    for t in tags:
        t = t.lower().replace(" ", "-")
        cleaned.append("".join(c for c in t if c.isalnum() or c == "-"))
    return cleaned[:4]


def publish_to_devto(article):
    if not DEVTO_API_KEY:
        print("ERROR: DEVTO_API_KEY is not set")
        sys.exit(1)

    payload = {
        "article": {
            "title": article["title"],
            "published": True,
            "body_markdown": article["body_markdown"],
            "canonical_url": article.get("canonical_url"),
            "tags": safe_tags(article.get("tags", [])),
            "series": article.get("series"),
        }
    }

    headers = {"Content-Type": "application/json", "api-key": DEVTO_API_KEY}

    response = requests.post(DEVTO_API_URL, json=payload, headers=headers)

    # Permanent validation error (already used canonical URL, bad tags, etc.)
    if response.status_code == 422:
        print("Permanent Dev.to error:", response.text)
        return {"status": "invalid", "error": response.text}

    # Rate limit – we should retry later
    if response.status_code == 429:
        print("Rate limited. Retry later.")
        return {"status": "retry"}

    if response.status_code not in (200, 201):
        print("Unknown Dev.to error:", response.text)
        return {"status": "retry"}

    data = response.json()
    print("Published →", data.get("url"))
    return {"status": "success", "url": data.get("url")}


def main():
    queue = load_json(QUEUE_FILE, default=[])
    archive = load_json(ARCHIVE_FILE, default=[])

    if not queue:
        print("No articles in queue.")
        return

    new_queue = []
    published_count = 0

    for article in queue:
        if published_count >= MAX_PER_RUN:
            new_queue.append(article)
            continue

        print(f"\nPublishing to Dev.to: {article['title']}")
        result = publish_to_devto(article)

        if result["status"] == "success":
            article["devto_url"] = result["url"]
            article["devto_published_at"] = time.time()
            archive.append(article)
            published_count += 1
            time.sleep(WAIT_SECONDS)
            continue

        if result["status"] == "invalid":
            print("Marking article as permanently invalid and moving to archive.")
            article["devto_error"] = result["error"]
            archive.append(article)
            continue

        if result["status"] == "retry":
            print("Keeping article in queue for next run.")
            new_queue.append(article)
            continue

    save_json(QUEUE_FILE, new_queue)
    save_json(ARCHIVE_FILE, archive)

    print(f"\nDone. Published {published_count} article(s).")


if __name__ == "__main__":
    main()
