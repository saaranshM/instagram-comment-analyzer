#!/usr/bin/env python3
"""Instagram Comment Analyzer CLI — fetch comments, extract entity requests, output rankings."""

import argparse
import json
import sys
import os
from collections import defaultdict
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


def _fetch_comments(handle, last, mode):
    """Fetch comments from Instagram. Returns (comments, posts_count, rate_limited)."""
    rate_limited = False
    if mode == "api":
        from instagram_api import fetch_via_api
        print("Using Instagram Graph API.", file=sys.stderr)
        comments, posts_count, rate_limited = fetch_via_api(handle, last)
    else:
        from apify_scraper import fetch_via_apify
        print("Using Apify scraper.", file=sys.stderr)
        comments, posts_count = fetch_via_apify(handle, last)
    return comments, posts_count, rate_limited


def _run_taxonomy_mode(args, comments, posts_count, rate_limited):
    """Taxonomy-enhanced extraction: fuzzy dictionary + GLiNER."""
    from taxonomy import Taxonomy, TaxonomyRegistry
    from entity_extractor import EntityExtractor
    from filters import filter_comments, filter_results
    from output import aggregate_results, build_output, save_json, print_summary

    if args.taxonomy_file:
        taxonomy = Taxonomy(args.taxonomy_file)
    else:
        taxonomy_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "taxonomies")
        reg = TaxonomyRegistry(taxonomy_dir)
        taxonomy = reg.get(args.taxonomy)

    comments = filter_comments(comments, text=args.text)
    if not comments:
        print("No comments matched the text filter.", file=sys.stderr)
        sys.exit(1)

    extractor = EntityExtractor(taxonomy)
    extractions = extractor.extract(comments)

    item_filter = args.item or args.car
    extractions = filter_results(extractions, brand=args.brand, item=item_filter)

    rankings, brand_summary = aggregate_results(extractions)

    metadata = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "account": f"@{args.handle}",
        "mode": args.mode or "auto",
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


def _run_extract_mode(args, comments, posts_count, rate_limited):
    """Taxonomy-free extraction: GLiNER only with user-provided labels."""
    from entity_extractor import RawExtractor
    from filters import filter_comments
    from output import save_json

    labels = [l.strip() for l in args.labels.split(",") if l.strip()]
    if not labels:
        print("Error: --labels must be a non-empty comma-separated string.", file=sys.stderr)
        sys.exit(1)

    comments = filter_comments(comments, text=args.text)
    if not comments:
        print("No comments matched the text filter.", file=sys.stderr)
        sys.exit(1)

    raw = RawExtractor(labels)
    extractions = raw.extract(comments)

    # Aggregate by entity text
    counts = defaultdict(lambda: {"count": 0, "weighted_score": 0, "comments": [], "label": ""})
    for ext in extractions:
        key = ext["entity"]
        counts[key]["count"] += 1
        counts[key]["weighted_score"] += 1 + ext.get("comment_like_count", 0)
        counts[key]["label"] = ext["label"]
        if len(counts[key]["comments"]) < 3:
            c = ext["source_comment"]
            if c not in counts[key]["comments"]:
                counts[key]["comments"].append(c)

    rankings = sorted(
        [{"rank": 0, "entity": k, "label": v["label"], "request_count": v["count"],
          "weighted_score": v["weighted_score"], "sample_comments": v["comments"]}
         for k, v in counts.items()],
        key=lambda x: x["request_count"], reverse=True,
    )
    for i, r in enumerate(rankings):
        r["rank"] = i + 1

    data = {
        "metadata": {
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "account": f"@{args.handle}",
            "mode": args.mode or "auto",
            "taxonomy": None,
            "labels": labels,
            "posts_scanned": posts_count,
            "total_comments_analyzed": len(comments),
            "entity_mentions_found": len(extractions),
        },
        "rankings": rankings,
    }

    if rate_limited:
        data["warning"] = "Rate limited — results may be partial"

    filepath = save_json(data, args.output)

    if args.quiet:
        print(filepath)
    else:
        print(f"\n=== Raw Extraction (labels: {', '.join(labels)}) ===", file=sys.stderr)
        for r in rankings[:20]:
            print(
                f"  #{r['rank']:<3} {r['entity']:<30} [{r['label']}]  {r['request_count']:>3} mentions",
                file=sys.stderr,
            )
        print(f"\n  Total mentions: {len(extractions)}", file=sys.stderr)
        print(f"  Comments analyzed: {len(comments)}\n", file=sys.stderr)
        print(f"Results saved to: {filepath}", file=sys.stderr)

    if rate_limited:
        sys.exit(2)
    sys.exit(0)


def main():
    parser = argparse.ArgumentParser(
        description="Analyze Instagram comments for entity requests (cars, phones, sneakers, etc.)"
    )
    parser.add_argument("--last", type=int, required=True, help="Number of recent posts to fetch")
    parser.add_argument("--mode", choices=["scrape", "api"], default=None,
                        help="Fetch mode: api or scrape. Auto-detects if omitted.")
    parser.add_argument("--handle", default=os.environ.get("INSTAGRAM_HANDLE", ""),
                        help="Instagram handle. Or set INSTAGRAM_HANDLE in .env")

    # Taxonomy mode (default)
    parser.add_argument("--taxonomy", default="cars",
                        help="Taxonomy to use (e.g. cars, phones, sneakers). Default: cars")
    parser.add_argument("--taxonomy-file", default=None,
                        help="Load taxonomy from a specific YAML/JSON file")
    parser.add_argument("--brand", help="Filter results to this brand/group")
    parser.add_argument("--item", help="Filter results to this item/model")
    parser.add_argument("--car", help="Alias for --item (backward compat)")

    # Taxonomy-free mode
    parser.add_argument("--labels", default=None,
                        help="Taxonomy-free mode: comma-separated GLiNER labels "
                             "(e.g. 'car brand,car model' or 'food item,cuisine'). "
                             "Skips taxonomy, uses only GLiNER zero-shot extraction.")

    # Common
    parser.add_argument("--text", help="Pre-filter comments containing this text")
    parser.add_argument("--output", help="Output JSON file path (auto-generated if omitted)")
    parser.add_argument("--quiet", action="store_true", help="Suppress console summary")
    args = parser.parse_args()

    load_dotenv()

    if not args.handle:
        print("Error: No handle. Use --handle or set INSTAGRAM_HANDLE in .env", file=sys.stderr)
        sys.exit(1)

    mode = _detect_mode(args.mode)
    comments, posts_count, rate_limited = _fetch_comments(args.handle, args.last, mode)

    if not comments:
        print("No comments found.", file=sys.stderr)
        sys.exit(1)

    if args.labels:
        _run_extract_mode(args, comments, posts_count, rate_limited)
    else:
        _run_taxonomy_mode(args, comments, posts_count, rate_limited)


if __name__ == "__main__":
    main()
