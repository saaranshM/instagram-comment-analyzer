"""FastAPI server — loads GLiNER model once, supports multiple taxonomies via HTTP."""

import os
import sys
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

load_dotenv()

from taxonomy import TaxonomyRegistry
from entity_extractor import EntityExtractor
from filters import filter_comments, filter_results
from output import aggregate_results, build_output

DEFAULT_HANDLE = os.environ.get("INSTAGRAM_HANDLE", "")
TAXONOMY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "taxonomies")

# Load all taxonomies and create extractors at startup (model loaded once, shared)
print("Starting server, loading taxonomies...", file=sys.stderr)
registry = TaxonomyRegistry(TAXONOMY_DIR)
extractors = {}
for tid in registry.list_ids():
    extractors[tid] = EntityExtractor(registry.get(tid))
print(f"Loaded taxonomies: {', '.join(registry.list_ids())}", file=sys.stderr)
print("Server ready.", file=sys.stderr)

app = FastAPI(
    title="Instagram Comment Analyzer",
    version="2.0.0",
    description="Analyze Instagram comments for entity requests (cars, phones, sneakers, etc.) using hybrid NER.",
)


class AnalyzeRequest(BaseModel):
    last: int
    handle: str = ""
    mode: Optional[str] = None
    taxonomy: Optional[str] = None
    brand: Optional[str] = None
    item: Optional[str] = None
    car: Optional[str] = None  # backward compat alias for item
    text: Optional[str] = None
    min_score: Optional[int] = None
    top_n: Optional[int] = None


def _resolve_handle(handle):
    h = handle or DEFAULT_HANDLE
    if not h:
        raise HTTPException(
            status_code=400,
            detail="Missing 'handle' parameter. Pass ?handle=your_account or set INSTAGRAM_HANDLE in .env",
        )
    return h


def _resolve_taxonomy(taxonomy_id):
    tid = taxonomy_id or "cars"
    if tid not in extractors:
        raise HTTPException(
            status_code=400,
            detail=f"Taxonomy '{tid}' not found. Available: {', '.join(registry.list_ids())}",
        )
    return tid


def _detect_mode(explicit_mode):
    if explicit_mode:
        return explicit_mode
    if os.environ.get("INSTAGRAM_ACCESS_TOKEN") and os.environ.get("INSTAGRAM_USER_ID"):
        return "api"
    if os.environ.get("APIFY_API_TOKEN"):
        return "scrape"
    raise HTTPException(
        status_code=500,
        detail="No credentials. Set INSTAGRAM_ACCESS_TOKEN+INSTAGRAM_USER_ID or APIFY_API_TOKEN in .env",
    )


@app.get("/health")
def health():
    """Check server status and loaded taxonomies."""
    return {
        "status": "ok",
        "model_loaded": True,
        "taxonomies": registry.list_ids(),
    }


@app.get("/taxonomies")
def list_taxonomies():
    """List all loaded taxonomies with metadata."""
    result = []
    for tid in registry.list_ids():
        t = registry.get(tid)
        result.append({
            "id": t.id,
            "name": t.name,
            "domain": t.domain,
            "group_label": t.group_label,
            "item_label": t.item_label,
            "group_count": t.group_count,
            "item_count": t.item_count,
        })
    return {"taxonomies": result, "default": "cars"}


@app.get("/brands")
def list_brands(taxonomy: str = "cars"):
    """List all groups and items for a taxonomy."""
    tid = _resolve_taxonomy(taxonomy)
    t = registry.get(tid)
    result = {}
    for group_name, group_data in t.database.items():
        result[group_name] = list(group_data.get("models", {}).keys())
    return result


@app.get("/top")
def top_item(
    last: int = 10,
    handle: str = "",
    taxonomy: Optional[str] = None,
    mode: Optional[str] = None,
):
    """Get the single most requested entity. Designed for automation."""
    data = _run_analysis(AnalyzeRequest(last=last, handle=handle, taxonomy=taxonomy, mode=mode))
    if not data["rankings"]:
        return {"result": None, "message": "No requests found"}
    top = data["rankings"][0]
    return {
        "result": f"{top['brand']} {top['model']}" if top["model"] else top["brand"],
        "brand": top["brand"],
        "model": top["model"],
        "request_count": top["request_count"],
        "weighted_score": top["weighted_score"],
        "sample_comments": top["sample_comments"],
        "taxonomy": data["metadata"]["taxonomy"],
    }


@app.post("/reload")
def reload_taxonomies():
    """Reload all taxonomies from disk."""
    global extractors
    registry.reload(TAXONOMY_DIR)
    extractors = {}
    for tid in registry.list_ids():
        extractors[tid] = EntityExtractor(registry.get(tid))
    return {"reloaded": registry.list_ids(), "status": "ok"}


def _run_analysis(req: AnalyzeRequest):
    handle = _resolve_handle(req.handle)
    tid = _resolve_taxonomy(req.taxonomy)
    mode = _detect_mode(req.mode)
    t = registry.get(tid)
    extractor = extractors[tid]

    # Fetch comments
    rate_limited = False
    if mode == "api":
        from instagram_api import fetch_via_api
        comments, posts_count, rate_limited = fetch_via_api(handle, req.last)
    else:
        from apify_scraper import fetch_via_apify
        comments, posts_count = fetch_via_apify(handle, req.last)

    if not comments:
        raise HTTPException(status_code=404, detail="No comments found")

    comments = filter_comments(comments, text=req.text)
    if not comments:
        raise HTTPException(status_code=404, detail="No comments matched the text filter")

    extractions = extractor.extract(comments)

    # item= or car= (backward compat)
    item_filter = req.item or req.car
    extractions = filter_results(extractions, brand=req.brand, item=item_filter)

    rankings, brand_summary = aggregate_results(extractions)

    if req.min_score:
        rankings = [r for r in rankings if r["weighted_score"] >= req.min_score]
        for i, r in enumerate(rankings):
            r["rank"] = i + 1

    if req.top_n:
        rankings = rankings[:req.top_n]

    metadata = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "account": f"@{handle}",
        "mode": mode,
        "taxonomy": tid,
        "taxonomy_name": t.name,
        "posts_scanned": posts_count,
        "total_comments_analyzed": len(comments),
        "entity_mentions_found": len(extractions),
        "filters_applied": {
            "brand": req.brand,
            "item": item_filter,
            "text": req.text,
            "min_score": req.min_score,
            "top_n": req.top_n,
        },
    }

    data = build_output(rankings, brand_summary, metadata)

    if rate_limited:
        data["warning"] = "Rate limited — results may be partial"

    return data


@app.post("/analyze")
def analyze(req: AnalyzeRequest):
    """Full analysis with all filter options."""
    return _run_analysis(req)


@app.get("/analyze")
def analyze_get(
    last: int,
    handle: str = "",
    taxonomy: Optional[str] = None,
    mode: Optional[str] = None,
    brand: Optional[str] = None,
    item: Optional[str] = None,
    car: Optional[str] = None,
    text: Optional[str] = None,
    min_score: Optional[int] = None,
    top_n: Optional[int] = None,
):
    """Full analysis via GET."""
    return _run_analysis(AnalyzeRequest(
        last=last, handle=handle, taxonomy=taxonomy, mode=mode,
        brand=brand, item=item, car=car, text=text,
        min_score=min_score, top_n=top_n,
    ))
