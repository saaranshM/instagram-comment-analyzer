# Instagram Comment Analyzer

Analyze Instagram comments to find the most requested cars. Built for car content creators whose followers comment requesting specific cars for future videos.

Fetches comments, extracts car brand/model mentions using hybrid NER (GLiNER + fuzzy dictionary), and outputs ranked car request counts as JSON.

## How It Works

```
Instagram Comments --> GLiNER NER + Fuzzy Dictionary --> Ranked Car Requests
```

1. **Fetch** comments from Instagram (Graph API or Apify scraper)
2. **Extract** car mentions using hybrid NER:
   - **GLiNER** (`gliner_multi-v2.1`, multilingual) for zero-shot entity discovery
   - **Fuzzy dictionary** (`rapidfuzz`) for misspellings, Hindi-English code-mixing, slang
3. **Aggregate** and rank by request count + like-weighted score
4. **Output** clean JSON for downstream AI agents or manual review

Handles Indian informal text: `"brezza ka video banao bhai"` --> Maruti Suzuki Brezza, `"creata plzz"` --> Hyundai Creta, `"marutisuzki swift"` --> Maruti Suzuki Swift.

## Quick Start

### Docker (Recommended)

The GLiNER model (~1.1GB) is bundled in the repo via Git LFS. No external downloads needed.

```bash
git clone <repo-url>
cd instagram-comment-analyzer

# Configure credentials
cp .env.example .env
# Edit .env — set INSTAGRAM_HANDLE and at least one auth method

# Build and run the server
docker build -t instagram-analyzer .
docker run -d --name ig-analyzer --env-file .env -p 8000:8000 instagram-analyzer

# Test
curl http://localhost:8000/health
curl "http://localhost:8000/analyze?last=5&handle=your_account"
```

### Local Development

```bash
git clone <repo-url>
cd instagram-comment-analyzer

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env

# CLI mode
python fetch_comments.py --handle your_account --last 5

# Server mode (model loads once, handles requests instantly)
uvicorn server:app --host 0.0.0.0 --port 8000
```

## Authentication

Two data fetching modes. Auto-detects: if Instagram API credentials exist, they're preferred; otherwise Apify is used.

### Option 1: Instagram Graph API (Recommended)

Free, 200 calls/hour, no ban risk. Requires the Instagram account owner to generate a token.

**Setup (~5 minutes):**

