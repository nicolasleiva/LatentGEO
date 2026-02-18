import inspect
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.routes.audits import generate_audit_pdf
from app.services.pdf_service import PDFService


def _build_audit(external_intelligence):
    return SimpleNamespace(
        id=77,
        url="https://example.com",
        domain="example.com",
        market="argentina",
        category="Education",
        target_audit={"market": "argentina"},
        external_intelligence=external_intelligence,
        search_results={},
        competitor_audits=[],
        pagespeed_data={"mobile": {"metadata": {"fetch_time": "2099-01-01T00:00:00Z"}}},
        keywords=[],
        backlinks=[],
        rank_trackings=[],
        llm_visibilities=[],
        ai_content_suggestions=[],
        report_markdown="Persisted report content. " * 15,
        fix_plan=[{"issue": "existing"}],
    )


def test_generate_audit_pdf_defaults_force_report_refresh_false():
    signature = inspect.signature(generate_audit_pdf)
    assert signature.parameters["force_report_refresh"].default is False


@pytest.mark.asyncio
async def test_external_intel_not_refreshed_when_complete_even_if_report_refresh_forced():
    mock_db = MagicMock()
    mock_audit = _build_audit(
        {
            "category": "Education",
            "subcategory": "Coding Bootcamp",
            "market": "argentina",
            "queries_to_run": ["coding bootcamp argentina"],
        }
    )
    pipeline_service_mock = MagicMock()
    pipeline_service_mock.analyze_external_intelligence = AsyncMock()

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
        return_value={
            "keywords": [],
            "backlinks": {"top_backlinks": [], "total_backlinks": 0},
            "rank_tracking": [],
            "llm_visibility": [],
            "ai_content_suggestions": [],
        },
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
        side_effect=Exception("skip product intelligence in test"),
    ), patch(
        "app.services.pipeline_service.get_pipeline_service",
        return_value=pipeline_service_mock,
    ), patch(
        "app.services.pipeline_service.PipelineService.generate_report",
        new_callable=AsyncMock,
        return_value=("Regenerated report content. " * 20, []),
    ), patch(
        "app.services.pdf_service.PDFService.generate_comprehensive_pdf",
        new_callable=AsyncMock,
        return_value="dummy.pdf",
    ):
        result = await PDFService.generate_pdf_with_complete_context(
            mock_db,
            77,
            force_report_refresh=True,
            return_details=True,
        )

    assert result["external_intel_refreshed"] is False
    assert result["external_intel_refresh_reason"] == "not_needed"
    pipeline_service_mock.analyze_external_intelligence.assert_not_called()


@pytest.mark.asyncio
async def test_external_intel_with_dict_queries_is_treated_as_complete():
    mock_db = MagicMock()
    mock_audit = _build_audit(
        {
            "category": "Education",
            "subcategory": "Coding Bootcamp",
            "market": "argentina",
            "queries_to_run": [
                {"query": "coding bootcamp argentina", "purpose": "competitors"}
            ],
        }
    )
    pipeline_service_mock = MagicMock()
    pipeline_service_mock.analyze_external_intelligence = AsyncMock()

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
        return_value={
            "keywords": [],
            "backlinks": {"top_backlinks": [], "total_backlinks": 0},
            "rank_tracking": [],
            "llm_visibility": [],
            "ai_content_suggestions": [],
        },
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
        side_effect=Exception("skip product intelligence in test"),
    ), patch(
        "app.services.pipeline_service.get_pipeline_service",
        return_value=pipeline_service_mock,
    ), patch(
        "app.services.pipeline_service.PipelineService.generate_report",
        new_callable=AsyncMock,
        return_value=("Regenerated report content. " * 20, []),
    ), patch(
        "app.services.pdf_service.PDFService.generate_comprehensive_pdf",
        new_callable=AsyncMock,
        return_value="dummy.pdf",
    ):
        result = await PDFService.generate_pdf_with_complete_context(
            mock_db,
            77,
            force_report_refresh=True,
            return_details=True,
        )

    assert result["external_intel_refreshed"] is False
    assert result["external_intel_refresh_reason"] == "not_needed"
    pipeline_service_mock.analyze_external_intelligence.assert_not_called()


@pytest.mark.asyncio
async def test_external_intel_refreshed_when_missing():
    mock_db = MagicMock()
    mock_audit = _build_audit({})
    pipeline_service_mock = MagicMock()
    pipeline_service_mock.analyze_external_intelligence = AsyncMock(
        return_value=(
            {
                "category": "Education",
                "subcategory": "Coding Bootcamp",
                "market": "argentina",
                "queries_to_run": ["coding bootcamp argentina"],
            },
            ["coding bootcamp argentina"],
        )
    )

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
        return_value={
            "keywords": [],
            "backlinks": {"top_backlinks": [], "total_backlinks": 0},
            "rank_tracking": [],
            "llm_visibility": [],
            "ai_content_suggestions": [],
        },
    ), patch(
        "app.services.pdf_service.PDFService._compute_report_context_signature",
        return_value="sig-abc",
    ), patch(
        "app.services.pdf_service.PDFService._load_saved_report_signature",
        return_value="sig-abc",
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
        "app.services.pipeline_service.get_pipeline_service",
        return_value=pipeline_service_mock,
    ), patch(
        "app.services.pipeline_service.PipelineService.generate_report",
        new_callable=AsyncMock,
    ) as mock_generate_report, patch(
        "app.services.pdf_service.PDFService.generate_comprehensive_pdf",
        new_callable=AsyncMock,
        return_value="dummy.pdf",
    ):
        result = await PDFService.generate_pdf_with_complete_context(
            mock_db,
            77,
            return_details=True,
        )

    assert result["report_cache_hit"] is True
    assert result["external_intel_refreshed"] is True
    assert result["external_intel_refresh_reason"] == "missing"
    pipeline_service_mock.analyze_external_intelligence.assert_awaited_once()
    mock_generate_report.assert_not_called()
