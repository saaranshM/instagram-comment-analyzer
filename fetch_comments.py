#!/usr/bin/env python3
"""Instagram Comment Analyzer CLI — fetch comments, extract car requests, output rankings."""

import argparse
import sys
import os
from datetime import datetime, timezone

from dotenv import load_dotenv


def _detect_mode(explicit_mode):
    """Auto-detect fetch mode: prefer API if credentials exist, else Apify."""
    if explicit_mode:
        return explicit_mode

    # Prefer Instagram Graph API (free, no rate limits for account owner)
    if os.environ.get("INSTAGRAM_ACCESS_TOKEN") and os.environ.get("INSTAGRAM_USER_ID"):
        return "api"

    # Fall back to Apify
    if os.environ.get("APIFY_API_TOKEN"):
        return "scrape"

    print(
        "Error: No credentials found. Set one of:\n"
        "  1. INSTAGRAM_ACCESS_TOKEN + INSTAGRAM_USER_ID (free, recommended)\n"
        "     Ask the account owner to generate a token at developers.facebook.com\n"
        "  2. APIFY_API_TOKEN (free tier, sign up at apify.com)\n"
        "Add them to your .env file.",
        file=sys.stderr,
    )
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Analyze Instagram comments for car requests"
    )
    parser.add_argument(
        "--last", type=int, required=True, help="Number of recent posts to fetch"
    )
    parser.add_argument(
        "--mode",
        choices=["scrape", "api"],
        default=None,
        help="Fetch mode: api (Graph API, free) or scrape (Apify). Auto-detects if omitted.",
    )
    parser.add_argument(
        "--handle",
        default="dreamy.loopz",
        help="Instagram handle to fetch from. Default: dreamy.loopz",
    )
    parser.add_argument("--brand", help="Filter results to this brand")
    parser.add_argument("--car", help="Filter results to this car model")
    parser.add_argument("--text", help="Pre-filter comments containing this text")
    parser.add_argument("--output", help="Output JSON file path (auto-generated if omitted)")
    parser.add_argument(
        "--quiet", action="store_true", help="Suppress console summary, only output JSON path"
    )
    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    # Step 1: Detect mode and fetch comments
    mode = _detect_mode(args.mode)
    rate_limited = False

    if mode == "api":
        from instagram_api import fetch_via_api

        print("Using Instagram Graph API (free, account owner token).", file=sys.stderr)
        comments, posts_count, rate_limited = fetch_via_api(args.handle, args.last)
    else:
        from apify_scraper import fetch_via_apify

        print("Using Apify scraper (no Instagram login needed).", file=sys.stderr)
        comments, posts_count = fetch_via_apify(args.handle, args.last)

    if not comments:
        print("No comments found.", file=sys.stderr)
        sys.exit(1)

    # Step 2: Pre-filter comments
    from filters import filter_comments, filter_results

    comments = filter_comments(comments, text=args.text)

    if not comments:
        print("No comments matched the text filter.", file=sys.stderr)
        sys.exit(1)

    # Step 3: Extract car mentions
    from car_extractor import CarExtractor

    extractor = CarExtractor()
    extractions = extractor.extract(comments)

    # Step 4: Post-filter results
    extractions = filter_results(extractions, brand=args.brand, car=args.car)

    # Step 5: Aggregate
    from output import aggregate_results, build_output, save_json, print_summary

    rankings, brand_summary = aggregate_results(extractions)

    metadata = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "account": f"@{args.handle}",
        "mode": mode,
        "posts_scanned": posts_count,
        "total_comments_analyzed": len(comments),
        "car_mentions_found": len(extractions),
        "filters_applied": {
            "brand": args.brand,
            "car": args.car,
            "text": args.text,
        },
    }

    data = build_output(rankings, brand_summary, metadata)

    # Step 6: Output
    filepath = save_json(data, args.output)

    if args.quiet:
        print(filepath)
    else:
        print_summary(data)
        print(f"Results saved to: {filepath}", file=sys.stderr)

    # Exit code
    if rate_limited:
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
