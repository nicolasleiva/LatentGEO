from datetime import datetime, timedelta

import pytest
from app.core.access_control import ensure_connection_access
from app.core.auth import AuthUser, get_current_user
from app.core.config import _parse_string_list, settings
from app.core.database import get_db
from app.core.oauth_state import build_oauth_state, validate_oauth_state
from app.main import app
from app.models.github import GitHubConnection, GitHubRepository
from app.models.hubspot import HubSpotConnection, HubSpotPage
from app.services.cache_service import cache
from fastapi import HTTPException
from fastapi.testclient import TestClient
from main import _redact_url_credentials


@pytest.fixture
def unauthenticated_client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            db_session.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides.pop(get_current_user, None)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


def test_integration_endpoints_require_bearer_auth(unauthenticated_client):
    requests = [
        ("get", "/api/github/auth-url", None),
        ("get", "/api/github/connections", None),
        ("post", "/api/github/callback", {"code": "x", "state": "y"}),
        ("get", "/api/hubspot/auth-url", None),
        ("get", "/api/hubspot/connections", None),
        ("post", "/api/hubspot/callback", {"code": "x", "state": "y"}),
    ]
    for method, path, payload in requests:
        if method == "get":
            response = unauthenticated_client.get(path)
        else:
            response = unauthenticated_client.post(path, json=payload)
        assert response.status_code == 401, f"{method.upper()} {path} should be 401"


def test_github_cross_user_connection_is_forbidden(client, db_session):
    other_connection = GitHubConnection(
        owner_user_id="other-user",
        owner_email="other@example.com",
        github_user_id="gh-other-1",
        github_username="otherdev",
        access_token="encrypted",
        scope="repo",
        token_type="bearer",
        account_type="user",
        is_active=True,
    )
    db_session.add(other_connection)
    db_session.commit()
    db_session.refresh(other_connection)

    other_repo = GitHubRepository(
        connection_id=other_connection.id,
        github_repo_id="repo-other-1",
        full_name="other/repo",
        name="repo",
        owner="other",
        url="https://github.com/other/repo",
        default_branch="main",
        is_private=False,
        is_active=True,
    )
    db_session.add(other_repo)
    db_session.commit()
    db_session.refresh(other_repo)
    other_repo_id = other_repo.id

    repos_res = client.get(f"/api/github/repos/{other_connection.id}")
    assert repos_res.status_code == 403

    prs_res = client.get(f"/api/github/prs/{other_repo_id}")
    assert prs_res.status_code == 403


def test_hubspot_cross_user_connection_is_forbidden(client, db_session):
    other_connection = HubSpotConnection(
        owner_user_id="other-user",
        owner_email="other@example.com",
        portal_id="portal-other",
        access_token="encrypted-access",
        refresh_token="encrypted-refresh",
        scopes="content,cms.pages.read,cms.pages.write",
        expires_at=datetime.utcnow() + timedelta(days=365),
        is_active=True,
    )
    db_session.add(other_connection)
    db_session.commit()
    db_session.refresh(other_connection)

    page = HubSpotPage(
        connection_id=other_connection.id,
        hubspot_id="page-other-1",
        url="https://example.com/hubspot-page",
    )
    db_session.add(page)
    db_session.commit()

    pages_res = client.get(f"/api/hubspot/pages/{other_connection.id}")
    assert pages_res.status_code == 403

    sync_res = client.post(f"/api/hubspot/sync/{other_connection.id}")
    assert sync_res.status_code == 403


def test_legacy_connection_blocked_in_production(db_session, monkeypatch):
    legacy = GitHubConnection(
        github_user_id="legacy-gh-1",
        github_username="legacy",
        access_token="encrypted",
        scope="repo",
        token_type="bearer",
        account_type="user",
        is_active=True,
    )
    db_session.add(legacy)
    db_session.commit()
    db_session.refresh(legacy)

    monkeypatch.setattr(settings, "DEBUG", False, raising=False)
    user = AuthUser(user_id="test-user", email="test@example.com")

    with pytest.raises(HTTPException) as exc_info:
        ensure_connection_access(legacy, user, db_session, "conexión de GitHub")
    assert exc_info.value.status_code == 403


