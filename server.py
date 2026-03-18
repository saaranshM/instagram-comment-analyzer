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
from filters import filter_comments, filter_results
from output import aggregate_results, build_output

# Load model once at startup
print("Starting server, loading model...", file=sys.stderr)
extractor = CarExtractor()
print("Server ready.", file=sys.stderr)

app = FastAPI(title="Instagram Comment Analyzer", version="1.0.0")


class AnalyzeRequest(BaseModel):
    last: int
    handle: str = "dreamy.loopz"
    mode: Optional[str] = None
    brand: Optional[str] = None
    car: Optional[str] = None
    text: Optional[str] = None


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
    return {"status": "ok", "model_loaded": True}


@app.post("/analyze")
def analyze(req: AnalyzeRequest):
    mode = _detect_mode(req.mode)

    # Fetch comments
    rate_limited = False
    if mode == "api":
        from instagram_api import fetch_via_api

        comments, posts_count, rate_limited = fetch_via_api(req.handle, req.last)
    else:
        from apify_scraper import fetch_via_apify

        comments, posts_count = fetch_via_apify(req.handle, req.last)

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

    metadata = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "account": f"@{req.handle}",
        "mode": mode,
        "posts_scanned": posts_count,
        "total_comments_analyzed": len(comments),
        "car_mentions_found": len(extractions),
        "filters_applied": {
            "brand": req.brand,
            "car": req.car,
            "text": req.text,
        },
    }

    data = build_output(rankings, brand_summary, metadata)

    if rate_limited:
        data["warning"] = "Rate limited — results may be partial"

    return data


# Convenience GET endpoint
@app.get("/analyze")
def analyze_get(
    last: int,
    handle: str = "dreamy.loopz",
    mode: Optional[str] = None,
    brand: Optional[str] = None,
    car: Optional[str] = None,
    text: Optional[str] = None,
):
    return analyze(AnalyzeRequest(
        last=last, handle=handle, mode=mode, brand=brand, car=car, text=text
    ))
