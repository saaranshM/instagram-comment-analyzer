import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone


def aggregate_results(extractions):
    """Aggregate car extractions into ranked results.

    Returns (rankings, brand_summary) where:
    - rankings: list of dicts sorted by request_count descending
    - brand_summary: list of dicts with brand-level totals
    """
    # Group by (brand, model)
    car_counts = defaultdict(lambda: {"count": 0, "weighted_score": 0, "comments": []})
    brand_totals = defaultdict(int)

    for ext in extractions:
        brand = ext["brand"]
        model = ext["model"]
        key = (brand, model or "Unknown")
        car_counts[key]["count"] += 1
        car_counts[key]["weighted_score"] += 1 + ext.get("comment_like_count", 0)
        # Keep up to 3 sample comments
        if len(car_counts[key]["comments"]) < 3:
            comment_text = ext["source_comment"]
            if comment_text not in car_counts[key]["comments"]:
                car_counts[key]["comments"].append(comment_text)
        brand_totals[brand] += 1

    # Build rankings sorted by count descending
    rankings = []
    for (brand, model), data in sorted(
        car_counts.items(), key=lambda x: x[1]["count"], reverse=True
    ):
        rankings.append(
            {
                "rank": 0,  # filled below
                "brand": brand,
                "model": model if model != "Unknown" else None,
                "request_count": data["count"],
                "weighted_score": data["weighted_score"],
                "sample_comments": data["comments"],
            }
        )

    for i, r in enumerate(rankings):
        r["rank"] = i + 1

    # Build brand summary sorted by total descending
    brand_summary = [
        {"brand": brand, "total_mentions": total}
        for brand, total in sorted(brand_totals.items(), key=lambda x: x[1], reverse=True)
    ]

    return rankings, brand_summary


def build_output(rankings, brand_summary, metadata):
    """Build the full output dict matching the JSON schema."""
    return {
        "metadata": metadata,
        "rankings": rankings,
        "brand_summary": brand_summary,
    }


def save_json(data, filepath=None):
    """Save output JSON to file. Auto-generates path if none given."""
    if filepath is None:
        os.makedirs("output", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join("output", f"car_requests_{timestamp}.json")

    # Ensure parent directory exists
    parent = os.path.dirname(filepath)
    if parent:
        os.makedirs(parent, exist_ok=True)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return filepath


def print_summary(data):
    """Print ranked car request table to stderr."""
    handle = data["metadata"].get("account", "")
    posts = data["metadata"].get("posts_scanned", 0)

    print(
        f"\n=== Car Request Rankings ({handle}, last {posts} posts) ===",
        file=sys.stderr,
    )

    if not data["rankings"]:
        print("  No car requests found.", file=sys.stderr)
        return

    for r in data["rankings"][:20]:
        name = r["brand"]
        if r["model"]:
            name += f" {r['model']}"
        print(
            f"  #{r['rank']:<3} {name:<30} {r['request_count']:>3} requests  (score: {r['weighted_score']})",
            file=sys.stderr,
        )

    print(f"\n  Total car mentions: {data['metadata']['car_mentions_found']}", file=sys.stderr)
    print(
        f"  Comments analyzed: {data['metadata']['total_comments_analyzed']}",
        file=sys.stderr,
    )

    if data["brand_summary"]:
        print("\n  Brand Summary:", file=sys.stderr)
        for b in data["brand_summary"][:10]:
            print(f"    {b['brand']:<25} {b['total_mentions']:>3} mentions", file=sys.stderr)

    print(file=sys.stderr)
