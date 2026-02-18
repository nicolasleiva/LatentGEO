import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.pdf_service import PDFService


@pytest.mark.asyncio
async def test_pdf_generation_uses_cached_geo_data_when_fresh_mode_disabled():
    mock_db = MagicMock()
    mock_audit = MagicMock()
    mock_audit.id = 1
    mock_audit.url = "https://example.com"
    mock_audit.target_audit = {}
    mock_audit.external_intelligence = {}
    mock_audit.search_results = {}
    mock_audit.competitor_audits = []
    mock_audit.pagespeed_data = {
        "mobile": {"metadata": {"fetch_time": "2099-01-01T00:00:00Z"}}
    }
    mock_audit.keywords = [
        SimpleNamespace(
            term="nike running shoes", volume=1200, difficulty=40, cpc=1.2, intent="commercial"
        )
    ]
    mock_audit.backlinks = [
        SimpleNamespace(
            source_url="https://example.org/article",
            target_url="https://example.com/product",
            anchor_text="source",
            domain_authority=45,
            is_dofollow=True,
        )
    ]
    mock_audit.rank_trackings = [
        SimpleNamespace(keyword="nike running shoes", position=8, url="https://example.com/product")
    ]
    mock_audit.llm_visibilities = [
        SimpleNamespace(
            query="best nike shoes",
            llm_name="ChatGPT",
            is_visible=True,
            rank=4,
            citation_text="Example citation",
        )
    ]
    mock_audit.ai_content_suggestions = [
        SimpleNamespace(
            topic="Best Nike Shoes Guide",
            suggestion_type="article",
            content_outline={"h2": ["Intro"]},
            priority="high",
            page_url="https://example.com/blog",
        )
    ]
    mock_audit.report_markdown = "Persisted report content. " * 10
    mock_audit.fix_plan = [{"issue": "existing fix"}]

    with patch.dict(
        os.environ,
        {"PDF_FORCE_FRESH_GEO": "false", "PDF_ALWAYS_FULL_MODE": "false"},
        clear=False,
    ), patch(
        "app.services.audit_service.AuditService.get_audit",
        return_value=mock_audit,
    ), patch(
        "app.services.audit_service.AuditService.get_audited_pages",
        return_value=[],
    ), patch(
        "app.services.audit_service.CompetitorService.get_competitors",
        return_value=[],
    ), patch(
        "app.services.keyword_service.KeywordService.research_keywords",
        new_callable=AsyncMock,
    ) as mock_fresh_keywords, patch(
        "app.services.backlink_service.BacklinkService.analyze_backlinks",
        new_callable=AsyncMock,
    ) as mock_fresh_backlinks, patch(
        "app.services.rank_tracker_service.RankTrackerService.track_rankings",
        new_callable=AsyncMock,
    ) as mock_fresh_rankings, patch(
        "app.services.llm_visibility_service.LLMVisibilityService.generate_llm_visibility",
        new_callable=AsyncMock,
    ) as mock_fresh_visibility, patch(
        "app.services.pipeline_service.PipelineService.generate_report",
        new_callable=AsyncMock,
        return_value=("Regenerated report content. " * 20, []),
    ), patch(
        "app.services.product_intelligence_service.ProductIntelligenceService.analyze",
        new_callable=AsyncMock,
        side_effect=Exception("skip product intelligence in test"),
    ), patch(
        "app.services.pdf_service.PDFService.generate_comprehensive_pdf",
        new_callable=AsyncMock,
        return_value="dummy.pdf",
    ) as mock_pdf_generator:
        pdf_path = await PDFService.generate_pdf_with_complete_context(mock_db, 1)

    assert pdf_path == "dummy.pdf"
    mock_pdf_generator.assert_awaited_once()
    mock_fresh_keywords.assert_not_called()


