#!/usr/bin/env python3
"""Test Instagram Graph API integration with mocked responses matching real API format."""

import json
import os
import sys
from unittest.mock import patch, MagicMock

# Mock responses based on official Meta documentation (v24.0)
MOCK_MEDIA_RESPONSE = {
    "data": [
        {
            "id": "17918920912340654",
            "caption": "Night drive lofi vibes 🚗✨",
            "timestamp": "2026-03-15T22:36:43+0000",
            "permalink": "https://www.instagram.com/p/DABcDeFgHiJ/",
            "media_type": "VIDEO",
            "comments_count": 14,
            "like_count": 583,
        },
        {
            "id": "17899305451014820",
            "caption": "Night drive through the city 🌙",
            "timestamp": "2026-03-10T18:12:01+0000",
            "permalink": "https://www.instagram.com/p/XyZaBcDeFgH/",
            "media_type": "VIDEO",
            "comments_count": 8,
            "like_count": 291,
        },
    ],
    "paging": {
        "cursors": {
            "before": "NDMyNzQyODI3OTQw",
            "after": "MTAxNTExOTQ1MjAwNzI5NDE=",
        },
    },
}

MOCK_COMMENTS_POST1 = {
    "data": [
        {
            "id": "17870913679156914",
            "text": "please make Hyundai Creta video",
            "timestamp": "2026-03-15T23:16:02+0000",
            "username": "car_lover_42",
            "like_count": 5,
        },
        {
            "id": "17881770991003328",
            "text": "brezza ka video banao bhai",
            "timestamp": "2026-03-15T22:45:19+0000",
            "username": "ravi_kumar_99",
            "like_count": 2,
        },
        {
            "id": "17892130678234512",
            "text": "Scorpio🙌",
            "timestamp": "2026-03-15T22:40:00+0000",
            "username": "scorpio_fan",
            "like_count": 61,
        },
        {
            "id": "17903445567345623",
            "text": "nice video 🔥🔥",
            "timestamp": "2026-03-15T22:38:00+0000",
            "username": "random_user",
            "like_count": 0,
        },
        {
            "id": "17914760456456734",
            "text": "Baleno!!!!",
            "timestamp": "2026-03-15T22:37:00+0000",
            "username": "baleno_dreamer",
            "like_count": 1,
        },
    ],
    "paging": {
        "cursors": {
            "before": "QVFIUnpKR0x4RmNfRkpOc0ZANnl5",
            "after": "QVFIUmlBZA05OWEzYjBMOWVF",
        },
    },
}

MOCK_COMMENTS_POST2 = {
    "data": [
        {
            "id": "17925075345567845",
            "text": "Bhai ertiga please 🙏",
            "timestamp": "2026-03-10T19:00:00+0000",
            "username": "ertiga_wala",
            "like_count": 3,
        },
        {
            "id": "17936390234678956",
            "text": "marutisuzki swift plzz",
            "timestamp": "2026-03-10T18:30:00+0000",
            "username": "swift_boy",
            "like_count": 0,
        },
        {
            "id": "17947705123789067",
            "text": "creata ka video banao",
            "timestamp": "2026-03-10T18:20:00+0000",
            "username": "hyundai_fan",
            "like_count": 1,
        },
    ],
    "paging": {
        "cursors": {
            "before": "QVFIbXpMR0ZANRmNfRk",
            "after": "QVFIcmlBZA05OWEzY",
        },
    },
}

MOCK_ERROR_EXPIRED = {
    "error": {
        "message": "Error validating access token: Session has expired.",
        "type": "OAuthException",
        "code": 190,
        "error_subcode": 463,
        "fbtrace_id": "EJplcsCHuLu",
    }
}

MOCK_ERROR_RATE_LIMIT = {
    "error": {
        "message": "(#4) Application request limit reached",
        "type": "OAuthException",
        "code": 4,
        "fbtrace_id": "AmFGcW_3hwDB7qFbl_QdebZ",
    }
}


