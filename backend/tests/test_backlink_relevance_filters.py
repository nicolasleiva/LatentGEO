import pytest

from app.services.backlink_service import BacklinkService
from app.services.pipeline_service import PipelineService


def test_build_brand_mentions_query_uses_context_terms():
    query = BacklinkService._build_brand_mentions_query(
        brand_name="plataforma5",
        domain="plataforma5.la",
        context_terms=["bootcamp", "coding", "developer"],
    )
    assert '"plataforma5"' in query
    assert '"bootcamp"' in query
    assert "-site:plataforma5.la" in query


def test_brand_result_filters_industrial_noise():
    item = {
        "title": "Plataforma 5 wheel flatbed trailer",
        "snippet": "Industrial platform trailer with 5 wheels for cargo",
        "link": "https://example-hardware.com/product/plataforma-5",
    }

    is_relevant = BacklinkService._is_relevant_brand_result(
        item=item,
        brand_name="plataforma5",
        clean_domain="plataforma5.la",
        context_terms=["bootcamp", "coding", "developer"],
        excluded_domains=[],
    )
    assert is_relevant is False


def test_analysis_is_irrelevant_when_model_marks_unrelated():
    analysis = {
        "summary": "This refers to an industrial platform, unrelated to the bootcamp brand.",
        "recommendation": "Exclude from brand monitoring.",
        "relevance_score": 72,
    }
    assert BacklinkService._analysis_is_irrelevant(analysis) is True


def test_pipeline_sanitizes_legacy_json_anchor_text():
    items = [
        {
            "source_url": "BRAND_MENTION",
            "target_url": "https://example.com/1",
            "anchor_text": '{"topic":"Review","summary":"Good educational mention","recommendation":"Track it","relevance_score":80}',
        },
        {
            "source_url": "BRAND_MENTION",
            "target_url": "https://example.com/2",
            "anchor_text": '{"topic":"Noise","summary":"Completely unrelated trailer model","recommendation":"Exclude from brand monitoring","relevance_score":90}',
        },
    ]

    sanitized = PipelineService._sanitize_backlink_items(items)
    assert len(sanitized) == 1
    assert "Good educational mention" in sanitized[0]["anchor_text"]
    assert "relevance_score" not in sanitized[0]["anchor_text"]
