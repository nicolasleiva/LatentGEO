from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.services.pdf_service import PDFService


@pytest.mark.asyncio
async def test_pdf_generation_uses_deterministic_fallback_when_llm_fails():
    mock_db = MagicMock()
    mock_audit = MagicMock()
    mock_audit.id = 1
    mock_audit.url = "https://example.com"
    mock_audit.target_audit = {"market": "argentina", "geo_score": 72}
    mock_audit.external_intelligence = {
        "category": "Education",
        "subcategory": "Bootcamp",
        "market": "argentina",
        "queries_to_run": ["coding bootcamp argentina"],
    }
    mock_audit.search_results = {}
    mock_audit.competitor_audits = []
    mock_audit.pagespeed_data = {
        "mobile": {"metadata": {"fetch_time": "2099-01-01T00:00:00Z"}}
    }
    mock_keyword = SimpleNamespace(
        term="seo test",
        volume=1200,
        difficulty=42,
        cpc=1.2,
        intent="informational",
    )
    mock_backlink = SimpleNamespace(
        source_url="https://ref.example.com/article",
        target_url="https://example.com",
        anchor_text="example",
        is_dofollow=True,
        domain_authority=55,
    )
    mock_ranking = SimpleNamespace(
        keyword="seo test",
        position=8,
        url="https://example.com",
        search_engine="google",
        device="desktop",
        previous_position=10,
        location="AR",
    )
    mock_audit.keywords = [mock_keyword]
    mock_audit.backlinks = [mock_backlink]
    mock_audit.rank_trackings = [mock_ranking]
    mock_audit.llm_visibilities = []
    mock_audit.ai_content_suggestions = []
    mock_audit.report_markdown = "Persisted report content. " * 10
    mock_audit.fix_plan = [{"issue": "existing fix"}]

    with patch(
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
        "app.services.llm_visibility_service.LLMVisibilityService.check_visibility",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "app.services.ai_content_service.AIContentService.generate_suggestions",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "app.services.product_intelligence_service.ProductIntelligenceService.analyze",
        new_callable=AsyncMock,
        side_effect=Exception("skip product intelligence during test"),
    ), patch(
        "app.services.pipeline_service.PipelineService.generate_report",
        new_callable=AsyncMock,
        side_effect=RuntimeError("LLM unavailable"),
    ), patch(
        "app.services.pdf_service.PDFService._compute_report_context_signature",
        return_value="sig-match",
    ), patch(
        "app.services.pdf_service.PDFService._load_saved_report_signature",
        return_value="sig-match",
    ), patch(
        "app.services.pdf_service.PDFService.generate_comprehensive_pdf",
        new_callable=AsyncMock,
        return_value="dummy.pdf",
    ) as mock_pdf_generator:
        result = await PDFService.generate_pdf_with_complete_context(
            mock_db, 1, force_report_refresh=True, return_details=True
        )

    assert result["pdf_path"] == "dummy.pdf"
    assert result["report_regenerated"] is False
    assert result["report_persisted"] is False
    assert result["generation_mode"] == "report_cached_llm_failure"
    assert mock_audit.report_markdown == "Persisted report content. " * 10
    assert result["generation_warnings"]
    mock_pdf_generator.assert_awaited_once()


@pytest.mark.asyncio
async def test_pdf_generation_uses_deterministic_fallback_without_cached_markdown():
    mock_db = MagicMock()
    mock_audit = MagicMock()
    mock_audit.id = 2
    mock_audit.url = "https://store.example.com"
    mock_audit.target_audit = {"market": "argentina", "geo_score": 55}
    mock_audit.external_intelligence = {
        "category": "Education",
        "subcategory": "Bootcamp",
        "market": "argentina",
        "queries_to_run": ["coding bootcamp argentina"],
    }
    mock_audit.search_results = {}
    mock_audit.competitor_audits = []
    mock_audit.pagespeed_data = {
        "mobile": {
            "performance_score": 42,
            "metadata": {"fetch_time": "2099-01-01T00:00:00Z"},
        },
        "desktop": {
            "performance_score": 61,
            "metadata": {"fetch_time": "2099-01-01T00:00:00Z"},
        },
    }
    mock_keyword = SimpleNamespace(
        term="store keyword",
        volume=900,
        difficulty=35,
        cpc=0.8,
        intent="commercial",
    )
    mock_backlink = SimpleNamespace(
        source_url="https://ref.example.com/store",
        target_url="https://store.example.com",
        anchor_text="store example",
        is_dofollow=True,
        domain_authority=47,
    )
    mock_ranking = SimpleNamespace(
        keyword="store keyword",
        position=12,
        url="https://store.example.com",
        search_engine="google",
        device="mobile",
        previous_position=15,
        location="AR",
    )
    mock_audit.keywords = [mock_keyword]
    mock_audit.backlinks = [mock_backlink]
    mock_audit.rank_trackings = [mock_ranking]
    mock_audit.llm_visibilities = []
    mock_audit.ai_content_suggestions = []
    mock_audit.report_markdown = ""
    mock_audit.fix_plan = []

    with patch(
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
        "app.services.llm_visibility_service.LLMVisibilityService.check_visibility",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "app.services.ai_content_service.AIContentService.generate_suggestions",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "app.services.product_intelligence_service.ProductIntelligenceService.analyze",
        new_callable=AsyncMock,
        side_effect=Exception("skip product intelligence during test"),
    ), patch(
        "app.services.pipeline_service.PipelineService.generate_report",
        new_callable=AsyncMock,
        side_effect=RuntimeError("LLM unavailable"),
    ), patch(
        "app.services.pdf_service.PDFService.generate_comprehensive_pdf",
        new_callable=AsyncMock,
        return_value="dummy.pdf",
    ) as mock_pdf_generator:
        result = await PDFService.generate_pdf_with_complete_context(
            mock_db, 2, return_details=True
        )

    assert result["pdf_path"] == "dummy.pdf"
    assert result["report_regenerated"] is True
    assert result["report_persisted"] is False
    assert result["generation_mode"] == "deterministic_fallback_transient"
    assert mock_audit.report_markdown == ""
    mock_pdf_generator.assert_awaited_once()


