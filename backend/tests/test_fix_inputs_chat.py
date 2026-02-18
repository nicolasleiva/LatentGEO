import json

from app.models import Audit, AuditStatus


def _seed_chat_audit(db_session) -> Audit:
    audit = Audit(
        url="https://example.com",
        domain="example.com",
        status=AuditStatus.COMPLETED,
        user_id="test-user",
        user_email="test@example.com",
        target_audit={
            "content": {
                "title": "Example Guitar Store",
                "meta_description": "Guitars, amps, and accessories",
                "text_sample": "We sell electric guitars, acoustic guitars, and amplifiers.",
            }
        },
        fix_plan=[
            {
                "page_path": "ALL_PAGES",
                "issue_code": "SCHEMA_MISSING",
                "priority": "CRITICAL",
                "description": "Missing schema",
                "suggestion": "Add schema",
            }
        ],
    )
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)
    return audit


def test_fix_inputs_chat_endpoint(client, db_session, monkeypatch):
    audit = _seed_chat_audit(db_session)

    async def fake_llm(**kwargs):
        return json.dumps(
            {
                "assistant_message": "Use the official organization name from the audit context.",
                "suggested_value": "Example Guitar Store",
                "confidence": "evidence",
            }
        )

    import app.api.routes.github as github_routes

    monkeypatch.setattr(github_routes, "get_llm_function", lambda: fake_llm)

    payload = {
        "issue_code": "SCHEMA_MISSING",
        "field_key": "org_name",
        "field_label": "Organization name",
        "placeholder": "example.com",
        "current_values": {},
        "language": "en",
    }

    response = client.post(f"/api/github/fix-inputs/chat/{audit.id}", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["suggested_value"] == "Example Guitar Store"
    assert data["confidence"] == "evidence"


def test_fix_inputs_chat_fallback_on_invalid_json(client, db_session, monkeypatch):
    audit = _seed_chat_audit(db_session)

    async def fake_llm(**kwargs):
        return "not-json"

    import app.api.routes.github as github_routes

    monkeypatch.setattr(github_routes, "get_llm_function", lambda: fake_llm)

    payload = {
        "issue_code": "SCHEMA_MISSING",
        "field_key": "org_name",
        "field_label": "Organization name",
        "placeholder": "example.com",
        "current_values": {},
        "language": "en",
    }

    response = client.post(f"/api/github/fix-inputs/chat/{audit.id}", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["suggested_value"] == ""
    assert data["confidence"] == "unknown"
