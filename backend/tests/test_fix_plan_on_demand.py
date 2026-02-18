import asyncio
import json
import os

import pytest

from app.core.config import settings
from app.models import Audit, AuditStatus, AuditedPage
from app.services.audit_service import AuditService


def _seed_audit(db_session, *, user_id="test-user", user_email="test@example.com") -> Audit:
    audit = Audit(
        url="https://example.com",
        domain="example.com",
        status=AuditStatus.COMPLETED,
        user_id=user_id,
        user_email=user_email,
        target_audit={
            "url": "https://example.com",
            "structure": {"h1_check": {"status": "missing"}},
            "schema": {"schema_presence": {"status": "missing"}},
            "eeat": {"author_presence": {"status": "missing"}},
            "content": {"conversational_tone": {"score": 2}},
            "audited_page_paths": ["/", "/about"],
        },
    )
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)
    return audit


def test_ensure_fix_plan_generates_and_persists(db_session, monkeypatch, tmp_path):
    audit = _seed_audit(db_session)

    async def fake_llm(*, system_prompt, user_prompt):
        payload = {
            "fix_plan": [
                {
                    "page_path": "/",
                    "issue_code": "H1_MISSING",
                    "priority": "CRITICAL",
                    "description": "Missing H1",
                    "suggestion": "Add H1",
                },
                {
                    "page_path": "/",
                    "issue_code": "SCHEMA_MISSING",
                    "priority": "CRITICAL",
                    "description": "Missing schema",
                    "suggestion": "Add schema",
                },
                {
                    "page_path": "/",
                    "issue_code": "AUTHOR_MISSING",
                    "priority": "HIGH",
                    "description": "Missing author",
                    "suggestion": "Add author",
                },
                {
                    "page_path": "/",
                    "issue_code": "FAQ_MISSING",
                    "priority": "MEDIUM",
                    "description": "Missing FAQ",
                    "suggestion": "Add FAQ",
                },
                {
                    "page_path": "/",
                    "issue_code": "LONG_PARAGRAPH",
                    "priority": "MEDIUM",
                    "description": "Long paragraphs",
                    "suggestion": "Shorten paragraphs",
                },
            ],
            "prioritization_matrix": {},
            "implementation_phases": [],
            "raci_matrix": [],
            "resource_requirements": {},
            "risk_assessment": [],
            "success_metrics": {},
        }
        return json.dumps(payload)

    monkeypatch.setattr("app.core.llm_kimi.get_llm_function", lambda: fake_llm)
    monkeypatch.setattr(settings, "REPORTS_DIR", str(tmp_path), raising=False)

    fix_plan = asyncio.run(AuditService.ensure_fix_plan(db_session, audit.id))

    assert isinstance(fix_plan, list)
    assert len(fix_plan) >= 5
    audit = db_session.query(Audit).filter(Audit.id == audit.id).first()
    assert isinstance(audit.fix_plan, list)

    fix_plan_path = os.path.join(str(tmp_path), f"audit_{audit.id}", "fix_plan.json")
    assert os.path.exists(fix_plan_path)


def test_audit_to_fixes_generates_fix_plan(client, db_session, monkeypatch):
    audit = _seed_audit(db_session)

    async def fake_ensure_fix_plan(db, audit_id, min_items=5):
        audit_row = db.query(Audit).filter(Audit.id == audit_id).first()
        audit_row.fix_plan = [
            {
                "page_path": "/",
                "issue_code": "H1_MISSING",
                "priority": "HIGH",
                "description": "Missing H1",
                "suggestion": "Add H1",
                "recommended_value": "Example H1",
            }
        ]
        db.commit()
        return audit_row.fix_plan

    monkeypatch.setattr(AuditService, "ensure_fix_plan", fake_ensure_fix_plan)

    response = client.get(f"/api/github/audit-to-fixes/{audit.id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_fixes"] == 1
    assert payload["fixes"][0]["type"] == "h1"


def _seed_fix_plan_audit(db_session, tmp_path) -> Audit:
    audit = _seed_audit(db_session)
    audit.fix_plan = [
        {
            "page_path": "/privacy-policy",
            "issue_code": "H1_MISSING",
            "priority": "CRITICAL",
            "description": "Missing H1",
            "suggestion": "Add H1",
        },
        {
            "page_path": "ALL_PAGES",
            "issue_code": "SCHEMA_MISSING",
            "priority": "CRITICAL",
            "description": "Missing schema",
            "suggestion": "Add schema",
        },
        {
            "page_path": "ALL_PAGES",
            "issue_code": "AUTHOR_MISSING",
            "priority": "HIGH",
            "description": "Missing author",
            "suggestion": "Add author",
        },
        {
            "page_path": "ALL_PAGES",
            "issue_code": "FAQ_MISSING",
            "priority": "MEDIUM",
            "description": "Missing FAQ",
            "suggestion": "Add FAQ",
        },
        {
            "page_path": "/privacy-policy",
            "issue_code": "LONG_PARAGRAPH",
            "priority": "MEDIUM",
            "description": "Long paragraphs",
            "suggestion": "Shorten paragraphs",
        },
    ]
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)

    page = AuditedPage(
        audit_id=audit.id,
        url="https://example.com/privacy-policy",
        path="/privacy-policy",
        audit_data={
            "structure": {
                "h1_check": {"details": {"example": "Privacy Policy"}}
            }
        },
    )
    db_session.add(page)
    db_session.commit()
    return audit


def test_get_fix_plan_missing_inputs_and_apply(db_session, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "REPORTS_DIR", str(tmp_path), raising=False)
    audit = _seed_fix_plan_audit(db_session, tmp_path)

    missing_inputs = asyncio.run(AuditService.get_fix_plan_missing_inputs(db_session, audit.id))
    assert any(group["issue_code"] == "H1_MISSING" for group in missing_inputs)
    assert any(group["issue_code"] == "SCHEMA_MISSING" for group in missing_inputs)
    assert any(group["issue_code"] == "AUTHOR_MISSING" for group in missing_inputs)
    assert any(group["issue_code"] == "FAQ_MISSING" for group in missing_inputs)

    answers = [
        {
            "id": "h1:/privacy-policy",
            "issue_code": "H1_MISSING",
            "page_path": "/privacy-policy",
            "values": {"h1_text": "Privacy Policy"},
        },
        {
            "id": "schema:org",
            "issue_code": "SCHEMA_MISSING",
            "page_path": "ALL_PAGES",
            "values": {"org_name": "Example Inc", "org_url": "https://example.com"},
        },
        {
            "id": "author:global",
            "issue_code": "AUTHOR_MISSING",
            "page_path": "ALL_PAGES",
            "values": {"author_name": "Test Author"},
        },
    ]

    updated = asyncio.run(AuditService.apply_fix_plan_inputs(db_session, audit.id, answers))
    assert isinstance(updated, list)
    assert any(item.get("recommended_value") == "Privacy Policy" for item in updated)

    fix_plan_path = os.path.join(str(tmp_path), f"audit_{audit.id}", "fix_plan.json")
    assert os.path.exists(fix_plan_path)
