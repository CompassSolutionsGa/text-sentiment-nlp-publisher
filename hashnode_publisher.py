import os
import sys
import json
import requests
from typing import List, Dict
from pathlib import Path

ARTICLES_FILE = Path("articles.json")
HASHNODE_API_URL = "https://gql.hashnode.com"

HASHNODE_API_KEY = os.getenv("HASHNODE_API_KEY")
HASHNODE_PUBLICATION_ID = os.getenv("HASHNODE_PUBLICATION_ID")


def load_articles() -> List[Dict]:
    if not ARTICLES_FILE.exists():
        print("articles.json missing.")
        sys.exit(1)
    with open(ARTICLES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_articles(articles: List[Dict]):
    with open(ARTICLES_FILE, "w", encoding="utf-8") as f:
        json.dump(articles, f, indent=2, ensure_ascii=False)


def get_next_unpublished_hashnode(articles):
    for a in articles:
        if not a.get("hashnode_published", False):
            return a
    return None


def publish_to_hashnode(article):
    if not HASHNODE_API_KEY or not HASHNODE_PUBLICATION_ID:
        print("Missing Hashnode API key or publication ID.")
        return None

    mutation = """
    mutation PublishToPublication($publicationId: ObjectId!, $input: CreateStoryInput!) {
      createStory(publicationId: $publicationId, input: $input) {
        _id
        slug
        url
      }
    }
    """

    variables = {
        "publicationId": HASHNODE_PUBLICATION_ID,
        "input": {
            "title": article["title"],
            "contentMarkdown": article["body_markdown"],
            "tags": article.get("tags", []),
        },
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": HASHNODE_API_KEY,
    }

    response = requests.post(
        HASHNODE_API_URL,
        json={"query": mutation, "variables": variables},
        headers=headers,
    )

    data = response.json()

    if "errors" in data:
        print("Hashnode Publish Error:", data)
        return None

    url = data["data"]["createStory"]["url"]
    print("Published to Hashnode:", url)
    return url


def main():
    articles = load_articles()

    article = get_next_unpublished_hashnode(articles)
    if not article:
        print("No Hashnode articles left.")
        return

    print(f"Publishing article to Hashnode: {article['title']}")
    url = publish_to_hashnode(article)

    if url:
        article["hashnode_published"] = True
        article["hashnode_url"] = url
    else:
        print("Hashnode publish failed. Leaving as unpublished.")

    save_articles(articles)


if __name__ == "__main__":
    main()
