from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.services.pdf_service import PDFService


@pytest.mark.asyncio
async def test_pdf_generation_fails_when_llm_fails_and_fallbacks_disabled():
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
    mock_audit.keywords = []
    mock_audit.backlinks = []
    mock_audit.rank_trackings = []
    mock_audit.llm_visibilities = []
    mock_audit.ai_content_suggestions = []
    mock_audit.report_markdown = "Persisted report content. " * 10
    mock_audit.fix_plan = [{"issue": "existing fix"}]

    with pytest.raises(RuntimeError, match="fallbacks are disabled"), patch(
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
        "app.services.llm_visibility_service.LLMVisibilityService.generate_llm_visibility",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "app.services.ai_content_service.AIContentService.generate_content_suggestions",
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
        await PDFService.generate_pdf_with_complete_context(mock_db, 1)

    mock_pdf_generator.assert_not_awaited()


@pytest.mark.asyncio
async def test_pdf_generation_fails_when_no_persisted_markdown_and_llm_fails():
    mock_db = MagicMock()
    mock_audit = MagicMock()
    mock_audit.id = 2
    mock_audit.url = "https://store.example.com"
    mock_audit.target_audit = {}
    mock_audit.external_intelligence = {}
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
    mock_audit.keywords = []
    mock_audit.backlinks = []
    mock_audit.rank_trackings = []
    mock_audit.llm_visibilities = []
    mock_audit.ai_content_suggestions = []
    mock_audit.report_markdown = ""
    mock_audit.fix_plan = []

    with pytest.raises(RuntimeError, match="fallbacks are disabled"), patch(
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
        "app.services.llm_visibility_service.LLMVisibilityService.generate_llm_visibility",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "app.services.ai_content_service.AIContentService.generate_content_suggestions",
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
        await PDFService.generate_pdf_with_complete_context(mock_db, 2)

    mock_pdf_generator.assert_not_awaited()