def test_legacy_connection_autoclaim_in_debug(db_session, monkeypatch):
    legacy = HubSpotConnection(
        portal_id="legacy-portal",
        access_token="encrypted-access",
        refresh_token="encrypted-refresh",
        scopes="content,cms.pages.read,cms.pages.write",
        expires_at=datetime.utcnow() + timedelta(days=365),
        is_active=True,
    )
    db_session.add(legacy)
    db_session.commit()
    db_session.refresh(legacy)

    monkeypatch.setattr(settings, "DEBUG", True, raising=False)
    user = AuthUser(user_id="test-user", email="test@example.com")
    claimed = ensure_connection_access(legacy, user, db_session, "conexión de HubSpot")

    assert claimed.owner_user_id == "test-user"
    assert claimed.owner_email == "test@example.com"


def test_oauth_state_validation_happy_path():
    user = AuthUser(user_id="test-user", email="test@example.com")
    state = build_oauth_state("github", user)
    payload = validate_oauth_state(state, "github", user)
    assert payload["sub"] == "test-user"
    assert payload["provider"] == "github"


def test_oauth_state_validation_rejects_invalid_state():
    user = AuthUser(user_id="test-user", email="test@example.com")
    with pytest.raises(HTTPException) as exc_info:
        validate_oauth_state("invalid-state-token", "github", user)
    assert exc_info.value.status_code == 400


def test_oauth_state_validation_rejects_user_mismatch():
    state = build_oauth_state(
        "hubspot", AuthUser(user_id="owner-user", email="owner@example.com")
    )
    with pytest.raises(HTTPException) as exc_info:
        validate_oauth_state(
            state, "hubspot", AuthUser(user_id="other-user", email="other@example.com")
        )
    assert exc_info.value.status_code == 401


def test_github_callback_rejects_missing_state(client):
    response = client.post("/api/github/callback", json={"code": "dummy"})
    assert response.status_code == 400
    assert "state" in response.json().get("detail", "").lower()


def test_hubspot_callback_rejects_missing_state(client):
    response = client.post("/api/hubspot/callback", json={"code": "dummy"})
    assert response.status_code == 400
    assert "state" in response.json().get("detail", "").lower()


def test_parse_string_list_accepts_json_csv_and_single_value():
    assert _parse_string_list('["http://a.com", "http://b.com"]') == [
        "http://a.com",
        "http://b.com",
    ]
    assert _parse_string_list("http://a.com, http://b.com") == [
        "http://a.com",
        "http://b.com",
    ]
    assert _parse_string_list("http://single.com") == ["http://single.com"]


def test_redact_url_credentials_masks_password():
    redacted = _redact_url_credentials("postgresql://user:secret@localhost:5432/appdb")
    assert redacted == "postgresql://user:****@localhost:5432/appdb"

    unchanged = _redact_url_credentials("sqlite:///./local.db")
    assert unchanged == "sqlite:///./local.db"


def test_health_degraded_returns_200_when_only_redis_fails(client, monkeypatch):
    class FailingRedis:
        def ping(self):
            raise RuntimeError("redis down")

    monkeypatch.setattr(cache, "enabled", True, raising=False)
    monkeypatch.setattr(cache, "redis_client", FailingRedis(), raising=False)

    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "degraded"


def test_health_unhealthy_returns_503_when_db_fails_even_if_redis_fails(
    client, monkeypatch
):
    class BrokenDb:
        def execute(self, *args, **kwargs):
            raise RuntimeError("db down")

    class FailingRedis:
        def ping(self):
            raise RuntimeError("redis down")

    def override_get_db_broken():
        yield BrokenDb()

    previous_get_db = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db_broken

    monkeypatch.setattr(cache, "enabled", True, raising=False)
    monkeypatch.setattr(cache, "redis_client", FailingRedis(), raising=False)

    try:
        response = client.get("/health")
    finally:
        if previous_get_db is not None:
            app.dependency_overrides[get_db] = previous_get_db
        else:
            app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 503
    assert response.json()["status"] == "unhealthy"
