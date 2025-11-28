import json
import os
from pathlib import Path

import requests

ARTICLES_FILE = Path("articles.json")

HASHNODE_API_KEY = os.getenv("HASHNODE_API_KEY")
HASHNODE_PUBLICATION_ID = os.getenv("HASHNODE_PUBLICATION_ID")
MAX_PER_RUN = int(os.getenv("MAX_ARTICLES_PER_RUN", "3"))

HASHNODE_API_URL = "https://gql.hashnode.com"


def load_articles():
    if not ARTICLES_FILE.exists():
        print("articles.json not found")
        raise SystemExit(1)
    with open(ARTICLES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_articles(articles):
    with open(ARTICLES_FILE, "w", encoding="utf-8") as f:
        json.dump(articles, f, indent=2, ensure_ascii=False)


def get_next_unpublished_hashnode(articles):
    for article in articles:
        if not article.get("hashnode_published", False):
            return article
    return None


def publish_to_hashnode(article):
    if not HASHNODE_API_KEY or not HASHNODE_PUBLICATION_ID:
        print("Missing HASHNODE_API_KEY or HASHNODE_PUBLICATION_ID.")
        return None

    # Hashnode v2 GraphQL mutation
    query = """
    mutation CreatePost($input: CreatePostInput!) {
      createPost(input: $input) {
        post {
          _id
          slug
          title
          url
        }
      }
    }
    """

    tags = article.get("tags", [])

    variables = {
        "input": {
            "title": article["title"],
            "slug": article["slug"],
            "contentMarkdown": article["content_markdown"],
            "tags": tags,
            "publicationId": HASHNODE_PUBLICATION_ID,
            "isPublished": True,
        }
    }

    headers = {
        "Authorization": HASHNODE_API_KEY,
        "Content-Type": "application/json",
    }

    response = requests.post(
        HASHNODE_API_URL,
        json={"query": query, "variables": variables},
        headers=headers,
    )

    if response.status_code != 200:
        print("Hashnode API request failed:", response.status_code, response.text)
        return None

    data = response.json()

    if "errors" in data:
        print("Hashnode GraphQL errors:", data["errors"])
        return None

    try:
        post = data["data"]["createPost"]["post"]
        url = post.get("url")
    except (KeyError, TypeError):
        print("Unexpected Hashnode response:", data)
        return None

    print("Published to Hashnode:", url)
    return url


def main():
    articles = load_articles()
    published_count = 0

    while published_count < MAX_PER_RUN:
        article = get_next_unpublished_hashnode(articles)
        if not article:
            print("No unpublished Hashnode articles remaining.")
            break

        print(f"Publishing article to Hashnode: {article['title']}")
        url = publish_to_hashnode(article)

        if not url:
            print("Hashnode publish failed, stopping this run.")
            break

        article["hashnode_published"] = True
        article["hashnode_url"] = url
        published_count += 1

    save_articles(articles)
    print(f"Hashnode publish run complete. Published {published_count} article(s).")


if __name__ == "__main__":
    main()
