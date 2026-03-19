# Instagram Comment Analyzer

Analyze Instagram comments to find what followers are requesting most. Supports any domain — cars, phones, sneakers, or anything custom — via simple YAML taxonomy files.

Fetches comments, extracts entity mentions using hybrid NER (GLiNER + fuzzy dictionary), and outputs ranked request counts as JSON.

## How It Works

```
Instagram Comments --> GLiNER NER + Fuzzy Dictionary --> Ranked Entity Requests
```

1. **Fetch** comments from Instagram (Graph API or Apify scraper)
2. **Extract** entity mentions using hybrid NER:
   - **GLiNER** (`gliner_multi-v2.1`, multilingual) — zero-shot entity discovery
   - **Fuzzy dictionary** (`rapidfuzz`) — catches misspellings, slang, code-mixing
3. **Aggregate** and rank by request count + like-weighted score
4. **Output** clean JSON for downstream AI agents or manual review

### Example: Car Requests

The bundled `cars` taxonomy handles Indian informal text out of the box:

- `"brezza ka video banao bhai"` --> Maruti Suzuki Brezza
- `"creata plzz"` --> Hyundai Creta
- `"marutisuzki swift"` --> Maruti Suzuki Swift

```
=== Request Rankings (Cars & Vehicles — @your_account, last 20 posts) ===
  #1   Maruti Suzuki Baleno             8 requests  (score: 18)
  #2   Maruti Suzuki Dzire              6 requests  (score: 16)
  #3   Mahindra Scorpio                 5 requests  (score: 98)
  #4   Maruti Suzuki Brezza             5 requests  (score: 12)
```

## Quick Start

### Docker (Recommended)

```bash
git clone <repo-url>
cd instagram-comment-analyzer

cp .env.example .env
# Edit .env — set INSTAGRAM_HANDLE and at least one auth method

docker build -t instagram-analyzer .
docker run -d --name analyzer --env-file .env -p 8000:8000 instagram-analyzer

# Analyze car requests (default taxonomy)
curl "http://localhost:8000/analyze?last=5&handle=your_account"

# Analyze phone requests
curl "http://localhost:8000/analyze?last=5&handle=your_account&taxonomy=phones"

# What should I generate next?
curl "http://localhost:8000/top?last=10&handle=your_account"
```

### Local Development

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env   # edit with your credentials

# CLI
python fetch_comments.py --handle your_account --last 5
python fetch_comments.py --handle your_account --last 10 --taxonomy phones

# Server (model loads once, requests are instant)
uvicorn server:app --host 0.0.0.0 --port 8000
```

## Taxonomies

A taxonomy is a YAML file that defines what entities to look for. Drop it in `taxonomies/` and it's available immediately.

### Bundled Taxonomies

| ID | Name | Brands | Models | Example |
|----|------|--------|--------|---------|
| `cars` | Cars & Vehicles | 26 | 151 | Maruti Suzuki Baleno, Hyundai Creta |
| `phones` | Smartphones | 10 | 44 | Samsung Galaxy S24, iPhone 16 Pro |
| `sneakers` | Sneakers & Shoes | 7 | 31 | Nike Air Jordan 1, Adidas Yeezy 350 |

### Creating a Custom Taxonomy

Create a YAML file in `taxonomies/`:

```yaml
# taxonomies/your_domain.yaml
taxonomy:
  id: your_domain
  name: "Your Domain Name"
  domain: widget              # auto-derives GLiNER labels: "widget brand", "widget model"
  group_label: brand          # what top-level groups are called
  item_label: model           # what sub-items are called
  reject_words: [common, words, to, ignore, in, this, domain]
  strip_prefixes: ["new ", "old "]

  # Optional: override auto-derived GLiNER labels
  # gliner_labels: ["custom label 1", "custom label 2"]

entities:
  "Brand A":
    aliases: [branda, brand-a, brnd_a]     # misspellings/variations
    models:
      "Product 1": [prod1, product-1, p1]
      "Product 2": [prod2, product-2]

  "Brand B":
    aliases: [brandb]
    models:
      "Item X": [itemx, item-x]