def mock_api_get(url, params=None, timeout=None):
    """Mock requests.get to return realistic Instagram API responses."""
    resp = MagicMock()
    resp.ok = True
    resp.status_code = 200

    if "/media" in url:
        resp.json.return_value = MOCK_MEDIA_RESPONSE
    elif "/comments" in url:
        # Return different comments for different posts
        if "17918920912340654" in url or (params and "17918920912340654" in str(params)):
            resp.json.return_value = MOCK_COMMENTS_POST1
        else:
            resp.json.return_value = MOCK_COMMENTS_POST2
    elif "/me" in url:
        resp.json.return_value = {"id": "17841405309211844", "username": "test_account"}
    else:
        resp.json.return_value = {"data": []}

    return resp


def test_api_fetch():
    """Test that our API client correctly parses Instagram Graph API responses."""
    os.environ["INSTAGRAM_ACCESS_TOKEN"] = "test_token_123"
    os.environ["INSTAGRAM_USER_ID"] = "17841405309211844"

    with patch("instagram_api.requests.get", side_effect=mock_api_get):
        from instagram_api import fetch_via_api

        comments, posts_count, rate_limited = fetch_via_api("test_account", 2)

    print(f"Posts fetched: {posts_count}")
    print(f"Comments fetched: {len(comments)}")
    print(f"Rate limited: {rate_limited}")
    print()

    assert posts_count == 2, f"Expected 2 posts, got {posts_count}"
    assert len(comments) == 8, f"Expected 8 comments, got {len(comments)}"
    assert not rate_limited, "Should not be rate limited"

    # Verify comment structure
    for c in comments:
        assert "id" in c, "Missing id"
        assert "text" in c, "Missing text"
        assert "username" in c, "Missing username"
        assert "like_count" in c, "Missing like_count"
        print(f"  {c['username']:20s} | {c['text'][:50]}")

    print("\n✓ API fetch test passed")
    return comments


def test_api_with_ner(comments):
    """Test that NER correctly extracts cars from API-formatted comments."""
    from taxonomy import Taxonomy
    from entity_extractor import EntityExtractor

    extractor = EntityExtractor(Taxonomy("taxonomies/cars.yaml"))
    results = extractor.extract(comments)

    print(f"\nExtractions: {len(results)}")
    for r in results:
        model = r["model"] or "(brand only)"
        print(f"  {r['brand']:20s} {model:20s} <- {r['source_comment'][:50]}")

    # Verify expected extractions
    brands = {r["brand"] for r in results}
    assert "Hyundai" in brands, "Should find Hyundai"
    assert "Maruti Suzuki" in brands, "Should find Maruti Suzuki"
    assert "Mahindra" in brands, "Should find Mahindra"

    models = {r["model"] for r in results if r["model"]}
    assert "Creta" in models, "Should find Creta"
    assert "Brezza" in models, "Should find Brezza"
    assert "Scorpio" in models, "Should find Scorpio"
    assert "Baleno" in models, "Should find Baleno"
    assert "Ertiga" in models, "Should find Ertiga"
    assert "Swift" in models, "Should find Swift"

    # "nice video" should NOT produce car matches
    nice_video_matches = [r for r in results if r["source_comment"] == "nice video 🔥🔥"]
    assert len(nice_video_matches) == 0, "nice video should have no car matches"

    print("\n✓ NER extraction test passed")


