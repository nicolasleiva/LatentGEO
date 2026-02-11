from app.core.auth import AuthUser, get_current_user
from app.main import app
from app.models import Audit, AuditStatus


def _test_user():
    return AuthUser(user_id="test-user", email="test@example.com")


def _other_user():
    return AuthUser(user_id="other-user", email="other@example.com")


def test_audit_detail_forbidden_for_non_owner(client):
    create_res = client.post("/api/audits/", json={"url": "https://owner-example.com"})
    assert create_res.status_code == 202
    audit_id = create_res.json()["id"]

    app.dependency_overrides[get_current_user] = _other_user
    try:
        forbidden_res = client.get(f"/api/audits/{audit_id}")
        assert forbidden_res.status_code == 403
    finally:
        app.dependency_overrides[get_current_user] = _test_user


def test_list_audits_returns_only_current_user_data(client, db_session):
    own_audit = Audit(
        url="https://owned-site.com/",
        domain="owned-site.com",
        status=AuditStatus.PENDING,
        language="en",
        user_id="test-user",
        user_email="test@example.com",
    )
    other_audit = Audit(
        url="https://other-site.com/",
        domain="other-site.com",
        status=AuditStatus.PENDING,
        language="en",
        user_id="other-user",
        user_email="other@example.com",
    )
    db_session.add(own_audit)
    db_session.add(other_audit)
    db_session.commit()

    list_res = client.get("/api/audits/")
    assert list_res.status_code == 200
    audits = list_res.json()
    returned_urls = {item["url"] for item in audits}

    assert "https://owned-site.com/" in returned_urls
    assert "https://other-site.com/" not in returned_urls
