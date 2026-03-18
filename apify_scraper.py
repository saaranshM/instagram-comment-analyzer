import os
import sys
from apify_client import ApifyClient


def _get_client():
    token = os.environ.get("APIFY_API_TOKEN")
    if not token:
        print(
            "Error: APIFY_API_TOKEN not set.\n"
            "Sign up at apify.com (free), get your API token from Settings > Integrations,\n"
            "and add it to your .env file.",
            file=sys.stderr,
        )
        sys.exit(1)
    return ApifyClient(token)


def fetch_posts_apify(handle, count):
    """Fetch recent post URLs from an Instagram profile using Apify."""
    client = _get_client()
    print(f"Fetching last {count} posts from @{handle} via Apify...", file=sys.stderr)
    run = client.actor("apify/instagram-post-scraper").call(
        run_input={
            "username": [handle],
            "resultsLimit": count,
        }
    )
    items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
    print(f"  Found {len(items)} posts.", file=sys.stderr)
    return items


def fetch_comments_apify(post_urls):
    """Fetch comments for a list of Instagram post URLs using Apify."""
    if not post_urls:
        return []
    client = _get_client()
    print(
        f"Fetching comments for {len(post_urls)} posts via Apify...", file=sys.stderr
    )
    run = client.actor("apify/instagram-comment-scraper").call(
        run_input={
            "directUrls": post_urls,
            "resultsLimit": 200,
        }
    )
    items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
    print(f"  Found {len(items)} comments.", file=sys.stderr)
    return items


def fetch_via_apify(handle, count):
    """Full pipeline: fetch posts then comments, return normalized comments."""
    posts = fetch_posts_apify(handle, count)
    post_urls = []
    for post in posts:
        url = post.get("url") or post.get("permalink")
        if url:
            post_urls.append(url)

    raw_comments = fetch_comments_apify(post_urls)

    # Normalize to unified format
    comments = []
    for c in raw_comments:
        comments.append(
            {
                "id": c.get("id", ""),
                "text": c.get("text", ""),
                "username": c.get("ownerUsername", c.get("username", "")),
                "timestamp": c.get("timestamp", ""),
                "like_count": c.get("likesCount", c.get("like_count", 0)),
            }
        )

    return comments, len(posts)
