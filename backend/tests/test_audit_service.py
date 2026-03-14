import json
import os
import re

import pytest
from app.core.config import settings
from app.models import Audit, AuditStatus, Competitor
from app.services.audit_service import AuditService


@pytest.mark.asyncio
async def test_save_audit_files_persists_sanitized_fix_plan_once(
    tmp_path, monkeypatch, caplog
):
    monkeypatch.setattr(settings, "REPORTS_DIR", str(tmp_path), raising=False)
    monkeypatch.setattr(settings, "AUDIT_LOCAL_ARTIFACTS_ENABLED", True, raising=False)
    caplog.set_level("ERROR")

    class NonSerializable:
        pass

    await AuditService._save_audit_files(
        audit_id=77,
        target_audit={"url": "https://example.com"},
        external_intelligence={},
        search_results={},
        competitor_audits=[],
        fix_plan=[{"priority": "HIGH", "payload": NonSerializable()}],
        pagespeed_data={},
        keywords=[],
        backlinks=[],
        rankings=[],
        llm_visibility=[],
    )

    fix_plan_path = tmp_path / "audit_77" / "fix_plan.json"
    assert fix_plan_path.exists()
    data = json.loads(fix_plan_path.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    assert isinstance(data[0]["payload"], str)
    assert not any("Error guardando archivos JSON" in r.message for r in caplog.records)


def test_safe_fs_name_removes_windows_invalid_chars():
    raw = 'https://a.com/p?x=1&y=2<>:"/\\|?*'
    safe = AuditService._safe_fs_name(raw)
    assert safe
    assert not re.search(r'[<>:"/\\|?*]', safe)


def test_save_page_audit_creates_windows_safe_file(db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "REPORTS_DIR", str(tmp_path), raising=False)
    monkeypatch.setattr(settings, "AUDIT_LOCAL_ARTIFACTS_ENABLED", True, raising=False)

    audit = Audit(
        url="https://example.com",
        domain="example.com",
        status=AuditStatus.PENDING,
        user_id="test-user",
        user_email="test@example.com",
    )
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)

    page_url = 'https://example.com/page?x=1&y=2<>:"/\\|?*'
    AuditService.save_page_audit(
        db=db_session,
        audit_id=audit.id,
        page_url=page_url,
        audit_data={"structure": {"h1_check": {"status": "pass"}}},
        page_index=3,
    )

    pages_dir = tmp_path / f"audit_{audit.id}" / "pages"
    files = list(pages_dir.glob("report_3_*.json"))
    assert files
    for file_path in files:
        assert not re.search(r'[<>:"/\\|?*]', file_path.name)
        assert os.path.exists(file_path)


@pytest.mark.asyncio
async def test_save_audit_files_skips_disk_when_local_artifacts_disabled(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(settings, "REPORTS_DIR", str(tmp_path), raising=False)
    monkeypatch.setattr(settings, "AUDIT_LOCAL_ARTIFACTS_ENABLED", False, raising=False)

    await AuditService._save_audit_files(
        audit_id=88,
        target_audit={"url": "https://example.com"},
        external_intelligence={},
        search_results={},
        competitor_audits=[],
        fix_plan=[{"priority": "HIGH"}],
        pagespeed_data={},
        keywords=[],
        backlinks=[],
        rankings=[],
        llm_visibility=[],
    )

    assert not (tmp_path / "audit_88").exists()


@pytest.mark.asyncio
async def test_set_audit_results_skips_failed_competitors_from_benchmark_and_persists_warning(
    db_session, monkeypatch, tmp_path
):
    monkeypatch.setattr(settings, "REPORTS_DIR", str(tmp_path), raising=False)
    monkeypatch.setattr(settings, "AUDIT_LOCAL_ARTIFACTS_ENABLED", True, raising=False)

    audit = Audit(
        url="https://example.com",
        domain="example.com",
        status=AuditStatus.PENDING,
        user_id="test-user",
        user_email="test@example.com",
    )
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)

    await AuditService.set_audit_results(
        db=db_session,
        audit_id=audit.id,
        target_audit={
            "url": "https://example.com",
            "site_metrics": {"structure_score_percent": 40},
        },
        external_intelligence={},
        search_results={},
        competitor_audits=[
            {
                "url": "https://good.example.com",
                "domain": "good.example.com",
                "status": 200,
                "structure": {"semantic_html": {"score_percent": 60}},
            },
            {
                "url": "https://blocked.example.com",
                "domain": "blocked.example.com",
                "status": 403,
                "error": "No se pudo acceder al sitio (HTTP 403)",
                "benchmark_available": False,
            },
        ],
        report_markdown="# Report",
        fix_plan=[],
        pagespeed_data={},
    )

    db_session.refresh(audit)

    persisted_competitors = (
        db_session.query(Competitor).filter(Competitor.audit_id == audit.id).all()
    )
    assert len(persisted_competitors) == 1
    assert persisted_competitors[0].domain == "good.example.com"

    assert len(audit.competitor_audits) == 2
    failed_competitors = [
        comp for comp in audit.competitor_audits if comp.get("status") == 403
    ]
    assert len(failed_competitors) == 1
    failed_competitor = failed_competitors[0]
    assert failed_competitor["error"] == "No se pudo acceder al sitio (HTTP 403)"
    assert failed_competitor["benchmark_available"] is False
    assert "benchmark" not in failed_competitor

    diagnostics = audit.runtime_diagnostics
    assert diagnostics
    assert diagnostics[-1]["source"] == "competitor"
    assert "HTTP 403" in diagnostics[-1]["message"]

    competitor_files = list(
        (tmp_path / f"audit_{audit.id}" / "competitors").glob("*.json")
    )
    assert len(competitor_files) == 1
    expected_filename = (
        f"competitor_{AuditService._safe_fs_name('good.example.com')}.json"
    )
    assert competitor_files[0].name == expected_filename


