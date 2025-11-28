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
        "Hashnode auto-publish is disabled.\n"
        "Reason: The public GraphQL endpoint at https://gql.hashnode.com "
        "does not support mutations to create posts "
        "(\"createStory\" / \"CreateStoryInput\" are not available).\n"
        "Please publish this article manually in Hashnode, then optionally "
        "set `hashnode_published` to true in articles.json:\n"
        f"  Title: {article['title']}\n"
        f"  Canonical URL: {article.get('canonical_url')}"
    )

    # If you want the script to automatically mark it as handled after you
    # manually post it, uncomment this block:
    #
    # article['hashnode_published'] = True
    # save_articles(articles)
    # print('Marked article as hashnode_published after manual steps.')

    sys.exit(0)


if __name__ == "__main__":
    main()
