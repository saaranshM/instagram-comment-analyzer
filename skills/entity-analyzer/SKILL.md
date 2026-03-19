---
name: entity-analyzer
description: Analyze Instagram comments to find the most requested items — cars, phones, sneakers, or any custom domain. Extracts entity mentions using hybrid NER and returns ranked results.
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

Analyze Instagram comments to find what followers are requesting most. Works with any domain — cars, phones, sneakers, or custom taxonomies.

## Prerequisites

The analyzer server must be running at `$IG_ANALYZER_URL` (e.g., `http://localhost:8000`).

## Understanding User Intent

When the user mentions a domain, map it to the right taxonomy parameter:

| User says | taxonomy= |
|-----------|-----------|
| "cars", "vehicles", "car requests" | `cars` |
| "phones", "smartphones", "mobile" | `phones` |
| "sneakers", "shoes", "kicks" | `sneakers` |
| anything else | Check available taxonomies first |

If the user doesn't specify a domain, first check what taxonomies are available:
```
curl -s "$IG_ANALYZER_URL/taxonomies" | jq '.taxonomies[].id'
```
Then ask which one they want, or default to `cars` if context suggests it.

Extract the Instagram handle from the user's message. If they say "my account" or "my page", use the handle configured in the server's INSTAGRAM_HANDLE env var (omit the `handle` param).

## Commands

### "Get me the top [item] from my last [N] posts"

Examples:
- "Get me the top car from my last 5 posts"
- "What phone are people requesting most from last 10 posts?"
- "Top sneaker from my last 20 posts"

```
curl -s "$IG_ANALYZER_URL/top?last=N&handle=HANDLE&taxonomy=TAXONOMY" | jq '.'
```

Present: the item name, request count, weighted score, and sample comments.

### "Show me rankings" / "What are people asking for?"

Examples:
- "Show me car request rankings from last 20 posts"
- "What phones are people asking for?"
- "Rank the sneaker requests"

```
curl -s "$IG_ANALYZER_URL/analyze?last=N&handle=HANDLE&taxonomy=TAXONOMY&top_n=10" | jq '.'
```

Format as a readable table: rank, name, request count, score.

### "Filter by brand"

Examples:
- "What Hyundai cars are people asking for?"
- "Show me Samsung phone requests"
- "How many Nike sneaker requests?"

```
curl -s "$IG_ANALYZER_URL/analyze?last=N&handle=HANDLE&taxonomy=TAXONOMY&brand=BRAND" | jq '.'
```

### "Filter by specific item"

Examples:
- "How many people want Creta?"
- "Is anyone asking for iPhone 16?"
- "How popular are Air Jordans?"

```
curl -s "$IG_ANALYZER_URL/analyze?last=N&handle=HANDLE&taxonomy=TAXONOMY&item=ITEM" | jq '.'
```

### "What taxonomies are available?"

```
curl -s "$IG_ANALYZER_URL/taxonomies" | jq '.'
```

### "What brands/items does [taxonomy] support?"

```
curl -s "$IG_ANALYZER_URL/brands?taxonomy=TAXONOMY" | jq '.'
```

### "Analyze a different account"

When the user specifies a different handle (strip `@` if present):

```
curl -s "$IG_ANALYZER_URL/analyze?last=N&handle=OTHER_HANDLE&taxonomy=TAXONOMY" | jq '.'
```

## Parameter Reference

| Parameter | Type | Description |
|-----------|------|-------------|
| `last` | int | Number of recent posts to analyze (required) |
| `handle` | string | Instagram handle (omit to use server default) |
| `taxonomy` | string | Domain: cars, phones, sneakers, or custom |
| `brand` | string | Filter to specific brand/group |
| `item` | string | Filter to specific item/model |
| `text` | string | Pre-filter comments containing this text |
| `min_score` | int | Minimum weighted score to include |
| `top_n` | int | Limit to top N results |

## Automation Workflow

1. Call `/top?last=20&handle=HANDLE&taxonomy=TAXONOMY` to find the most requested item.
2. Use the `result` field as input for content generation.
3. `sample_comments` shows how followers phrase requests — useful for titles/captions.
4. After posting, call again for the next most requested item.

## Server Management

Health check:
```
curl -s "$IG_ANALYZER_URL/health" | jq '.'
```

Reload taxonomies after adding/editing YAML files:
```
curl -s -X POST "$IG_ANALYZER_URL/reload" | jq '.'
```

## Guardrails

- Never fabricate request counts or rankings — always call the API.
- If the server is unreachable, tell the user to check if the Docker container is running.
- Do not cache results — comment data changes frequently.
- Present exact numbers from the API, do not round or estimate.
- If the user asks for a taxonomy that doesn't exist, list available ones and suggest creating a custom YAML.