@pytest.mark.asyncio
async def test_pdf_generation_handles_null_cached_opportunity_scores():
    mock_db = MagicMock()
    mock_audit = MagicMock()
    mock_audit.id = 99
    mock_audit.url = "https://example.com"
    mock_audit.target_audit = {}
    mock_audit.external_intelligence = {}
    mock_audit.search_results = {}
    mock_audit.competitor_audits = []
    mock_audit.pagespeed_data = {
        "mobile": {"metadata": {"fetch_time": "2099-01-01T00:00:00Z"}}
    }
    mock_audit.report_markdown = "Persisted report content. " * 10
    mock_audit.fix_plan = [{"issue": "existing fix"}]

    cached_context = {
        "keywords": [
            {
                "keyword": "nike pegasus 40",
                "search_volume": 1200,
                "difficulty": 44,
                "cpc": 1.9,
                "intent": "commercial",
                "opportunity_score": None,
            },
            {
                "keyword": "nike vomero 17",
                "search_volume": 900,
                "difficulty": 40,
                "cpc": 1.5,
                "intent": "commercial",
                "opportunity_score": None,
            },
        ],
        "backlinks": {"top_backlinks": [], "total_backlinks": 0, "referring_domains": 0},
        "rank_tracking": [],
        "llm_visibility": [],
        "ai_content_suggestions": [],
    }

    with patch.dict(
        os.environ,
        {"PDF_FORCE_FRESH_GEO": "false", "PDF_ALWAYS_FULL_MODE": "false"},
        clear=False,
    ), patch(
        "app.services.audit_service.AuditService.get_audit",
        return_value=mock_audit,
    ), patch(
        "app.services.audit_service.AuditService.get_audited_pages",
        return_value=[],
    ), patch(
        "app.services.audit_service.CompetitorService.get_competitors",
        return_value=[],
    ), patch(
        "app.services.pdf_service.PDFService._load_complete_audit_context",
        return_value=cached_context,
    ), patch(
        "app.services.keyword_service.KeywordService.research_keywords",
        new_callable=AsyncMock,
    ) as mock_fresh_keywords, patch(
        "app.services.backlink_service.BacklinkService.analyze_backlinks",
        new_callable=AsyncMock,
    ) as mock_fresh_backlinks, patch(
        "app.services.rank_tracker_service.RankTrackerService.track_rankings",
        new_callable=AsyncMock,
    ) as mock_fresh_rankings, patch(
        "app.services.llm_visibility_service.LLMVisibilityService.generate_llm_visibility",
        new_callable=AsyncMock,
    ) as mock_fresh_visibility, patch(
        "app.services.pipeline_service.PipelineService.generate_report",
        new_callable=AsyncMock,
        return_value=("Regenerated report content. " * 20, []),
    ), patch(
        "app.services.product_intelligence_service.ProductIntelligenceService.analyze",
        new_callable=AsyncMock,
        side_effect=Exception("skip product intelligence in test"),
    ), patch(
        "app.services.pdf_service.PDFService.generate_comprehensive_pdf",
        new_callable=AsyncMock,
        return_value="dummy.pdf",
    ) as mock_pdf_generator:
        pdf_path = await PDFService.generate_pdf_with_complete_context(mock_db, 99)

    assert pdf_path == "dummy.pdf"
    mock_pdf_generator.assert_awaited_once()
    mock_fresh_keywords.assert_not_called()


@pytest.mark.asyncio
async def test_pdf_generation_uses_report_cache_when_signature_matches():
    mock_db = MagicMock()
    mock_audit = MagicMock()
    mock_audit.id = 55
    mock_audit.url = "https://example.com"
    mock_audit.domain = "example.com"
    mock_audit.target_audit = {}
    mock_audit.external_intelligence = {}
    mock_audit.search_results = {}
    mock_audit.competitor_audits = []
    mock_audit.pagespeed_data = {
        "mobile": {"metadata": {"fetch_time": "2099-01-01T00:00:00Z"}}
    }
    mock_audit.keywords = []
    mock_audit.backlinks = []
    mock_audit.rank_trackings = []
    mock_audit.llm_visibilities = []
    mock_audit.ai_content_suggestions = []
    mock_audit.report_markdown = "Cached markdown content. " * 20
    mock_audit.fix_plan = [{"issue": "cached"}]

    cached_context = {
        "keywords": [{"keyword": "bootcamp", "search_volume": 1000}],
        "backlinks": {
            "top_backlinks": [],
            "total_backlinks": 0,
            "referring_domains": 0,
        },
        "rank_tracking": [],
        "llm_visibility": [],
        "ai_content_suggestions": [],
    }

    with patch.dict(
        os.environ,
        {"PDF_FORCE_FRESH_GEO": "false", "PDF_ALWAYS_FULL_MODE": "false"},
        clear=False,
    ), patch(
        "app.services.audit_service.AuditService.get_audit",
        return_value=mock_audit,
    ), patch(
        "app.services.audit_service.AuditService.get_audited_pages",
        return_value=[],
    ), patch(
        "app.services.audit_service.CompetitorService.get_competitors",
        return_value=[],
    ), patch(
        "app.services.pdf_service.PDFService._load_complete_audit_context",
        return_value=cached_context,
    ), patch(
        "app.services.pdf_service.PDFService._compute_report_context_signature",
        return_value="sig-123",
    ), patch(
        "app.services.pdf_service.PDFService._load_saved_report_signature",
        return_value="sig-123",
    ), patch(
        "app.services.keyword_service.KeywordService.research_keywords",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "app.services.backlink_service.BacklinkService.analyze_backlinks",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "app.services.rank_tracker_service.RankTrackerService.track_rankings",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "app.services.llm_visibility_service.LLMVisibilityService.generate_llm_visibility",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "app.services.ai_content_service.AIContentService.generate_content_suggestions",
        return_value=[],
    ), patch(
        "app.services.pipeline_service.PipelineService.generate_report",
        new_callable=AsyncMock,
    ) as mock_generate_report, patch(
        "app.services.pdf_service.PDFService.generate_comprehensive_pdf",
        new_callable=AsyncMock,
        return_value="dummy.pdf",
    ):
        result = await PDFService.generate_pdf_with_complete_context(
            mock_db, 55, return_details=True
        )

    assert result["pdf_path"] == "dummy.pdf"
    assert result["report_cache_hit"] is True
    assert result["report_regenerated"] is False
    assert result["generation_mode"] == "report_cache_hit"
    mock_generate_report.assert_not_called()


