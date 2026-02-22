import json
import os
import re

import pytest

from app.core.config import settings
from app.models import Audit, AuditStatus
from app.services.audit_service import AuditService


@pytest.mark.asyncio
async def test_save_audit_files_persists_sanitized_fix_plan_once(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(settings, "REPORTS_DIR", str(tmp_path), raising=False)
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
