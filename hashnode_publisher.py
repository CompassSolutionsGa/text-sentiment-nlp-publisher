
import os
import sys
import json
from typing import List, Dict, Optional

import requests

ARTICLES_FILE = "articles.json"
HASHNODE_GRAPHQL_URL = "https://gql.hashnode.com"

HASHNODE_API_KEY = os.getenv("HASHNODE_API_KEY")
HASHNODE_PUBLICATION_ID = os.getenv("HASHNODE_PUBLICATION_ID")


def load_articles() -> List[Dict]:
    if not os.path.exists(ARTICLES_FILE):
        print(f"{ARTICLES_FILE} not found.")
        sys.exit(1)

    with open(ARTICLES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_articles(articles: List[Dict]) -> None:
    with open(ARTICLES_FILE, "w", encoding="utf-8") as f:
        json.dump(articles, f, indent=2, ensure_ascii=False)


def get_next_unpublished_hashnode(articles: List[Dict]) -> Optional[Dict]:
    """Return the first article that has not yet been published to Hashnode."""
    for article in articles:
        if not article.get("hashnode_published"):
            return article
    return None


def build_hashnode_payload(article: Dict) -> Dict:
    """
    Build GraphQL mutation payload for Hashnode publications.
    Uses createPublicationStory(pubId: ID!, input: CreateStoryInput!).
    """
    title = article["title"]
    content_markdown = article["content_markdown"]
    tags = article.get("tags", [])  # list of strings

    # Hashnode tags: list of TagInput (slug + name). We'll map string tags -> both fields.
    hashnode_tags = [{"slug": t, "name": t} for t in tags]

    mutation = """
    mutation CreatePublicationStory($pubId: ID!, $input: CreateStoryInput!) {
      createPublicationStory(publicationId: $pubId, input: $input) {
        code
        success
        message
        post {
          _id
          slug
          url
        }
      }
    }
    """

    variables = {
        "pubId": HASHNODE_PUBLICATION_ID,
        "input": {
            "title": title,
            "contentMarkdown": content_markdown,
            "tags": hashnode_tags,
            "isPartOfPublication": True,
            # you can add "isRepublished": { "originalArticleURL": ... } here if needed
        },
    }

    return {"query": mutation, "variables": variables}


def publish_to_hashnode(article: Dict) -> Optional[str]:
    if not HASHNODE_API_KEY or not HASHNODE_PUBLICATION_ID:
        print("Missing HASHNODE_API_KEY or HASHNODE_PUBLICATION_ID environment variables.")
        sys.exit(1)

    payload = build_hashnode_payload(article)

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {HASHNODE_API_KEY}",
    }

    response = requests.post(HASHNODE_GRAPHQL_URL, json=payload, headers=headers)

    if response.status_code != 200:
        print("Failed to publish to Hashnode:", response.status_code, response.text)
        return None

    data = response.json()
    if "errors" in data:
        print("Hashnode GraphQL errors:", data["errors"])
        return None

    story = data.get("data", {}).get("createPublicationStory")
    if not story or not story.get("success"):
        print("Hashnode API returned an error:", story or data)
        return None

    post = story.get("post") or {}
    url = post.get("url")
    print(f"Published to Hashnode: {url}")
    return url


def main():
    articles = load_articles()
    article = get_next_unpublished_hashnode(articles)

    if not article:
        print("No unpublished Hashnode articles remaining.")
        return

    print(f"Publishing article to Hashnode: {article['title']}")
    url = publish_to_hashnode(article)

    if url:
        article["hashnode_published"] = True
        article["hashnode_url"] = url
        save_articles(articles)
        print("Hashnode publish complete.")
    else:
        print("Hashnode publish failed.")


if __name__ == "__main__":
    main()
