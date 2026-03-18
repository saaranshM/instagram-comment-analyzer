---
name: car-request-analyzer
description: Analyze Instagram comments to find the most requested cars. Fetches comments, extracts car brand/model mentions using NER, and returns ranked results.
version: 1.0.0
user-invocable: true
metadata:
  openclaw:
    emoji: "C"
    homepage: https://github.com/saaranshmenon/instagram-comment-analyzer
    primaryEnv: IG_ANALYZER_URL
    requires:
      env:
        - IG_ANALYZER_URL
      bins:
        - curl
        - jq
---

# Car Request Analyzer

Analyze Instagram comments to find which cars followers are requesting most. Uses a running Instagram Comment Analyzer server that extracts car mentions using hybrid NER (GLiNER + fuzzy dictionary).

## Prerequisites

The Instagram Comment Analyzer server must be running. Set `IG_ANALYZER_URL` to the server address (e.g., `http://localhost:8000`).

## Commands

### What car should I generate next?

When the user asks what car video to make, which car is most requested, or what to generate next:

1. Call the `/top` endpoint to get the single most requested car:
   ```
   curl -s "$IG_ANALYZER_URL/top?last=20" | jq '.'
   ```
2. Present the result: car name, request count, weighted score, and sample comments.
3. Suggest this as the next video to generate.

### Show me car request rankings

When the user wants to see full rankings or a breakdown:

1. Call the `/analyze` endpoint:
   ```
   curl -s "$IG_ANALYZER_URL/analyze?last=20&top_n=10" | jq '.'
   ```
2. Format the rankings as a readable table showing rank, car name, request count, and score.
3. Also show the brand summary at the end.

### Filter by brand

When the user asks about a specific brand (e.g., "what Hyundai cars are people asking for?"):

1. Extract the brand name from the user's message.
2. Call:
   ```
   curl -s "$IG_ANALYZER_URL/analyze?last=20&brand=BRAND_NAME" | jq '.'
   ```
3. Show only that brand's results.

### Filter by car model

When the user asks about a specific car (e.g., "how many people want Creta?"):

1. Extract the model name.
2. Call:
   ```
   curl -s "$IG_ANALYZER_URL/analyze?last=20&car=MODEL_NAME" | jq '.'
   ```

### Analyze a different account

When the user specifies a different Instagram handle:

1. Extract the handle (strip the `@` prefix if present).
2. Call:
   ```
   curl -s "$IG_ANALYZER_URL/analyze?last=20&handle=HANDLE" | jq '.'
   ```

### List supported car brands

When the user asks what brands are supported or recognized:

```
curl -s "$IG_ANALYZER_URL/brands" | jq '.'
```

### Check server health

When the user asks if the analyzer is running or there's a connection issue:

```
curl -s "$IG_ANALYZER_URL/health" | jq '.'
```

## Automation Workflow

When integrated into a video generation pipeline:

1. Call `GET $IG_ANALYZER_URL/top?last=20` to find the most requested car.
2. Use the `car` field from the response as the input for video generation.
3. The `sample_comments` field shows how followers phrase their requests — useful for video titles/captions.
4. After generating and posting the video, call again to find the next most requested car.

## API Parameters Reference

| Parameter | Type | Description |
|-----------|------|-------------|
| `last` | int | Number of recent posts to analyze (required) |
| `handle` | string | Instagram handle to analyze |
| `brand` | string | Filter to specific brand |
| `car` | string | Filter to specific car model |
| `text` | string | Pre-filter comments containing this text |
| `min_score` | int | Minimum weighted score to include |
| `top_n` | int | Limit to top N results |
| `mode` | string | `api` (Graph API) or `scrape` (Apify) |

## Guardrails

- Never fabricate car request counts or rankings — always call the API.
- If the server is unreachable, tell the user to check if the Docker container is running.
- Do not cache results for more than a few minutes — comment data changes frequently.
- Present exact numbers from the API, do not round or estimate.
