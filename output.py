import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone


def aggregate_results(extractions):
    """Aggregate entity extractions into ranked results."""
    counts = defaultdict(lambda: {"count": 0, "weighted_score": 0, "comments": []})
    brand_totals = defaultdict(int)

    for ext in extractions:
        brand = ext["brand"]
        model = ext["model"]
        key = (brand, model or "Unknown")
        counts[key]["count"] += 1
        counts[key]["weighted_score"] += 1 + ext.get("comment_like_count", 0)
        if len(counts[key]["comments"]) < 3:
            comment_text = ext["source_comment"]
            if comment_text not in counts[key]["comments"]:
                counts[key]["comments"].append(comment_text)
        brand_totals[brand] += 1

    rankings = []
    for (brand, model), data in sorted(
        counts.items(), key=lambda x: x[1]["count"], reverse=True
    ):
        rankings.append({
            "rank": 0,
            "brand": brand,
            "model": model if model != "Unknown" else None,
            "request_count": data["count"],
            "weighted_score": data["weighted_score"],
            "sample_comments": data["comments"],
        })

    for i, r in enumerate(rankings):
        r["rank"] = i + 1

    brand_summary = [
        {"brand": brand, "total_mentions": total}
        for brand, total in sorted(brand_totals.items(), key=lambda x: x[1], reverse=True)
    ]

    return rankings, brand_summary


def build_output(rankings, brand_summary, metadata):
    return {
        "metadata": metadata,
        "rankings": rankings,
        "brand_summary": brand_summary,
    }


def save_json(data, filepath=None):
    if filepath is None:
        os.makedirs("output", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        taxonomy = data.get("metadata", {}).get("taxonomy", "results")
        filepath = os.path.join("output", f"{taxonomy}_{timestamp}.json")

    parent = os.path.dirname(filepath)
    if parent:
        os.makedirs(parent, exist_ok=True)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return filepath


def print_summary(data):
    handle = data["metadata"].get("account", "")
    posts = data["metadata"].get("posts_scanned", 0)
    taxonomy_name = data["metadata"].get("taxonomy_name", "")
    mentions_key = "entity_mentions_found"
    mentions = data["metadata"].get(mentions_key, 0)

    header = f"{handle}, last {posts} posts"
    if taxonomy_name:
        header = f"{taxonomy_name} — {header}"

    print(f"\n=== Request Rankings ({header}) ===", file=sys.stderr)

    if not data["rankings"]:
        print("  No requests found.", file=sys.stderr)
        return

    for r in data["rankings"][:20]:
        name = r["brand"]
        if r["model"]:
            name += f" {r['model']}"
        print(
            f"  #{r['rank']:<3} {name:<30} {r['request_count']:>3} requests  (score: {r['weighted_score']})",
            file=sys.stderr,
        )

    print(f"\n  Total mentions: {mentions}", file=sys.stderr)
    print(f"  Comments analyzed: {data['metadata']['total_comments_analyzed']}", file=sys.stderr)

    if data["brand_summary"]:
        print("\n  Brand Summary:", file=sys.stderr)
        for b in data["brand_summary"][:10]:
            print(f"    {b['brand']:<25} {b['total_mentions']:>3} mentions", file=sys.stderr)

    print(file=sys.stderr)
