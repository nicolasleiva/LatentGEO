from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import sse as sse_route
from app.core.auth import create_access_token


class _DummyStatus:
    value = "processing"


class _DummyAudit:
    id = 123
    status = _DummyStatus()
    progress = 10
    error_message = None
    geo_score = None
    total_pages = 1


class _DummySession:
    def close(self):
        return None


def _build_sse_test_app(monkeypatch) -> FastAPI:
    import app.core.database as database_module

    async def _fake_stream(_: int, __):
        yield 'data: {"status":"processing","progress":10}\n\n'

    monkeypatch.setattr(
        sse_route.AuditService,
        "get_audit",
        lambda _db, _audit_id: _DummyAudit(),
    )
    monkeypatch.setattr(
        sse_route, "ensure_audit_access", lambda audit, _user: audit
    )
    monkeypatch.setattr(sse_route, "audit_progress_stream", _fake_stream)
    monkeypatch.setattr(
        database_module, "SessionLocal", lambda: _DummySession(), raising=False
    )

    app = FastAPI()
    app.include_router(sse_route.router)
    return app


def test_sse_rejects_query_token_without_authorization(monkeypatch):
    monkeypatch.setenv("BACKEND_INTERNAL_JWT_SECRET", "test-sse-secret")
    app = _build_sse_test_app(monkeypatch)
    token = create_access_token({"sub": "test-user", "email": "test@example.com"})

    with TestClient(app) as client:
        response = client.get(f"/sse/audits/123/progress?token={token}")

    assert response.status_code == 401
    assert response.json()["detail"] == "Token no proporcionado"


def test_sse_accepts_authorization_header(monkeypatch):
    monkeypatch.setenv("BACKEND_INTERNAL_JWT_SECRET", "test-sse-secret")
    app = _build_sse_test_app(monkeypatch)
    token = create_access_token({"sub": "test-user", "email": "test@example.com"})

    with TestClient(app) as client:
        response = client.get(
            "/sse/audits/123/progress",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "data:" in response.text