```

Then reload: `curl -X POST localhost:8000/reload`

The GLiNER labels are auto-derived from `domain` + `group_label` + `item_label` (e.g., `"widget brand"`, `"widget model"`, `"widget"`). Override with `gliner_labels` if you need custom phrasing.

## Authentication

Two data fetching modes. Auto-detects: if Instagram API credentials exist, they're preferred.

### Option 1: Instagram Graph API (Recommended)

Free, 200 calls/hour, no ban risk. Requires the account owner to generate a token.

1. Convert account to **Business/Creator** (Settings > Account type)
2. [developers.facebook.com](https://developers.facebook.com) > Create App > Add Instagram product
3. Generate token via [Graph API Explorer](https://developers.facebook.com/tools/explorer/)
4. Exchange for long-lived token (60 days):
   ```bash
   curl "https://graph.instagram.com/access_token?grant_type=ig_exchange_token&client_secret=APP_SECRET&access_token=SHORT_TOKEN"
   ```
5. Get user ID:
   ```bash
   curl "https://graph.instagram.com/me?fields=id,username&access_token=TOKEN"
   ```
6. Add to `.env`:
   ```
   INSTAGRAM_ACCESS_TOKEN=your_long_lived_token
   INSTAGRAM_USER_ID=your_user_id
   ```

Refresh every ~50 days: `curl "https://graph.instagram.com/refresh_access_token?grant_type=ig_refresh_token&access_token=TOKEN"`

### Option 2: Apify Scraper (No Login)

Free tier, works on any public profile.

1. Sign up at [apify.com](https://apify.com) (free)
2. Add to `.env`:
   ```
   APIFY_API_TOKEN=apify_api_XXXXX
   ```

## API Reference

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Server status + loaded taxonomies |
| `GET` | `/taxonomies` | List all taxonomies with metadata |
| `GET` | `/brands?taxonomy=cars` | List groups/items for a taxonomy |
| `GET` | `/top` | Single most requested entity (for automation) |
| `GET/POST` | `/analyze` | Full ranked analysis (with taxonomy) |
| `GET/POST` | `/extract` | Taxonomy-free extraction (just GLiNER labels) |
| `POST` | `/reload` | Reload taxonomies from disk |
| `GET` | `/docs` | Interactive Swagger UI |

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `last` | int | **required** | Number of recent posts to analyze |
| `handle` | string | from env | Instagram handle |
| `taxonomy` | string | `cars` | Taxonomy to use (cars, phones, sneakers, custom) |
| `mode` | string | auto | `api` or `scrape` |
| `brand` | string | -- | Filter by brand/group |
| `item` | string | -- | Filter by item/model |
| `text` | string | -- | Pre-filter comments containing this text |
| `min_score` | int | -- | Minimum weighted score |
| `top_n` | int | -- | Limit to top N results |

### Examples

```bash
# Car requests (default)
curl "localhost:8000/analyze?last=10&handle=car_page"

# Phone requests
curl "localhost:8000/analyze?last=10&handle=tech_reviewer&taxonomy=phones"

# Sneaker requests filtered by Nike
curl "localhost:8000/analyze?last=10&handle=sneaker_page&taxonomy=sneakers&brand=nike"

# Top requested item across any taxonomy
curl "localhost:8000/top?last=20&handle=your_account&taxonomy=phones"

# POST with full options
curl -X POST localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"last": 20, "handle": "your_account", "taxonomy": "cars", "top_n": 5}'

# === Taxonomy-free mode (no YAML needed, just GLiNER labels) ===

# Extract with custom labels — zero config
curl "localhost:8000/extract?last=5&handle=food_page&labels=food%20item,cuisine,dish"

# POST with label array
curl -X POST localhost:8000/extract \
  -H "Content-Type: application/json" \
  -d '{"last": 10, "handle": "travel_page", "labels": ["city", "country", "travel destination"]}'