def test_sanitize_json_value_strips_null_bytes():
    """_sanitize_json_value must remove \\x00 from strings at every nesting level."""
    payload = {
        "title": "Hello\x00World",
        "nested": {"desc": "A\x00B", "ok": 42},
        "items": ["foo\x00bar", {"inner": "x\x00y"}],
        "clean": "no nulls here",
    }
    result = AuditService._sanitize_json_value(payload)

    assert result["title"] == "HelloWorld"
    assert result["nested"]["desc"] == "AB"
    assert result["nested"]["ok"] == 42
    assert result["items"][0] == "foobar"
    assert result["items"][1]["inner"] == "xy"
    assert result["clean"] == "no nulls here"
    # Ensure the result is JSON-serializable without \x00
    serialized = json.dumps(result)
    assert "\x00" not in serialized
    assert "\\u0000" not in serialized


@pytest.mark.asyncio
async def test_set_audit_results_with_null_bytes_succeeds(
    db_session, monkeypatch, tmp_path
):
    """set_audit_results must not crash when scraped data contains \\x00."""
    monkeypatch.setattr(settings, "REPORTS_DIR", str(tmp_path), raising=False)
    monkeypatch.setattr(settings, "AUDIT_LOCAL_ARTIFACTS_ENABLED", True, raising=False)

    audit = Audit(
        url="https://example.com",
        domain="example.com",
        status=AuditStatus.PENDING,
        user_id="test-user",
        user_email="test@example.com",
    )
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)

    # Data that mimics the real error: \x00 embedded in strings
    contaminated_target = {
        "url": "https://example.com",
        "content": {"title": "Réseau en tant que service / SD-WAN", "desc": "S\x00ome text"},
        "site_metrics": {"structure_score_percent": 40},
    }
    contaminated_external = {"category": "Cloud\x00Infra"}
    contaminated_search = {"query\x00key": {"items": [{"title": "R\x00esult"}]}}
    contaminated_competitors = [
        {"url": "https://comp.example.com", "domain": "comp.example.com", "status": 200, "note": "N\x00ote"}
    ]

    await AuditService.set_audit_results(
        db=db_session,
        audit_id=audit.id,
        target_audit=contaminated_target,
        external_intelligence=contaminated_external,
        search_results=contaminated_search,
        competitor_audits=contaminated_competitors,
        report_markdown="# Report with \x00 null byte",
        fix_plan=[],
        pagespeed_data={},
    )

    db_session.refresh(audit)
    # Verify no \x00 survives in any persisted field
    assert "\x00" not in json.dumps(audit.target_audit)
    assert "\x00" not in json.dumps(audit.external_intelligence)
    assert "\x00" not in json.dumps(audit.search_results)
    assert "\x00" not in json.dumps(audit.competitor_audits)
    assert "\x00" not in (audit.report_markdown or "")

