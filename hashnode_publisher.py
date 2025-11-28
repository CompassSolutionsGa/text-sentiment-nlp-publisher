import os
import sys
import json
import requests
from typing import List, Dict, Optional

ARTICLES_FILE = "articles.json"
# New GraphQL endpoint
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
    for article in articles:
        if not article.get("hashnode_published"):
            return article
    return None


def build_hashnode_payload(article: Dict) -> Dict:
    title = article["title"]
    content_markdown = article["content_markdown"]
    tags = article.get("tags", [])

    # Hashnode tags: list of { slug, name }
    hashnode_tags = [{"slug": t, "name": t} for t in tags]

    mutation = """
    mutation PublishToPublication(
      $title: String!,
      $contentMarkdown: String!,
      $tags: [TagInput!],
      $publicationId: ID!
    ) {
      createPost(
        input: {
          title: $title,
          contentMarkdown: $contentMarkdown,
          tags: $tags,
          publicationId: $publicationId
        }
      ) {
        post {
          id
          slug
          url
        }
      }
    }
    """

    variables = {
        "title": title,
        "contentMarkdown": content_markdown,
        "tags": hashnode_tags,
        "publicationId": HASHNODE_PUBLICATION_ID,
    }

    return {
        "query": mutation,
        "variables": variables,
    }


def publish_to_hashnode(article: Dict) -> Optional[str]:
    if not HASHNODE_API_KEY or not HASHNODE_PUBLICATION_ID:
        print("Missing HASHNODE_API_KEY or HASHNODE_PUBLICATION_ID environment variables.")
        sys.exit(1)

    payload = build_hashnode_payload(article)

    headers = {
        "Content-Type": "application/json",
        # Hashnode uses the token directly in Authorization
        "Authorization": HASHNODE_API_KEY,
    }

    response = requests.post(HASHNODE_API_URL, json=payload, headers=headers)

    if response.status_code != 200:
        print("Failed to publish to Hashnode:", response.status_code, response.text)
        return None

    data = response.json()
    errors = data.get("errors")
    if errors:
        print("Hashnode GraphQL errors:", errors)
        return None

    post = (
        data
        .get("data", {})
        .get("createPost", {})
        .get("post", {})
    )

    url = post.get("url")
    if not url:
        print("Hashnode response did not include a post URL:", data)
        return None

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
        print("Hashnode publish failed. Leaving article as unpublished so you can fix the mutation later.")


if __name__ == "__main__":
    main()