```

### Taxonomy-free mode (`/extract`)

No YAML taxonomy needed — just pass GLiNER labels and get raw entity extraction. Useful for quick exploration or domains where you don't have a curated dictionary.

**Tradeoffs vs `/analyze` with taxonomy:**
- No fuzzy matching (misspellings won't be corrected)
- No canonical normalization (raw text as-is)
- No reject words (more false positives)
- Works instantly for any domain without config

### Response Schema

```json
{
  "metadata": {
    "fetched_at": "2026-03-19T14:30:22+00:00",
    "account": "@your_account",
    "mode": "api",
    "taxonomy": "cars",
    "taxonomy_name": "Cars & Vehicles",
    "posts_scanned": 10,
    "total_comments_analyzed": 247,
    "entity_mentions_found": 89,
    "filters_applied": { "brand": null, "item": null, "text": null }
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
    { "brand": "Hyundai", "total_mentions": 28 }
  ]
}
```

### `/extract` Response Schema

```json
{
  "metadata": {
    "fetched_at": "2026-03-19T14:30:22+00:00",
    "account": "@your_account",
    "mode": "scrape",
    "taxonomy": null,
    "labels": ["food item", "cuisine", "dish"],
    "posts_scanned": 5,
    "total_comments_analyzed": 120,
    "entity_mentions_found": 34
  },
  "rankings": [
    {
      "rank": 1,
      "entity": "Biryani",
      "label": "dish",
      "request_count": 8,
      "weighted_score": 15,
      "sample_comments": ["biryani recipe please", "make biryani next"]
    }
  ]
}
```

Note: `/extract` returns `entity`/`label` fields (raw GLiNER output). `/analyze` returns `brand`/`model` fields (taxonomy-normalized).

## CLI Usage

### With taxonomy (default — fuzzy matching + GLiNER)

```bash
python fetch_comments.py --handle your_account --last 5
python fetch_comments.py --handle your_account --last 10 --taxonomy phones
python fetch_comments.py --handle your_account --last 10 --taxonomy sneakers --brand nike
python fetch_comments.py --handle your_account --last 10 --item creta
python fetch_comments.py --handle your_account --last 5 --taxonomy-file ./my_custom.yaml
python fetch_comments.py --handle your_account --last 5 --quiet
```

### Without taxonomy (GLiNER only — zero config)

Use `--labels` to skip taxonomy and extract with just GLiNER labels:

```bash
# Extract car mentions without taxonomy
python fetch_comments.py --handle car_page --last 5 --labels "car brand,car model"

# Extract food items
python fetch_comments.py --handle food_page --last 10 --labels "food item,cuisine,dish"

# Extract travel destinations
python fetch_comments.py --handle travel_page --last 10 --labels "city,country,travel destination"

# Extract anything — just describe what you're looking for
python fetch_comments.py --handle any_page --last 5 --labels "product,brand name"
```

## OpenClaw Integration

An OpenClaw skill is included at `skills/entity-analyzer/`.

```bash
# Copy skill to OpenClaw
cp -r skills/entity-analyzer ~/.openclaw/skills/

# Set server URL
export IG_ANALYZER_URL=http://localhost:8000
```

Configure in `~/.openclaw/openclaw.json`:
```json
{
  "skills": {
    "entries": {
      "entity-analyzer": {
        "enabled": true,
        "env": { "IG_ANALYZER_URL": "http://localhost:8000" }
      }
    }
  }
}
```

Then ask naturally: *"What car should I make next?"*, *"Show me phone request rankings"*, *"What sneakers are trending?"*

### LangChain

```python
from langchain.tools import tool
import requests

@tool
def get_top_request(handle: str, taxonomy: str = "cars", last_n: int = 10) -> str:
    """Get the most requested entity from Instagram comments."""
    resp = requests.get("http://localhost:8000/top",
                        params={"last": last_n, "handle": handle, "taxonomy": taxonomy})
    data = resp.json()
    if data.get("result"):
        return f"{data['result']} ({data['request_count']} requests). Comments: {data['sample_comments']}"
    return "No requests found"
```

### Raw HTTP

```bash
curl -s "localhost:8000/top?last=20&handle=your_account" | jq '.result'
```

## Architecture

```
taxonomy.py            Taxonomy loading + registry (YAML/JSON)
entity_extractor.py    Hybrid NER: GLiNER + fuzzy dictionary (domain-agnostic)
taxonomies/            YAML taxonomy files (cars, phones, sneakers, custom)
server.py              FastAPI server (multi-taxonomy, model loaded once)
fetch_comments.py      CLI entry point
instagram_api.py       Instagram Graph API client (v24.0)
apify_scraper.py       Apify scraper client
filters.py             Pre/post comment filtering
output.py              JSON aggregation + console summary
models/                Bundled GLiNER model (Git LFS)
skills/                OpenClaw skill
test_api.py            Integration tests
```

## Tests

```bash
python test_api.py
```
