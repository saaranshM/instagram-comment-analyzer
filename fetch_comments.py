#!/usr/bin/env python3
"""Instagram Comment Analyzer CLI — fetch comments, extract entity requests, output rankings."""

import argparse
import sys
import os
from datetime import datetime, timezone

from dotenv import load_dotenv


def _detect_mode(explicit_mode):
    if explicit_mode:
        return explicit_mode
    if os.environ.get("INSTAGRAM_ACCESS_TOKEN") and os.environ.get("INSTAGRAM_USER_ID"):
        return "api"
    if os.environ.get("APIFY_API_TOKEN"):
        return "scrape"
    print(
        "Error: No credentials found. Set one of:\n"
        "  1. INSTAGRAM_ACCESS_TOKEN + INSTAGRAM_USER_ID (free, recommended)\n"
        "  2. APIFY_API_TOKEN (free tier, sign up at apify.com)\n"
        "Add them to your .env file.",
        file=sys.stderr,
    )
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Analyze Instagram comments for entity requests (cars, phones, sneakers, etc.)"
    )
    parser.add_argument("--last", type=int, required=True, help="Number of recent posts to fetch")
    parser.add_argument("--mode", choices=["scrape", "api"], default=None,
                        help="Fetch mode: api or scrape. Auto-detects if omitted.")
    parser.add_argument("--handle", default=os.environ.get("INSTAGRAM_HANDLE", ""),
                        help="Instagram handle. Or set INSTAGRAM_HANDLE in .env")
    parser.add_argument("--taxonomy", default="cars",
                        help="Taxonomy to use (e.g. cars, phones, sneakers). Default: cars")
    parser.add_argument("--taxonomy-file", default=None,
                        help="Load taxonomy from a specific YAML/JSON file")
    parser.add_argument("--brand", help="Filter results to this brand/group")
    parser.add_argument("--item", help="Filter results to this item/model")
    parser.add_argument("--car", help="Alias for --item (backward compat)")
    parser.add_argument("--text", help="Pre-filter comments containing this text")
    parser.add_argument("--output", help="Output JSON file path (auto-generated if omitted)")
    parser.add_argument("--quiet", action="store_true", help="Suppress console summary")
    args = parser.parse_args()

    load_dotenv()

    if not args.handle:
        print("Error: No handle. Use --handle or set INSTAGRAM_HANDLE in .env", file=sys.stderr)
        sys.exit(1)

    # Load taxonomy
    from taxonomy import Taxonomy, TaxonomyRegistry

    if args.taxonomy_file:
        taxonomy = Taxonomy(args.taxonomy_file)
    else:
        taxonomy_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "taxonomies")
        reg = TaxonomyRegistry(taxonomy_dir)
        taxonomy = reg.get(args.taxonomy)

    # Fetch comments
    mode = _detect_mode(args.mode)
    rate_limited = False

    if mode == "api":
        from instagram_api import fetch_via_api
        print(f"Using Instagram Graph API.", file=sys.stderr)
        comments, posts_count, rate_limited = fetch_via_api(args.handle, args.last)
    else:
        from apify_scraper import fetch_via_apify
        print(f"Using Apify scraper.", file=sys.stderr)
        comments, posts_count = fetch_via_apify(args.handle, args.last)

    if not comments:
        print("No comments found.", file=sys.stderr)
        sys.exit(1)

    # Pre-filter
    from filters import filter_comments, filter_results

    comments = filter_comments(comments, text=args.text)
    if not comments:
        print("No comments matched the text filter.", file=sys.stderr)
        sys.exit(1)

    # Extract entities
    from entity_extractor import EntityExtractor

    extractor = EntityExtractor(taxonomy)
    extractions = extractor.extract(comments)

    # Post-filter
    item_filter = args.item or args.car
    extractions = filter_results(extractions, brand=args.brand, item=item_filter)

    # Aggregate
    from output import aggregate_results, build_output, save_json, print_summary

    rankings, brand_summary = aggregate_results(extractions)

    metadata = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "account": f"@{args.handle}",
        "mode": mode,
        "taxonomy": taxonomy.id,
        "taxonomy_name": taxonomy.name,
        "posts_scanned": posts_count,
        "total_comments_analyzed": len(comments),
        "entity_mentions_found": len(extractions),
        "filters_applied": {
            "brand": args.brand,
            "item": item_filter,
            "text": args.text,
        },
    }

    data = build_output(rankings, brand_summary, metadata)

    filepath = save_json(data, args.output)

    if args.quiet:
        print(filepath)
    else:
        print_summary(data)
        print(f"Results saved to: {filepath}", file=sys.stderr)

    if rate_limited:
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