def test_full_pipeline(comments):
    """Test aggregation and output format."""
    from taxonomy import Taxonomy
    from entity_extractor import EntityExtractor
    from output import aggregate_results, build_output

    extractor = EntityExtractor(Taxonomy("taxonomies/cars.yaml"))
    extractions = extractor.extract(comments)
    rankings, brand_summary = aggregate_results(extractions)

    metadata = {
        "fetched_at": "2026-03-19T00:00:00+00:00",
        "account": "@test_account",
        "mode": "api",
        "posts_scanned": 2,
        "total_comments_analyzed": len(comments),
        "car_mentions_found": len(extractions),
        "filters_applied": {"brand": None, "car": None, "text": None},
    }
    data = build_output(rankings, brand_summary, metadata)

    # Verify output schema
    assert "metadata" in data
    assert "rankings" in data
    assert "brand_summary" in data
    assert data["metadata"]["mode"] == "api"
    assert data["metadata"]["posts_scanned"] == 2

    for r in data["rankings"]:
        assert "rank" in r
        assert "brand" in r
        assert "model" in r
        assert "request_count" in r
        assert "weighted_score" in r
        assert "sample_comments" in r
        assert isinstance(r["sample_comments"], list)

    print(f"\nRankings ({len(rankings)} entries):")
    for r in rankings[:10]:
        name = r["brand"] + (f" {r['model']}" if r["model"] else "")
        print(f"  #{r['rank']:<3} {name:<30} {r['request_count']} requests (score: {r['weighted_score']})")

    print(f"\nOutput JSON valid: {len(json.dumps(data))} bytes")
    print("\n✓ Full pipeline test passed")


def test_error_handling():
    """Test that error responses are handled correctly."""
    os.environ["INSTAGRAM_ACCESS_TOKEN"] = "expired_token"
    os.environ["INSTAGRAM_USER_ID"] = "17841405309211844"

    # Test expired token
    def mock_expired(url, params=None, timeout=None):
        resp = MagicMock()
        resp.ok = False
        resp.status_code = 400
        resp.json.return_value = MOCK_ERROR_EXPIRED
        return resp

    print("\nTesting expired token handling...")
    with patch("instagram_api.requests.get", side_effect=mock_expired):
        try:
            # Re-import to get fresh module
            import importlib
            import instagram_api
            importlib.reload(instagram_api)
            instagram_api.fetch_recent_posts(1)
            print("  ERROR: Should have called sys.exit(1)")
        except SystemExit as e:
            assert e.code == 1, f"Expected exit code 1, got {e.code}"
            print("  ✓ Correctly exits with code 1 on expired token")

    # Test rate limit
    call_count = 0

    def mock_rate_limit(url, params=None, timeout=None):
        nonlocal call_count
        call_count += 1
        resp = MagicMock()
        if call_count <= 1:
            # First call returns posts
            resp.ok = True
            resp.status_code = 200
            resp.json.return_value = MOCK_MEDIA_RESPONSE
        else:
            # Subsequent calls hit rate limit
            resp.ok = False
            resp.status_code = 429
            resp.json.return_value = MOCK_ERROR_RATE_LIMIT
        return resp

    print("\nTesting rate limit handling...")
    with patch("instagram_api.requests.get", side_effect=mock_rate_limit):
        import importlib
        import instagram_api
        importlib.reload(instagram_api)
        comments, posts_count, rate_limited = instagram_api.fetch_via_api("test_account", 2)
        assert rate_limited, "Should be rate limited"
        print(f"  ✓ Rate limit detected, got {len(comments)} partial comments")

    print("\n✓ Error handling test passed")


if __name__ == "__main__":
    print("=" * 60)
    print("Instagram Graph API Integration Tests (Mocked v24.0)")
    print("=" * 60)

    # Test 1: API fetch with mocked responses
    print("\n--- Test 1: API Response Parsing ---")
    comments = test_api_fetch()

    # Test 2: NER on API-formatted comments
    print("\n--- Test 2: NER Extraction ---")
    test_api_with_ner(comments)

    # Test 3: Full pipeline
    print("\n--- Test 3: Full Pipeline ---")
    test_full_pipeline(comments)

    # Test 4: Error handling
    print("\n--- Test 4: Error Handling ---")
    test_error_handling()

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED ✓")
    print("=" * 60)
