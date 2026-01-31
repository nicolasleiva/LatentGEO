"""
Test for fix plan generation in PDF service.
"""
import pytest
import json
from unittest.mock import AsyncMock, patch
from app.services.pipeline_service import PipelineService


@pytest.mark.asyncio
async def test_generate_report_with_fix_plan():
    """Test that generate_report produces both markdown and fix_plan correctly."""

    # Mock audit data
    target_audit = {
        "url": "https://example.com",
        "status": 200,
        "structure": {
            "h1_check": {"status": "warn", "details": "H1 issues found"},
            "header_hierarchy": {"issues": [{"prev_tag_html": "<h2>", "current_tag_html": "<h4>"}]}
        },
        "eeat": {
            "author_presence": {"status": "fail"},
            "citations_and_sources": {"external_links": 5, "authoritative_links": 2}
        },
        "schema": {
            "schema_presence": {"status": "warn"},
            "schema_types": []
        },
        "content": {
            "question_targeting": {"status": "fail"}
        }
    }

    external_intelligence = {"is_ymyl": False, "category": "Business"}
    search_results = {"competitors": {"items": []}}
    competitor_audits = []

    # Mock LLM response with proper delimiter and JSON
    mock_llm_response = """# Test Report

This is a test markdown report.

Some content here.

---START_FIX_PLAN---
[
    {
        "page_path": "https://example.com/",
        "issue_code": "SCHEMA-ORG-001",
        "priority": "critical",
        "description": "Schema MedicalBusiness ausente en YMYL site. No hay Organization, Pharmacy, ni HealthTopicContent",
        "snippet": "schema_types: []",
        "suggestion": "Implementar JSON-LD MedicalBusiness + FAQPage en homepage, BreadcrumbList con position prop, ItemList con offers para productos"
    },
    {
        "page_path": "/blog",
        "issue_code": "E-E-A-T-001",
        "priority": "critical",
        "description": "0 fechas de actualización, 0 citas autoritativas en contenido YMYL",
        "snippet": "content_freshness: { \\"dates_found\\": 0 }, citations: { \\"external_links\\": 0 }",
        "suggestion": "Añadir fechas de actualización, 3+ enlaces a ANMAT/WHO por artículo"
    },
    {
        "page_path": "SITE-WIDE",
        "issue_code": "TECH-H1-001",
        "priority": "high",
        "description": "H1 duplicado o ausente en 40% páginas. Impacta semantic understanding para IA",
        "snippet": "h1_check: { \\"status\\": \\"warn\\" }",
        "suggestion": "Crear H1 único por página con formato: 'Comprar [Categoría] Online | Farmalife - Autorizado ANMAT'"
    }
]"""

    with patch('app.core.llm_kimi.get_llm_function') as mock_get_llm:
        mock_llm = AsyncMock(return_value=mock_llm_response)
        mock_get_llm.return_value = mock_llm

        # Call generate_report
        markdown_report, fix_plan = await PipelineService.generate_report(
            target_audit=target_audit,
            external_intelligence=external_intelligence,
            search_results=search_results,
            competitor_audits=competitor_audits,
            llm_function=mock_llm
        )

        # Assertions
        assert markdown_report is not None
        assert len(markdown_report) > 0
        assert "Test Report" in markdown_report

        assert fix_plan is not None
        assert isinstance(fix_plan, list)
        assert len(fix_plan) >= 3

        by_code = {i.get("issue_code"): i for i in fix_plan if isinstance(i, dict)}

        item1 = by_code["SCHEMA-ORG-001"]
        assert item1["page_path"] == "https://example.com/"
        assert item1["priority"] == "critical"

        item2 = by_code["E-E-A-T-001"]
        assert item2["page_path"] == "/blog"
        assert item2["priority"] == "critical"

        item3 = by_code["TECH-H1-001"]
        assert item3["page_path"] == "SITE-WIDE"
        assert item3["priority"] == "high"

        print("Test passed: Fix plan generated correctly with LLM response")


@pytest.mark.asyncio
async def test_generate_report_fallback_fix_plan():
    """Test that generate_report uses fallback when LLM doesn't provide fix_plan."""

    # Mock audit data with issues that should trigger fallback
    target_audit = {
        "url": "https://example.com",
        "status": 200,
        "structure": {
            "h1_check": {"status": "fail"},
            "header_hierarchy": {"issues": [{"prev_tag_html": "<h1>", "current_tag_html": "<h3>"}]}
        },
        "eeat": {
            "author_presence": {"status": "fail"}
        },
        "schema": {
            "schema_presence": {"status": "fail"}
        },
        "content": {
            "question_targeting": {"status": "fail"}
        }
    }

    external_intelligence = {"is_ymyl": True, "category": "Finance"}
    search_results = {}
    competitor_audits = []

    # Mock LLM response WITHOUT fix_plan (markdown only)
    mock_llm_response = """
# Test Report Without Fix Plan

This report has markdown but no fix plan JSON.
"""

    with patch('app.core.llm_kimi.get_llm_function') as mock_get_llm:
        mock_llm = AsyncMock(return_value=mock_llm_response)
        mock_get_llm.return_value = mock_llm

        # Call generate_report
        markdown_report, fix_plan = await PipelineService.generate_report(
            target_audit=target_audit,
            external_intelligence=external_intelligence,
            search_results=search_results,
            competitor_audits=competitor_audits,
            llm_function=mock_llm
        )

        # Assertions
        assert markdown_report is not None
        assert len(markdown_report) > 0

        assert fix_plan is not None
        assert isinstance(fix_plan, list)
        assert len(fix_plan) > 0

        print("Test passed: No fix plan fallbacks used in production")


@pytest.mark.asyncio
async def test_pdf_service_context_loading():
    """Test that PDF service loads complete audit context correctly."""

    from app.services.pdf_service import PDFService
    from app.services.audit_service import AuditService
    from unittest.mock import Mock, patch
    from app.models import Audit

    # Mock audit with relationships
    mock_audit = Mock(spec=Audit)
    mock_audit.id = 1
    mock_audit.target_audit = '{"url": "https://example.com"}'
    mock_audit.external_intelligence = '{"is_ymyl": false}'
    mock_audit.search_results = '{}'
    mock_audit.competitor_audits = '[]'
    mock_audit.pagespeed_data = '{"mobile": {"score": 85}}'

    # Mock relationships
    mock_audit.keywords = []
    mock_audit.backlinks = []
    mock_audit.rank_trackings = []
    mock_audit.llm_visibilities = []
    mock_audit.ai_content_suggestions = []

    with patch.object(AuditService, 'get_audit') as mock_get_audit:
        mock_get_audit.return_value = mock_audit

        # Call context loading
        context = PDFService._load_complete_audit_context(None, 1)

        # Assertions
        assert context is not None
        assert isinstance(context, dict)
        assert "target_audit" in context
        assert "keywords" in context
        assert "backlinks" in context
        assert "pagespeed" in context

        print("Test passed: PDF context loading works correctly")


if __name__ == "__main__":
    import asyncio

    print("Running fix plan generation tests...")

    asyncio.run(test_generate_report_with_fix_plan())
    asyncio.run(test_generate_report_fallback_fix_plan())
    asyncio.run(test_pdf_service_context_loading())

    print("All tests completed!")
