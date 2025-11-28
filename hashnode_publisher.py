import os
import sys
import json
from typing import List, Dict

ARTICLES_FILE = "articles.json"


def load_articles() -> List[Dict]:
    if not os.path.exists(ARTICLES_FILE):
        print(f"{ARTICLES_FILE} not found.")
        sys.exit(1)
    with open(ARTICLES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_articles(articles: List[Dict]) -> None:
    with open(ARTICLES_FILE, "w", encoding="utf-8") as f:
        json.dump(articles, f, indent=2, ensure_ascii=False)


def get_next_unpublished_hashnode(articles: List[Dict]) -> Dict | None:
    for article in articles:
        if not article.get("hashnode_published", False):
            return article
    return None


def main():
    articles = load_articles()
    article = get_next_unpublished_hashnode(articles)

    if not article:
        print("No unpublished Hashnode articles remaining.")
        return

    print(
        "Hashnode auto-publish is currently disabled.\n"
        "Reason: The public GraphQL API at https://gql.hashnode.com "
        "does not expose a mutation to create posts. "
        "You will need to publish this article manually:\n"
        f"  Title: {article['title']}"
    )

    # If you want to mark items as 'handled' after manual posting, uncomment:
    # article["hashnode_published"] = True
    # save_articles(articles)
    # print("Marked article as hashnode_published after manual steps.")

    # Exit successfully so the GitHub Action does not fail
    sys.exit(0)


if __name__ == "__main__":
    main()
