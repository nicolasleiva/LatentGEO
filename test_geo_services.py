#!/usr/bin/env python3
"""
Unit tests for GEO services (Keywords, Backlinks, Rankings) adapted to pytest.
"""
import json
import sys
from pathlib import Path
import pytest

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from app.services.keywords_service import KeywordsService
from app.services.backlinks_service import BacklinksService
from app.services.rank_tracking_service import RankTrackingService


@pytest.fixture
def sample_audit():
    return {
        "url": "https://example.com",
        "structure": {
            "h1_check": {
                "details": {
                    "example": "Best AI Coding Assistant",
                    "count": 1
                }
            }
        }
    }


def test_keywords_service_returns_list(sample_audit):
    keywords = KeywordsService.generate_keywords_from_audit(sample_audit, sample_audit["url"])
    assert isinstance(keywords, list)
    # If there are results, ensure expected keys exist on the first item
    if keywords:
        for key in ("keyword", "search_volume", "difficulty", "current_rank", "opportunity_score"):
            assert key in keywords[0]


def test_backlinks_service_structure(sample_audit):
    backlinks = BacklinksService.generate_backlinks_from_audit({"url": sample_audit["url"]}, sample_audit["url"])
    assert isinstance(backlinks, dict)
    assert "total_backlinks" in backlinks
    assert "referring_domains" in backlinks
    assert "summary" in backlinks
    assert "top_backlinks" in backlinks


def test_rank_tracking_service_distribution(sample_audit):
    keywords = KeywordsService.generate_keywords_from_audit(sample_audit, sample_audit["url"])
    rankings = RankTrackingService.generate_rankings_from_keywords(keywords, sample_audit["url"])

    assert isinstance(rankings, list)

    if rankings:
        # Ensure position and keyword exist
        for r in rankings[:5]:
            assert "position" in r
            assert "keyword" in r


def test_full_pipeline_integration(sample_audit, tmp_path):
    keywords = KeywordsService.generate_keywords_from_audit(sample_audit, sample_audit["url"])
    backlinks = BacklinksService.generate_backlinks_from_audit({"url": sample_audit["url"]}, sample_audit["url"])
    rankings = RankTrackingService.generate_rankings_from_keywords(keywords, sample_audit["url"])

    result = {
        "keywords": {"keywords": keywords, "total_keywords": len(keywords)},
        "backlinks": backlinks,
        "rank_tracking": {"rankings": rankings, "total_keywords": len(rankings)}
    }

    # Save to tmp file for manual inspection in CI artifacts
    output_file = tmp_path / "test_geo_output.json"
    output_file.write_text(json.dumps(result, indent=2))

    assert "keywords" in result and "backlinks" in result and "rank_tracking" in result
    assert isinstance(result["keywords"]["keywords"], list)

