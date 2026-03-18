import os
import sys
import time
import requests

BASE_URL = "https://graph.instagram.com/v24.0"

# Rate limit sentinel — returned by _api_request when rate limited
_RATE_LIMITED = object()


def _get_credentials():
    token = os.environ.get("INSTAGRAM_ACCESS_TOKEN")
    user_id = os.environ.get("INSTAGRAM_USER_ID")
    if not token or not user_id:
        print(
            "Error: INSTAGRAM_ACCESS_TOKEN and INSTAGRAM_USER_ID must be set.\n"
            "\n"
            "How to get them (free):\n"
            "  1. Convert @dreamy.loopz to a Business/Creator account (Settings > Account type)\n"
            "  2. Go to developers.facebook.com > Create App > Business type\n"
            "  3. Add 'Instagram' product to your app\n"
            "  4. Generate a token via Instagram Login flow\n"
            "  5. Exchange for a long-lived token (60 days):\n"
            "     GET https://graph.instagram.com/access_token\n"
            "       ?grant_type=ig_exchange_token\n"
            "       &client_secret=YOUR_APP_SECRET\n"
            "       &access_token=SHORT_LIVED_TOKEN\n"
            "  6. Get your user ID:\n"
            "     GET https://graph.instagram.com/me?fields=id,username&access_token=TOKEN\n"
            "  7. Add both to .env:\n"
            "     INSTAGRAM_ACCESS_TOKEN=your_long_lived_token\n"
            "     INSTAGRAM_USER_ID=your_user_id\n",
            file=sys.stderr,
        )
        sys.exit(1)
    return token, user_id


def _api_request(url, params, retries=1):
    """Make a Graph API request with basic retry on 5xx.

    Returns:
        dict: response data on success
        _RATE_LIMITED: on rate limit (codes 4, 17)
        None: on other failure (after retries)
    """
    for attempt in range(retries + 1):
        resp = requests.get(url, params=params, timeout=30)
        data = resp.json()

        if resp.ok:
            return data

        error = data.get("error", {})
        code = error.get("code")

        if code == 190:
            sub_code = error.get("error_subcode")
            if sub_code == 463:
                msg = "Token has expired."
            elif sub_code == 460:
                msg = "Password was changed."
            elif sub_code == 458:
                msg = "App was removed."
            else:
                msg = "Token is invalid."
            print(
                f"Error: Instagram API — {msg}\n"
                "The account owner needs to generate a new token.\n"
                "Refresh a valid long-lived token:\n"
                "  GET https://graph.instagram.com/refresh_access_token\n"
                "    ?grant_type=ig_refresh_token&access_token=CURRENT_TOKEN\n"
                "(Refresh every ~50 days to prevent expiration.)",
                file=sys.stderr,
            )
            sys.exit(1)

        if code in (4, 17):
            print(
                "Warning: Rate limit hit (200 calls/hour). Saving partial results.",
                file=sys.stderr,
            )
            return _RATE_LIMITED

        if resp.status_code >= 500 and attempt < retries:
            time.sleep(2)
            continue

        print(
            f"Error: Instagram API returned {resp.status_code}: "
            f"{error.get('message', resp.text)}",
            file=sys.stderr,
        )
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
        if data is _RATE_LIMITED or data is None:
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
    """Fetch all comments for a single media post.

    Returns (comments_list, rate_limited_bool).
    """
    token, _ = _get_credentials()
    fields = "id,text,timestamp,username,like_count"
    url = f"{BASE_URL}/{media_id}/comments"

    comments = []
    rate_limited = False
    params = {"fields": fields, "access_token": token, "limit": 50}

    while True:
        data = _api_request(url, params)
        if data is _RATE_LIMITED:
            rate_limited = True
            break
        if data is None:
            break
        comments.extend(data.get("data", []))
        paging = data.get("paging", {})
        next_url = paging.get("next")
        if not next_url:
            break
        url = next_url
        params = {}

    return comments, rate_limited


def fetch_via_api(handle, count):
    """Full pipeline: fetch posts then comments, return normalized comments."""
    print(f"Fetching last {count} posts from @{handle} via Graph API...", file=sys.stderr)
    posts = fetch_recent_posts(count)
    print(f"  Found {len(posts)} posts.", file=sys.stderr)

    rate_limited = False
    all_comments = []
    for post in posts:
        media_id = post["id"]
        comments, hit_limit = fetch_comments(media_id)
        if hit_limit:
            rate_limited = True
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
        if rate_limited:
            break

    print(f"  Found {len(all_comments)} comments.", file=sys.stderr)
    return all_comments, len(posts), rate_limited
