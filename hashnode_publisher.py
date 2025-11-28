import os
import sys
import json
from typing import List, Dict, Optional

import requests

ARTICLES_FILE = "articles.json"
HASHNODE_API_URL = "https://gql.hashnode.com"

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
    """Return the next article where hashnode_published is not True."""
    for article in articles:
        if not article.get("hashnode_published", False):
            return article
    return None


# You may need to tweak this mutation name and/or input type based on the
# "Docs" panel in your Hashnode GraphQL Playground.
CREATE_POST_MUTATION = """
mutation CreatePost($input: CreatePostInput!) {
  createPost(input: $input) {
    post {
      id
      slug
      url
    }
  }
}
"""


def build_hashnode_payload(article: Dict) -> Dict:
    title = article["title"]
    content_markdown = article["content_markdown"]

    tags = article.get("tags", [])
    hashnode_tags = [{"slug": t, "name": t} for t in tags]

    variables = {
        "input": {
            "title": title,
            "contentMarkdown": content_markdown,
            "tags": hashnode_tags,
            # If your schema expects a different field name than "publicationId",
            # adjust this based on the Playground docs.
            "publicationId": HASHNODE_PUBLICATION_ID,
        }
    }

    return {
        "query": CREATE_POST_MUTATION,
        "variables": variables,
    }


def publish_to_hashnode(article: Dict) -> Optional[str]:
    if not HASHNODE_API_KEY or not HASHNODE_PUBLICATION_ID:
        print("Missing HASHNODE_API_KEY or HASHNODE_PUBLICATION_ID. Skipping Hashnode publish.")
        return None

    payload = build_hashnode_payload(article)

    headers = {
        "Content-Type": "application/json",
        "Authorization": HASHNODE_API_KEY,
    }

    response = requests.post(HASHNODE_API_URL, json=payload, headers=headers)

    if response.status_code != 200:
        print("Hashnode API request failed:", response.status_code, response.text)
        # Do not crash the workflow; just report the error.
        return None

    data = response.json()

    # Handle GraphQL errors block
    if "errors" in data:
        print("Hashnode GraphQL errors:", json.dumps(data["errors"], indent=2))
        return None

    post_data = (
        data.get("data", {})
        .get("createPost", {})
        .get("post", {})
    )

    url = post_data.get("url")
    if url:
        print("Published to Hashnode:", url)
    else:
        print("Hashnode did not return a post URL:", json.dumps(data, indent=2))

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
        print("Hashnode publish failed. Leaving article as unpublished so you can fix the mutation later.")


if __name__ == "__main__":
    main()
