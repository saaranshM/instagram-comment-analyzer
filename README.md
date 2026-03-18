# Instagram Comment Analyzer

Analyze Instagram comments to find the most requested cars. Built for [@dreamy.loopz](https://www.instagram.com/dreamy.loopz/) — an AI car video page where followers comment requesting specific cars.

Fetches comments, extracts car brand/model mentions using hybrid NER (GLiNER + fuzzy dictionary), and outputs ranked car request counts as JSON.

## How It Works

```
Instagram Comments → GLiNER NER + Fuzzy Dictionary → Ranked Car Requests
```

1. **Fetch** comments from Instagram (Graph API or Apify scraper)
2. **Extract** car mentions using hybrid NER:
   - **GLiNER** (`gliner_multi-v2.1`, multilingual) — zero-shot entity discovery
   - **Fuzzy dictionary** (`rapidfuzz`) — catches misspellings, Hindi-English code-mixing, slang
3. **Aggregate** and rank by request count + like-weighted score
4. **Output** clean JSON for downstream AI agents

Handles Indian informal text: `"brezza ka video banao bhai"` → Maruti Suzuki Brezza, `"creata plzz"` → Hyundai Creta, `"marutisuzki swift"` → Maruti Suzuki Swift.

## Quick Start

### Docker (Recommended)

GLiNER model (~1.1GB) is bundled in the repo via Git LFS. No external downloads needed.

```bash
git clone <repo-url>
cd instagram-comment-analyzer

# Configure credentials (see "Authentication" section below)
cp .env.example .env
# Edit .env with your credentials

# Build and run
docker build -t instagram-analyzer .
docker run -d --name ig-analyzer --env-file .env -p 8000:8000 instagram-analyzer

# Test
curl http://localhost:8000/health
curl "http://localhost:8000/analyze?last=5"
```

### Local Development

```bash
git clone <repo-url>
cd instagram-comment-analyzer

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env with your credentials

# CLI mode
python fetch_comments.py --last 5

# Server mode
uvicorn server:app --host 0.0.0.0 --port 8000
```

## Authentication

The tool supports two data fetching modes. Credentials auto-detect: if Instagram API credentials exist, they're used; otherwise Apify is used.

### Option 1: Instagram Graph API (Recommended)

Free, 200 calls/hour, no ban risk. Requires the account owner to generate a token.

**Setup (account owner does this once, ~5 minutes):**

1. Convert Instagram account to **Business** or **Creator** (Settings > Account type)
2. Go to [developers.facebook.com](https://developers.facebook.com) > Create App > Business type
3. Add the **Instagram** product to your app
4. Go to [Graph API Explorer](https://developers.facebook.com/tools/explorer/)
5. Select your app, click **Generate Access Token**, log in with Instagram
6. Copy the short-lived token, then exchange for a long-lived token (60 days):
   ```
   curl "https://graph.instagram.com/access_token?grant_type=ig_exchange_token&client_secret=YOUR_APP_SECRET&access_token=SHORT_LIVED_TOKEN"
   ```
7. Get your user ID:
   ```
   curl "https://graph.instagram.com/me?fields=id,username&access_token=YOUR_TOKEN"
   ```
8. Add to `.env`:
   ```
   INSTAGRAM_ACCESS_TOKEN=your_long_lived_token
   INSTAGRAM_USER_ID=your_user_id
   ```

**Token refresh** (every ~50 days before the 60-day expiry):
```
curl "https://graph.instagram.com/refresh_access_token?grant_type=ig_refresh_token&access_token=CURRENT_TOKEN"
```

**Permissions needed:** `instagram_basic` + `instagram_manage_comments`

### Option 2: Apify Scraper (No Login)

Free tier ($5/month credits, no credit card), works on any public profile, no Instagram account needed.

1. Sign up at [apify.com](https://apify.com) (free)
2. Get your API token from Settings > Integrations
3. Add to `.env`:
   ```
   APIFY_API_TOKEN=apify_api_XXXXXXXXXXXXXXXXXXXXX
   ```

## API Reference

The server loads the GLiNER model once at startup (~3s), then handles requests instantly.

### `GET /health`

Check server status.

```bash
curl http://localhost:8000/health
```
```json
{"status": "ok", "model_loaded": true}
```

### `GET /analyze`

Full analysis with query parameters.

```bash
# Basic — analyze last 5 posts
curl "http://localhost:8000/analyze?last=5"

# Filter by brand
curl "http://localhost:8000/analyze?last=10&brand=hyundai"

# Filter by car model
curl "http://localhost:8000/analyze?last=10&car=creta"

# Pre-filter comments containing specific text
curl "http://localhost:8000/analyze?last=10&text=please"

# Only results with weighted score >= 10
curl "http://localhost:8000/analyze?last=20&min_score=10"

# Top 5 results only
curl "http://localhost:8000/analyze?last=20&top_n=5"

# Different Instagram handle
curl "http://localhost:8000/analyze?last=5&handle=other_account"

# Force specific fetch mode
curl "http://localhost:8000/analyze?last=5&mode=scrape"
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `last` | int | **required** | Number of recent posts to analyze |
| `handle` | string | `dreamy.loopz` | Instagram handle |
| `mode` | string | auto | `api` (Graph API) or `scrape` (Apify) |
| `brand` | string | — | Filter results to this brand |
| `car` | string | — | Filter results to this car model |
| `text` | string | — | Pre-filter comments containing this text |
| `min_score` | int | — | Minimum weighted score to include |
| `top_n` | int | — | Limit to top N results |

### `POST /analyze`

Same options as GET, but via JSON body.

```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "last": 20,
    "handle": "dreamy.loopz",
    "brand": "maruti",
    "top_n": 5
  }'
```

### `GET /top`

Returns only the single most requested car. Designed for automation.

```bash
curl "http://localhost:8000/top?last=10"
```
```json
{
  "car": "Maruti Suzuki Baleno",
  "brand": "Maruti Suzuki",
  "model": "Baleno",
  "request_count": 8,
  "weighted_score": 18,
  "sample_comments": [
    "Please bro baleno video",
    "New baleno",
    "New age baleno please"
  ]
}
```

### `GET /brands`

List all supported car brands and models in the dictionary.

```bash
curl http://localhost:8000/brands
```

### Interactive API Docs

FastAPI auto-generates interactive docs:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Response Schema

All analysis endpoints return this JSON structure:

```json
{
  "metadata": {
    "fetched_at": "2026-03-19T14:30:22+00:00",
    "account": "@dreamy.loopz",
    "mode": "scrape",
    "posts_scanned": 10,
    "total_comments_analyzed": 247,
    "car_mentions_found": 89,
    "filters_applied": {
      "brand": null,
      "car": null,
      "text": null,
      "min_score": null,
      "top_n": null
    }
  },
  "rankings": [
    {
      "rank": 1,
      "brand": "Hyundai",
      "model": "Creta",
      "request_count": 15,
      "weighted_score": 42,
      "sample_comments": [
        "please make Hyundai Creta video",
        "creta next plzz",
        "creata ka video banao bhai"
      ]
    }
  ],
  "brand_summary": [
    {"brand": "Hyundai", "total_mentions": 28},
    {"brand": "Maruti Suzuki", "total_mentions": 22}
  ]
}
```

- **`rankings`** — sorted by `request_count` descending. Each entry = one car model.
- **`weighted_score`** — `request_count` + sum of `like_count` on those comments. A comment with 10 likes is a stronger signal.
- **`sample_comments`** — up to 3 raw comments per car for context.
- **`brand_summary`** — brand-level aggregation.

## CLI Usage

For one-off analysis without running a server:

```bash
python fetch_comments.py --last 5
python fetch_comments.py --last 10 --brand hyundai
python fetch_comments.py --last 10 --car creta
python fetch_comments.py --last 10 --text "please make"
python fetch_comments.py --last 5 --quiet              # only output JSON path
python fetch_comments.py --last 5 --output results.json
python fetch_comments.py --last 5 --mode api            # force Graph API
python fetch_comments.py --last 5 --handle other_account
```

Exit codes: `0` success, `1` fatal error, `2` partial results (rate limited).

## Integrating with Agentic AI (Openclaw / LangChain / CrewAI)

The API is designed to be called by AI agents that decide what video to generate next.

### Openclaw Integration

Configure your openclaw agent to call the analyzer as a tool:

```yaml
# openclaw tool definition
tools:
  - name: get_car_requests
    description: "Get the most requested cars from Instagram comments on @dreamy.loopz"
    endpoint: http://localhost:8000/top?last=10
    method: GET
    response_path: $.car
```

Or for full rankings:

```yaml
tools:
  - name: analyze_car_requests
    description: "Analyze Instagram comments for car video requests. Returns ranked list of requested cars with counts."
    endpoint: http://localhost:8000/analyze
    method: POST
    parameters:
      last:
        type: integer
        description: "Number of recent posts to analyze"
        required: true
      brand:
        type: string
        description: "Filter to specific brand (e.g. 'hyundai', 'maruti')"
      top_n:
        type: integer
        description: "Limit to top N results"
    response_path: $.rankings
```

**Agent workflow:**
1. Agent calls `GET /top?last=20` to find the most requested car
2. Response: `{"car": "Maruti Suzuki Baleno", "request_count": 8, ...}`
3. Agent triggers video generation for "Maruti Suzuki Baleno"
4. After posting, agent calls again to find the next most requested car

### LangChain Integration

```python
from langchain.tools import tool
import requests

@tool
def get_most_requested_car(last_n_posts: int = 10) -> str:
    """Get the most requested car from Instagram comments on @dreamy.loopz.
    Returns the car name that followers are requesting the most."""
    resp = requests.get(f"http://localhost:8000/top?last={last_n_posts}")
    data = resp.json()
    if data.get("car"):
        return f"{data['car']} ({data['request_count']} requests). Sample comments: {data['sample_comments']}"
    return "No car requests found"

@tool
def get_car_rankings(last_n_posts: int = 10, brand: str = None, top_n: int = 5) -> str:
    """Get ranked list of car requests from Instagram comments.
    Optionally filter by brand (e.g. 'hyundai', 'tata', 'maruti')."""
    params = {"last": last_n_posts, "top_n": top_n}
    if brand:
        params["brand"] = brand
    resp = requests.get("http://localhost:8000/analyze", params=params)
    data = resp.json()
    lines = []
    for r in data["rankings"]:
        name = f"{r['brand']} {r['model']}" if r["model"] else r["brand"]
        lines.append(f"#{r['rank']} {name}: {r['request_count']} requests (score: {r['weighted_score']})")
    return "\n".join(lines) if lines else "No car requests found"
```

### CrewAI Integration

```python
from crewai_tools import tool
import requests

@tool("Instagram Car Request Analyzer")
def analyze_car_requests(last_n_posts: int = 10) -> str:
    """Analyzes Instagram comments on @dreamy.loopz to find which cars
    followers are requesting. Returns the top requested car with sample
    comments showing the exact phrasing followers use."""
    resp = requests.get(f"http://localhost:8000/top?last={last_n_posts}")
    data = resp.json()
    if not data.get("car"):
        return "No car requests found in recent comments."
    return (
        f"Most requested: {data['car']} with {data['request_count']} requests "
        f"(weighted score: {data['weighted_score']}). "
        f"Sample comments: {', '.join(data['sample_comments'])}"
    )
```

### Raw HTTP (Any Agent Framework)

```bash
# Simple — what should I generate next?
curl -s http://localhost:8000/top?last=20 | jq '.car'
# → "Maruti Suzuki Baleno"

# Full rankings as JSON for agent consumption
curl -s "http://localhost:8000/analyze?last=20&top_n=5" | jq '.rankings[] | {car: (.brand + " " + (.model // "")), requests: .request_count}'

# Brand-specific analysis
curl -s "http://localhost:8000/analyze?last=20&brand=hyundai" | jq '.rankings'
```

## Supported Cars

~120 models across 25+ brands focused on the Indian market:

**Mass market:** Maruti Suzuki (Swift, Baleno, Brezza, Dzire, Ertiga, WagonR, Fronx, Alto, Grand Vitara, ...), Hyundai (Creta, Venue, i20, Verna, Exter, ...), Tata (Nexon, Punch, Harrier, Safari, Altroz, ...), Mahindra (Thar, XUV700, Scorpio, Bolero, ...), Kia (Seltos, Sonet, Carens, ...), Honda, Toyota, Ford, Chevrolet, Renault, Nissan

**Luxury:** BMW, Mercedes-Benz, Audi, Porsche, Land Rover, Lamborghini, Ferrari, Rolls-Royce

**Others:** MG, Skoda, Volkswagen, Jeep, Citroen, BYD, Royal Enfield

The fuzzy dictionary handles common misspellings (`"creata"` → Creta, `"marutisuzki"` → Maruti Suzuki, `"breeza"` → Brezza) and Hindi-English code-mixing.

New cars/brands can be added by editing `car_dictionary.py`.

## Architecture

```
fetch_comments.py      CLI entry point
server.py              FastAPI server (model loaded once)
instagram_api.py       Instagram Graph API client (v24.0)
apify_scraper.py       Apify scraper client
car_extractor.py       Hybrid NER: GLiNER + fuzzy dictionary
car_dictionary.py      Curated car brands/models with aliases
filters.py             Pre/post comment filtering
output.py              JSON aggregation + console summary
models/                Bundled GLiNER model (Git LFS)
test_api.py            Integration tests with mocked API responses
```

## Tests

```bash
python test_api.py
```

Runs 4 test suites against mocked Instagram Graph API v24.0 responses:
1. API response parsing
2. NER extraction accuracy
3. Full pipeline (fetch → extract → aggregate → JSON)
4. Error handling (expired token, rate limits)
