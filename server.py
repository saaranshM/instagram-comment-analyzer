"""FastAPI server — loads GLiNER model once, accepts analysis requests via HTTP."""

import os
import sys
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

load_dotenv()

from car_extractor import CarExtractor
from car_dictionary import CAR_DATABASE
from filters import filter_comments, filter_results
from output import aggregate_results, build_output

DEFAULT_HANDLE = os.environ.get("INSTAGRAM_HANDLE", "")

# Load model once at startup
print("Starting server, loading model...", file=sys.stderr)
extractor = CarExtractor()
print("Server ready.", file=sys.stderr)

app = FastAPI(
    title="Instagram Comment Analyzer",
    version="1.0.0",
    description="Analyze Instagram comments for car requests using hybrid NER (GLiNER + fuzzy dictionary).",
)


class AnalyzeRequest(BaseModel):
    last: int
    handle: str = ""
    mode: Optional[str] = None
    brand: Optional[str] = None
    car: Optional[str] = None
    text: Optional[str] = None
    min_score: Optional[int] = None
    top_n: Optional[int] = None


def _resolve_handle(handle):
    """Resolve handle from request, env default, or error."""
    h = handle or DEFAULT_HANDLE
    if not h:
        raise HTTPException(
            status_code=400,
            detail="Missing 'handle' parameter. Pass ?handle=your_account or set INSTAGRAM_HANDLE in .env",
        )
    return h


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
    """Check server status and model readiness."""
    return {"status": "ok", "model_loaded": True}


@app.get("/brands")
def list_brands():
    """List all supported car brands and their models."""
    result = {}
    for brand, data in CAR_DATABASE.items():
        result[brand] = list(data["models"].keys())
    return result


@app.get("/top")
def top_car(
    last: int = 10,
    handle: str = "",
    mode: Optional[str] = None,
):
    """Get just the single most requested car. Designed for automation."""
    data = _run_analysis(AnalyzeRequest(last=last, handle=handle, mode=mode))
    if not data["rankings"]:
        return {"car": None, "message": "No car requests found"}
    top = data["rankings"][0]
    return {
        "car": f"{top['brand']} {top['model']}" if top["model"] else top["brand"],
        "brand": top["brand"],
        "model": top["model"],
        "request_count": top["request_count"],
        "weighted_score": top["weighted_score"],
        "sample_comments": top["sample_comments"],
    }


def _run_analysis(req: AnalyzeRequest):
    """Core analysis pipeline shared by all endpoints."""
    handle = _resolve_handle(req.handle)
    mode = _detect_mode(req.mode)

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

    # Pre-filter
    comments = filter_comments(comments, text=req.text)
    if not comments:
        raise HTTPException(status_code=404, detail="No comments matched the text filter")

    # Extract car mentions (model already loaded)
    extractions = extractor.extract(comments)

    # Post-filter
    extractions = filter_results(extractions, brand=req.brand, car=req.car)

    # Aggregate
    rankings, brand_summary = aggregate_results(extractions)

    # Apply min_score filter
    if req.min_score:
        rankings = [r for r in rankings if r["weighted_score"] >= req.min_score]
        for i, r in enumerate(rankings):
            r["rank"] = i + 1

    # Apply top_n limit
    if req.top_n:
        rankings = rankings[: req.top_n]

    metadata = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "account": f"@{handle}",
        "mode": mode,
        "posts_scanned": posts_count,
        "total_comments_analyzed": len(comments),
        "car_mentions_found": len(extractions),
        "filters_applied": {
            "brand": req.brand,
            "car": req.car,
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
    """Full analysis with all filter options. Returns ranked car requests."""
    return _run_analysis(req)


@app.get("/analyze")
def analyze_get(
    last: int,
    handle: str = "",
    mode: Optional[str] = None,
    brand: Optional[str] = None,
    car: Optional[str] = None,
    text: Optional[str] = None,
    min_score: Optional[int] = None,
    top_n: Optional[int] = None,
):
    """Full analysis via GET. Same as POST /analyze but with query params."""
    return _run_analysis(AnalyzeRequest(
        last=last, handle=handle, mode=mode, brand=brand,
        car=car, text=text, min_score=min_score, top_n=top_n,
    ))
