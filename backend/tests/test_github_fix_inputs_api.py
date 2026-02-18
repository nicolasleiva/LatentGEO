import os

from app.core.config import settings
from app.models import Audit, AuditedPage, AuditStatus


def _seed_fix_inputs_audit(db_session) -> Audit:
    audit = Audit(
        url="https://example.com",
        domain="example.com",
        status=AuditStatus.COMPLETED,
        user_id="test-user",
        user_email="test@example.com",
        fix_plan=[
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
        ],
    )
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)

    page = AuditedPage(
        audit_id=audit.id,
        url="https://example.com/privacy-policy",
        path="/privacy-policy",
        audit_data={
            "structure": {"h1_check": {"details": {"example": "Privacy Policy"}}}
        },
    )
    db_session.add(page)
    db_session.commit()
    return audit


def test_fix_inputs_endpoints(client, db_session, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "REPORTS_DIR", str(tmp_path), raising=False)
    audit = _seed_fix_inputs_audit(db_session)

    response = client.get(f"/api/github/fix-inputs/{audit.id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["missing_inputs"]

    # Should block PR while required inputs are missing
    pr_response = client.post(
        "/api/github/create-auto-fix-pr/connection/repo", json={"audit_id": audit.id}
    )
    assert pr_response.status_code == 422

    submit_payload = {
        "inputs": [
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
    }

    submit_response = client.post(
        f"/api/github/fix-inputs/{audit.id}", json=submit_payload
    )
    assert submit_response.status_code == 200
    submit_payload = submit_response.json()
    assert submit_payload["missing_required"] == 0

    fix_plan_path = os.path.join(str(tmp_path), f"audit_{audit.id}", "fix_plan.json")
    assert os.path.exists(fix_plan_path)