@pytest.mark.asyncio
async def test_pdf_generation_force_report_refresh_bypasses_cache():
    mock_db = MagicMock()
    mock_audit = MagicMock()
    mock_audit.id = 56
    mock_audit.url = "https://example.com"
    mock_audit.domain = "example.com"
    mock_audit.target_audit = {}
    mock_audit.external_intelligence = {}
    mock_audit.search_results = {}
    mock_audit.competitor_audits = []
    mock_audit.pagespeed_data = {
        "mobile": {"metadata": {"fetch_time": "2099-01-01T00:00:00Z"}}
    }
    mock_audit.keywords = []
    mock_audit.backlinks = []
    mock_audit.rank_trackings = []
    mock_audit.llm_visibilities = []
    mock_audit.ai_content_suggestions = []
    mock_audit.report_markdown = "Cached markdown content. " * 20
    mock_audit.fix_plan = [{"issue": "cached"}]

    cached_context = {
        "keywords": [{"keyword": "bootcamp", "search_volume": 1000}],
        "backlinks": {
            "top_backlinks": [],
            "total_backlinks": 0,
            "referring_domains": 0,
        },
        "rank_tracking": [],
        "llm_visibility": [],
        "ai_content_suggestions": [],
    }

    with patch.dict(
        os.environ,
        {"PDF_FORCE_FRESH_GEO": "false", "PDF_ALWAYS_FULL_MODE": "false"},
        clear=False,
    ), patch(
        "app.services.audit_service.AuditService.get_audit",
        return_value=mock_audit,
    ), patch(
        "app.services.audit_service.AuditService.get_audited_pages",
        return_value=[],
    ), patch(
        "app.services.audit_service.CompetitorService.get_competitors",
        return_value=[],
    ), patch(
        "app.services.pdf_service.PDFService._load_complete_audit_context",
        return_value=cached_context,
    ), patch(
        "app.services.pdf_service.PDFService._compute_report_context_signature",
        return_value="sig-123",
    ), patch(
        "app.services.pdf_service.PDFService._load_saved_report_signature",
        return_value="sig-123",
    ), patch(
        "app.services.keyword_service.KeywordService.research_keywords",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "app.services.backlink_service.BacklinkService.analyze_backlinks",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "app.services.rank_tracker_service.RankTrackerService.track_rankings",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "app.services.llm_visibility_service.LLMVisibilityService.generate_llm_visibility",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "app.services.ai_content_service.AIContentService.generate_content_suggestions",
        return_value=[],
    ), patch(
        "app.services.pdf_service.PDFService._save_report_signature"
    ), patch(
        "app.services.pipeline_service.PipelineService.generate_report",
        new_callable=AsyncMock,
        return_value=("Regenerated report content. " * 20, []),
    ) as mock_generate_report, patch(
        "app.services.product_intelligence_service.ProductIntelligenceService.analyze",
        new_callable=AsyncMock,
        side_effect=Exception("skip product intelligence in test"),
    ), patch(
        "app.services.pdf_service.PDFService.generate_comprehensive_pdf",
        new_callable=AsyncMock,
        return_value="dummy.pdf",
    ):
        result = await PDFService.generate_pdf_with_complete_context(
            mock_db,
            56,
            force_report_refresh=True,
            return_details=True,
        )

    assert result["pdf_path"] == "dummy.pdf"
    assert result["report_cache_hit"] is False
    assert result["report_regenerated"] is True
    assert result["generation_mode"] == "report_regenerated"
    mock_generate_report.assert_awaited_once()
