import os
import sys
import time
import requests

BASE_URL = "https://graph.instagram.com/v21.0"


def _get_credentials():
    token = os.environ.get("INSTAGRAM_ACCESS_TOKEN")
    user_id = os.environ.get("INSTAGRAM_USER_ID")
    if not token or not user_id:
        print(
            "Error: INSTAGRAM_ACCESS_TOKEN and INSTAGRAM_USER_ID must be set.\n"
            "Ask the account owner to generate a token at developers.facebook.com\n"
            "and add both values to your .env file.",
            file=sys.stderr,
        )
        sys.exit(1)
    return token, user_id


def _api_request(url, params, retries=1):
    """Make a Graph API request with basic retry on 5xx."""
    for attempt in range(retries + 1):
        resp = requests.get(url, params=params, timeout=30)
        data = resp.json()

        if resp.ok:
            return data

        error = data.get("error", {})
        code = error.get("code")

        if code == 190:
            print(
                "Error: Instagram access token has expired.\n"
                "Ask the account owner to refresh it at developers.facebook.com.",
                file=sys.stderr,
            )
            sys.exit(1)

        if code in (4, 17):
            print(
                "Warning: Rate limit hit. Partial data may have been saved.",
                file=sys.stderr,
            )
            return None  # Caller handles partial results

        if resp.status_code >= 500 and attempt < retries:
            time.sleep(2)
            continue

        print(f"Error: Instagram API returned {resp.status_code}: {error.get('message', resp.text)}", file=sys.stderr)
        sys.exit(1)

    return None


def fetch_recent_posts(count):
    """Fetch recent posts from the authenticated user's media."""
    token, user_id = _get_credentials()
    fields = "id,caption,timestamp,permalink,media_type,comments_count,like_count"
    url = f"{BASE_URL}/{user_id}/media"

    posts = []
    params = {"fields": fields, "access_token": token, "limit": min(count, 25)}

    while len(posts) < count:
        data = _api_request(url, params)
        if data is None:
            break
        posts.extend(data.get("data", []))
        paging = data.get("paging", {})
        next_url = paging.get("next")
        if not next_url or len(posts) >= count:
            break
        url = next_url
        params = {}  # next_url already includes params

    return posts[:count]


def fetch_comments(media_id):
    """Fetch all comments for a single media post."""
    token, _ = _get_credentials()
    fields = "id,text,timestamp,username,like_count"
    url = f"{BASE_URL}/{media_id}/comments"

    comments = []
    params = {"fields": fields, "access_token": token, "limit": 50}

    while True:
        data = _api_request(url, params)
        if data is None:
            break
        comments.extend(data.get("data", []))
        paging = data.get("paging", {})
        next_url = paging.get("next")
        if not next_url:
            break
        url = next_url
        params = {}

    return comments


def fetch_via_api(handle, count):
    """Full pipeline: fetch posts then comments, return normalized comments."""
    print(f"Fetching last {count} posts from @{handle} via Graph API...", file=sys.stderr)
    posts = fetch_recent_posts(count)
    print(f"  Found {len(posts)} posts.", file=sys.stderr)

    rate_limited = False
    all_comments = []
    for post in posts:
        media_id = post["id"]
        comments = fetch_comments(media_id)
        if comments is None:
            rate_limited = True
            break
        for c in comments:
            all_comments.append(
                {
                    "id": c.get("id", ""),
                    "text": c.get("text", ""),
                    "username": c.get("username", ""),
                    "timestamp": c.get("timestamp", ""),
                    "like_count": c.get("like_count", 0),
                }
            )

    print(f"  Found {len(all_comments)} comments.", file=sys.stderr)
    return all_comments, len(posts), rate_limited