1. Convert the Instagram account to **Business** or **Creator** (Settings > Account type)
2. Go to [developers.facebook.com](https://developers.facebook.com) > Create App > Business type
3. Add the **Instagram** product to your app
4. Go to [Graph API Explorer](https://developers.facebook.com/tools/explorer/)
5. Select your app, click **Generate Access Token**, log in with Instagram
6. Exchange for a long-lived token (60 days):
   ```bash
   curl "https://graph.instagram.com/access_token\
   ?grant_type=ig_exchange_token\
   &client_secret=YOUR_APP_SECRET\
   &access_token=SHORT_LIVED_TOKEN"
   ```
7. Get your user ID:
   ```bash
   curl "https://graph.instagram.com/me?fields=id,username&access_token=YOUR_TOKEN"
   ```
8. Add to `.env`:
   ```
   INSTAGRAM_ACCESS_TOKEN=your_long_lived_token
   INSTAGRAM_USER_ID=your_user_id
   ```

**Token refresh** (run every ~50 days before the 60-day expiry):
```bash
curl "https://graph.instagram.com/refresh_access_token\
?grant_type=ig_refresh_token\
&access_token=CURRENT_TOKEN"
```

**Permissions needed:** `instagram_basic` + `instagram_manage_comments`

### Option 2: Apify Scraper (No Login)

Free tier ($5/month credits, no credit card required). Works on any public profile without an Instagram account.

1. Sign up at [apify.com](https://apify.com) (free)
2. Get your API token from Settings > Integrations
3. Add to `.env`:
   ```
   APIFY_API_TOKEN=apify_api_XXXXXXXXXXXXXXXXXXXXX
   ```

## API Reference

The server loads the GLiNER model once at startup (~3s). Subsequent requests are instant.

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Server status check |
| `GET` | `/brands` | List all supported car brands and models |
| `GET` | `/top` | Single most requested car (for automation) |
| `GET` | `/analyze` | Full ranked analysis |
| `POST` | `/analyze` | Full ranked analysis (JSON body) |
| `GET` | `/docs` | Interactive Swagger UI |

### `GET /analyze`

```bash
# Basic usage
curl "http://localhost:8000/analyze?last=5&handle=your_account"

# Filter by brand
curl "http://localhost:8000/analyze?last=10&handle=your_account&brand=hyundai"

# Filter by car model
curl "http://localhost:8000/analyze?last=10&handle=your_account&car=creta"

# Pre-filter comments containing specific text
curl "http://localhost:8000/analyze?last=10&handle=your_account&text=please"

# Only results with weighted score >= 10
curl "http://localhost:8000/analyze?last=20&handle=your_account&min_score=10"

# Top 5 results only
curl "http://localhost:8000/analyze?last=20&handle=your_account&top_n=5"

# Force specific fetch mode
curl "http://localhost:8000/analyze?last=5&handle=your_account&mode=scrape"
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `last` | int | **required** | Number of recent posts to analyze |
| `handle` | string | from `INSTAGRAM_HANDLE` env | Instagram handle to analyze |
| `mode` | string | auto-detect | `api` (Graph API) or `scrape` (Apify) |
| `brand` | string | -- | Filter results to this brand |
| `car` | string | -- | Filter results to this car model |
| `text` | string | -- | Pre-filter comments containing this text |
| `min_score` | int | -- | Minimum weighted score to include |
| `top_n` | int | -- | Limit to top N results |

### `POST /analyze`

```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "last": 20,
    "handle": "your_account",
    "brand": "maruti",
    "top_n": 5
  }'
```

### `GET /top`

Returns only the single most requested car. Designed for automation and AI agents.

```bash
curl "http://localhost:8000/top?last=10&handle=your_account"
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

```bash
curl http://localhost:8000/brands
```

### Response Schema

All analysis endpoints return:

```json
{
  "metadata": {
    "fetched_at": "2026-03-19T14:30:22+00:00",
    "account": "@your_account",
    "mode": "api",
    "posts_scanned": 10,
    "total_comments_analyzed": 247,
    "car_mentions_found": 89,
    "filters_applied": { "brand": null, "car": null, "text": null, "min_score": null, "top_n": null }
  },
  "rankings": [
    {
      "rank": 1,
      "brand": "Hyundai",
      "model": "Creta",
      "request_count": 15,
      "weighted_score": 42,
      "sample_comments": ["please make Hyundai Creta video", "creta next plzz"]
    }
  ],
  "brand_summary": [
    { "brand": "Hyundai", "total_mentions": 28 },
    { "brand": "Maruti Suzuki", "total_mentions": 22 }
  ]
}
```

- **`weighted_score`** = `request_count` + sum of `like_count` on those comments
- **`sample_comments`** = up to 3 raw comments per car

## CLI Usage

```bash
python fetch_comments.py --handle your_account --last 5
python fetch_comments.py --handle your_account --last 10 --brand hyundai
python fetch_comments.py --handle your_account --last 10 --car creta
python fetch_comments.py --handle your_account --last 5 --quiet
python fetch_comments.py --handle your_account --last 5 --output results.json
python fetch_comments.py --handle your_account --last 5 --mode api
```

Exit codes: `0` success, `1` fatal error, `2` partial results (rate limited).

## OpenClaw Integration

An OpenClaw skill is included at `skills/car-request-analyzer/`. It lets your OpenClaw agent analyze Instagram car requests via natural language.

### Setup

1. Start the analyzer server:
   ```bash
   docker run -d --env-file .env -p 8000:8000 instagram-analyzer
   ```

2. Copy the skill into your OpenClaw skills directory:
   ```bash
   cp -r skills/car-request-analyzer ~/.openclaw/skills/
   ```

3. Set the environment variable:
   ```bash
   # In your shell or ~/.openclaw/openclaw.json
   export IG_ANALYZER_URL=http://localhost:8000
   ```

4. Configure in `~/.openclaw/openclaw.json` (optional):
   ```json
   {
     "skills": {
       "entries": {
         "car-request-analyzer": {
           "enabled": true,
           "env": {
             "IG_ANALYZER_URL": "http://localhost:8000"
           }
         }
       }
     }
   }
   ```

### Usage with OpenClaw

Once installed, talk to your OpenClaw agent naturally:

- *"What car should I make a video about next?"*
- *"Show me the top 10 car requests"*
- *"How many people are asking for Hyundai cars?"*
- *"What's trending on my Instagram?"*
- *"Analyze the last 50 posts for car requests"*

The skill instructs OpenClaw to call the analyzer API and present the results.

### Integration with Other AI Frameworks

#### LangChain

```python
from langchain.tools import tool
import requests

ANALYZER_URL = "http://localhost:8000"

@tool
def get_most_requested_car(handle: str, last_n_posts: int = 10) -> str:
    """Get the most requested car from Instagram comments.
    Returns the car name that followers are requesting the most."""
    resp = requests.get(f"{ANALYZER_URL}/top", params={"last": last_n_posts, "handle": handle})
    data = resp.json()
    if data.get("car"):
        return f"{data['car']} ({data['request_count']} requests). Comments: {data['sample_comments']}"
    return "No car requests found"

@tool
def get_car_rankings(handle: str, last_n_posts: int = 10, brand: str = None, top_n: int = 5) -> str:
    """Get ranked list of car requests from Instagram comments.
    Optionally filter by brand (e.g. 'hyundai', 'tata', 'maruti')."""
    params = {"last": last_n_posts, "handle": handle, "top_n": top_n}
    if brand:
        params["brand"] = brand
    resp = requests.get(f"{ANALYZER_URL}/analyze", params=params)
    rankings = resp.json()["rankings"]
    lines = [f"#{r['rank']} {r['brand']} {r['model'] or ''}: {r['request_count']} requests" for r in rankings]
    return "\n".join(lines) or "No car requests found"
```

#### CrewAI

```python
from crewai_tools import tool
import requests

@tool("Instagram Car Request Analyzer")
def analyze_car_requests(handle: str, last_n_posts: int = 10) -> str:
    """Analyzes Instagram comments to find which cars followers are requesting."""
    resp = requests.get(f"http://localhost:8000/top", params={"last": last_n_posts, "handle": handle})
    data = resp.json()
    if not data.get("car"):
        return "No car requests found."
    return f"Most requested: {data['car']} ({data['request_count']} requests). Comments: {data['sample_comments']}"
```

#### Raw HTTP (Any Framework)

```bash
# What should I generate next?
curl -s "http://localhost:8000/top?last=20&handle=your_account" | jq '.car'

# Full rankings
curl -s "http://localhost:8000/analyze?last=20&handle=your_account&top_n=5" \
  | jq '.rankings[] | {car: (.brand + " " + (.model // "")), requests: .request_count}'
```

## Supported Cars

~120 models across 25+ brands focused on the Indian market:

**Mass market:** Maruti Suzuki, Hyundai, Tata, Mahindra, Kia, Honda, Toyota, Ford, Chevrolet, Renault, Nissan, Citroen, BYD

**Luxury:** BMW, Mercedes-Benz, Audi, Porsche, Land Rover, Lamborghini, Ferrari, Rolls-Royce

**Others:** MG, Skoda, Volkswagen, Jeep, Royal Enfield

The fuzzy dictionary handles misspellings and Hindi-English code-mixing. New cars can be added by editing `car_dictionary.py`.

## Architecture

```
fetch_comments.py      CLI entry point
server.py              FastAPI server (model loaded once at startup)
instagram_api.py       Instagram Graph API client (v24.0)
apify_scraper.py       Apify scraper client
car_extractor.py       Hybrid NER: GLiNER + fuzzy dictionary
car_dictionary.py      Curated car brands/models with aliases
filters.py             Pre/post comment filtering
output.py              JSON aggregation + console summary
models/                Bundled GLiNER model (Git LFS)
skills/                OpenClaw skill definition
test_api.py            Integration tests with mocked API responses
```

## Tests

```bash
python test_api.py
```

Runs 4 test suites against mocked Instagram Graph API v24.0 responses:
1. API response parsing
2. NER extraction accuracy
3. Full pipeline (fetch -> extract -> aggregate -> JSON)
4. Error handling (expired token, rate limits)
