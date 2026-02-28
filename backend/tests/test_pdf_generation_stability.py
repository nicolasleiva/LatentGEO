import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.services import create_pdf as create_pdf_module
from app.services.pdf_service import PDFService


def _build_page(page_id: int = 1):
    return SimpleNamespace(
        id=page_id,
        url="https://example.com/",
        path="/",
        overall_score=75,
        h1_score=80,
        structure_score=70,
        content_score=72,
        eeat_score=65,
        schema_score=60,
        critical_issues=0,
        high_issues=1,
        medium_issues=2,
        low_issues=3,
        audit_data={"summary": "ok"},
    )


def test_write_json_summary_box_sanitizes_unicode_when_core_font(monkeypatch):
    # Force core font mode (helvetica) by pointing all font files to missing paths.
    missing_root = Path("Z:/definitely-missing-fonts")
    monkeypatch.setattr(
        create_pdf_module, "FONT_REGULAR_PATH", str(missing_root / "Roboto.ttf")
    )
    monkeypatch.setattr(
        create_pdf_module, "FONT_BOLD_PATH", str(missing_root / "Roboto-Bold.ttf")
    )
    monkeypatch.setattr(
        create_pdf_module, "FONT_ITALIC_PATH", str(missing_root / "Roboto-Italic.ttf")
    )
    monkeypatch.setattr(
        create_pdf_module, "FONT_MONO_PATH", str(missing_root / "RobotoMono.ttf")
    )

    pdf = create_pdf_module.PDFReport()
    pdf.add_page()

    # Must not raise FPDFUnicodeEncodingException when helvetica is active.
    pdf.write_json_summary_box(
        {
            "title": "Comparativa – mercado",
            "notes": "Comillas “curvas” y emoji 🚀 deben sanearse",
        },
        top_n=3,
        filename_hint="pages/report_unicode.json",
    )


def test_create_comprehensive_pdf_prefers_page_files_and_ignores_noise(
    tmp_path, monkeypatch
):
    report_dir = tmp_path / "audit_99"
    pages_dir = report_dir / "pages"
    pages_dir.mkdir(parents=True)

    (report_dir / "ag2_report.md").write_text("# Report\n\nContenido", encoding="utf-8")
    (report_dir / "fix_plan.json").write_text("[]", encoding="utf-8")
    (report_dir / "aggregated_summary.json").write_text(
        json.dumps({"url": "https://example.com", "audited_pages_count": 1}),
        encoding="utf-8",
    )

    (pages_dir / "page_1.json").write_text(
        json.dumps({"url": "https://example.com", "ok": True}),
        encoding="utf-8",
    )
    (pages_dir / "report_legacy.json").write_text(
        json.dumps({"url": "https://legacy.example.com", "legacy": True}),
        encoding="utf-8",
    )
    (pages_dir / "noise.json").write_text(
        json.dumps({"ignored": True}), encoding="utf-8"
    )

    page_hints = []
    original = create_pdf_module.PDFReport.write_json_summary_box

    def _spy(self, data, top_n=3, filename_hint=None):
        if filename_hint and str(filename_hint).startswith("pages"):
            page_hints.append(os.path.basename(str(filename_hint)))
        return original(self, data, top_n=top_n, filename_hint=filename_hint)

    monkeypatch.setattr(create_pdf_module.PDFReport, "write_json_summary_box", _spy)

    create_pdf_module.create_comprehensive_pdf(str(report_dir))

    assert "page_1.json" in page_hints
    assert "report_legacy.json" not in page_hints
    assert "noise.json" not in page_hints


@pytest.mark.asyncio
async def test_generate_comprehensive_pdf_uploads_to_supabase(monkeypatch):
    audit_id = 42

    def _fake_create_pdf(folder_path: str, metadata=None):
        output = Path(folder_path) / "Reporte_Consolidado_audit_42.pdf"
        output.write_bytes(b"%PDF-1.4 new")

    monkeypatch.setattr(
        "app.services.pdf_service.create_comprehensive_pdf", _fake_create_pdf
    )
    monkeypatch.setattr(
        "app.services.pdf_service.PDFService._upload_pdf_to_supabase",
        lambda audit_id, pdf_file_path: (
            f"supabase://audits/{audit_id}/report.pdf",
            17,
        ),
    )

    audit = SimpleNamespace(
        id=audit_id,
        report_markdown="# Report",
        fix_plan=[],
        target_audit={"url": "https://example.com"},
    )
    pages = [_build_page(1)]
    competitors = [{"url": "https://competitor.example.com"}]

    pdf_path = await PDFService.generate_comprehensive_pdf(
        audit=audit,
        pages=pages,
        competitors=competitors,
    )

    assert pdf_path == "supabase://audits/42/report.pdf"
    assert getattr(audit, "_generated_pdf_size_bytes", None) == 17


@pytest.mark.asyncio
async def test_pdf_generation_with_kimi_failure_errors_when_fallbacks_disabled(
    tmp_path,
):
    mock_db = MagicMock()
    mock_audit = MagicMock()
    mock_audit.id = 7
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
    mock_audit.report_markdown = "Persisted fallback report. " * 10
    mock_audit.fix_plan = [{"issue": "existing fix"}]

    expected_pdf = tmp_path / "generated_deterministic.pdf"

    async def _fake_generate_pdf(**kwargs):
        expected_pdf.write_bytes(b"%PDF-1.4 deterministic")
        return str(expected_pdf)

    with pytest.raises(RuntimeError, match="fallbacks are disabled"), patch.dict(
        os.environ,
        {"PDF_ALWAYS_FULL_MODE": "true"},
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
        side_effect=RuntimeError("Kimi connection error"),
    ), patch(
        "app.services.pdf_service.PDFService.generate_comprehensive_pdf",
        new_callable=AsyncMock,
        side_effect=_fake_generate_pdf,
    ):
        await PDFService.generate_pdf_with_complete_context(
            mock_db, 7, return_details=True
        )