@pytest.mark.asyncio
async def test_pdf_generation_marks_incomplete_context_without_calling_llm():
    mock_db = MagicMock()
    mock_audit = MagicMock()
    mock_audit.id = 3
    mock_audit.url = "https://example.com"
    mock_audit.target_audit = {}
    mock_audit.external_intelligence = {
        "category": "Education",
        "subcategory": "Bootcamp",
        "market": "argentina",
        "queries_to_run": ["coding bootcamp argentina"],
    }
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
    mock_audit.report_markdown = "Persisted report content. " * 10
    mock_audit.fix_plan = []

    with patch(
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
        "app.services.llm_visibility_service.LLMVisibilityService.check_visibility",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "app.services.ai_content_service.AIContentService.generate_suggestions",
        new_callable=AsyncMock,
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
            mock_db, 3, return_details=True
        )

    assert result["generation_mode"] == "deterministic_missing_context"
    assert "target_audit" in result["missing_context"]
    assert result["report_persisted"] is False
    mock_generate_report.assert_not_awaited()


@pytest.mark.asyncio
async def test_pdf_generation_still_invokes_llm_when_supporting_datasets_are_missing():
    mock_db = MagicMock()
    mock_audit = MagicMock()
    mock_audit.id = 4
    mock_audit.url = "https://example.com"
    mock_audit.target_audit = {"market": "argentina", "geo_score": 65}
    mock_audit.external_intelligence = {
        "category": "Education",
        "subcategory": "Bootcamp",
        "market": "argentina",
        "queries_to_run": ["coding bootcamp argentina"],
    }
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
    mock_audit.report_markdown = ""
    mock_audit.fix_plan = []
    mock_audit.pages = []

    with patch(
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
    ) as mock_research, patch(
        "app.services.backlink_service.BacklinkService.analyze_backlinks",
        new_callable=AsyncMock,
    ) as mock_backlinks, patch(
        "app.services.rank_tracker_service.RankTrackerService.track_rankings",
        new_callable=AsyncMock,
    ) as mock_rankings, patch(
        "app.services.llm_visibility_service.LLMVisibilityService.check_visibility",
        new_callable=AsyncMock,
    ) as mock_visibility, patch(
        "app.services.ai_content_service.AIContentService.generate_suggestions",
        new_callable=AsyncMock,
    ) as mock_ai_suggestions, patch(
        "app.services.product_intelligence_service.ProductIntelligenceService.analyze",
        new_callable=AsyncMock,
        side_effect=Exception("skip product intelligence during test"),
    ), patch(
        "app.services.pipeline_service.PipelineService.generate_report",
        new_callable=AsyncMock,
        return_value=("Rich markdown report content. " * 40, []),
    ) as mock_generate_report, patch(
        "app.services.pdf_service.PDFService.generate_comprehensive_pdf",
        new_callable=AsyncMock,
        return_value="dummy.pdf",
    ):
        mock_research.return_value = []
        mock_backlinks.return_value = []
        mock_rankings.return_value = []
        mock_visibility.return_value = []
        mock_ai_suggestions.return_value = []
        result = await PDFService.generate_pdf_with_complete_context(
            mock_db, 4, return_details=True
        )

    assert result["generation_mode"] == "report_regenerated"
    assert result["missing_context"] == []
    assert any(
        "Supporting PDF datasets are unavailable" in warning
        for warning in result["generation_warnings"]
    )
    assert result["report_persisted"] is True
    assert mock_audit.report_markdown.startswith("Rich markdown report content.")
    mock_generate_report.assert_awaited_once()
    mock_research.assert_awaited_once()
    mock_backlinks.assert_awaited_once()
    mock_rankings.assert_awaited_once()
    mock_visibility.assert_awaited_once()
    mock_ai_suggestions.assert_awaited_once()


def test_normalize_markdown_for_pdf_render_strips_cover_scaffold():
    markdown = "\n".join(
        [
            "# GEO Audit Report",
            "",
            "## Cover",
            "Prepared by: Example",
            "",
            "## Table of Contents",
            "- Item",
            "",
            "# 1. Executive Summary",
            "Body",
        ]
    )

    normalized = PDFService._normalize_markdown_for_pdf_render(markdown)

    assert "# GEO Audit Report" not in normalized
    assert "## Cover" not in normalized
    assert "## Table of Contents" not in normalized
    assert normalized.startswith("# 1. Executive Summary")


def test_build_pdf_metadata_uses_human_prepared_by():
    mock_audit = MagicMock()
    mock_audit.url = "https://example.com"
    mock_audit.domain = "example.com"
    mock_audit.user_email = ""
    mock_audit.user_id = "google-oauth2|12345"

    metadata = PDFService._build_pdf_metadata(mock_audit)

    assert metadata["prepared_by"] == "Auditor GEO"
