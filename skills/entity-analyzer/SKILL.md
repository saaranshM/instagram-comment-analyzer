---
name: entity-analyzer
description: Analyze Instagram comments to find the most requested entities (cars, phones, sneakers, etc.) using configurable taxonomies and hybrid NER.
version: 2.0.0
user-invocable: true
metadata:
  openclaw:
    emoji: "A"
    homepage: https://github.com/saaranshM/instagram-comment-analyzer
    primaryEnv: IG_ANALYZER_URL
    requires:
      env:
        - IG_ANALYZER_URL
      bins:
        - curl
        - jq
---

# Entity Analyzer

Analyze Instagram comments to find what followers are requesting most. Supports any domain via configurable taxonomies — cars, phones, sneakers, or custom.

The analyzer server runs a hybrid NER pipeline (GLiNER + fuzzy dictionary) that extracts entity mentions from comments and ranks them by request count.

## Prerequisites

The analyzer server must be running. Set `IG_ANALYZER_URL` to the server address (e.g., `http://localhost:8000`).

## Primary Use Case: Car Requests

The default taxonomy is `cars` — optimized for Indian car content creators whose followers request specific cars in comments.

### What car should I generate next?

When the user asks what to make next, which car is trending, or what video to create:

```
curl -s "$IG_ANALYZER_URL/top?last=20&handle=HANDLE" | jq '.'
```

Example response:
```json
{
  "result": "Maruti Suzuki Baleno",
  "brand": "Maruti Suzuki",
  "model": "Baleno",
  "request_count": 8,
  "weighted_score": 18,
  "sample_comments": ["Please bro baleno video", "New baleno", "New age baleno please"]
}
```

Present the result: car name, request count, and sample comments showing how followers phrase their requests.

### Show me car request rankings

```
curl -s "$IG_ANALYZER_URL/analyze?last=20&handle=HANDLE&top_n=10" | jq '.'
```

Format the rankings as a readable table: rank, car name, request count, score.

### Filter by brand

When the user asks about a specific brand (e.g., "what Hyundai cars are people asking for?"):

```
curl -s "$IG_ANALYZER_URL/analyze?last=20&handle=HANDLE&brand=hyundai" | jq '.'
```

### Filter by car model

When the user asks about a specific car (e.g., "how many people want Creta?"):

```
curl -s "$IG_ANALYZER_URL/analyze?last=20&handle=HANDLE&item=creta" | jq '.'
```

## Using Other Taxonomies

The analyzer supports multiple domains. To use a different taxonomy, add `&taxonomy=TAXONOMY_ID`.

### List available taxonomies

```
curl -s "$IG_ANALYZER_URL/taxonomies" | jq '.'
```

### Analyze with a specific taxonomy

For phones:
```
curl -s "$IG_ANALYZER_URL/analyze?last=10&handle=HANDLE&taxonomy=phones" | jq '.'
```

For sneakers:
```
curl -s "$IG_ANALYZER_URL/analyze?last=10&handle=HANDLE&taxonomy=sneakers" | jq '.'
```

### Top requested entity in any domain

```
curl -s "$IG_ANALYZER_URL/top?last=10&handle=HANDLE&taxonomy=phones" | jq '.'
```

### List brands/groups for a taxonomy

```
curl -s "$IG_ANALYZER_URL/brands?taxonomy=phones" | jq '.'
```

## API Parameters Reference

| Parameter | Type | Description |
|-----------|------|-------------|
| `last` | int | Number of recent posts to analyze (required) |
| `handle` | string | Instagram handle to analyze |
| `taxonomy` | string | Taxonomy to use: cars (default), phones, sneakers, or custom |
| `brand` | string | Filter to specific brand/group |
| `item` | string | Filter to specific item/model |
| `text` | string | Pre-filter comments containing this text |
| `min_score` | int | Minimum weighted score to include |
| `top_n` | int | Limit to top N results |
| `mode` | string | `api` (Graph API) or `scrape` (Apify) |

## Automation Workflow

For automated video/content generation pipelines:

1. Call `GET $IG_ANALYZER_URL/top?last=20&handle=HANDLE` to find the most requested entity.
2. Use the `result` field as input for content generation.
3. The `sample_comments` show how followers phrase requests — useful for titles/captions.
4. After posting, call again to find the next most requested entity.

## Server Health

```
curl -s "$IG_ANALYZER_URL/health" | jq '.'
```

## Reload Taxonomies

After adding or editing a taxonomy YAML file:

```
curl -s -X POST "$IG_ANALYZER_URL/reload" | jq '.'
```

## Guardrails

- Never fabricate request counts or rankings — always call the API.
- If the server is unreachable, tell the user to check if the Docker container is running.
- Do not cache results for more than a few minutes — comment data changes frequently.
- Present exact numbers from the API, do not round or estimate.
