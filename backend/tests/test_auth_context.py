from app.core.auth_context import AuthContextMiddleware
from app.core.config import settings
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient


def _build_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(AuthContextMiddleware)

    @app.get("/whoami")
    async def whoami(request: Request):
        return {
            "legacy_user_id": getattr(request.state, "legacy_user_id", None),
        }

    return app


def test_auth_context_does_not_enable_legacy_header_when_environment_is_unset(
    monkeypatch,
):
    monkeypatch.setattr(settings, "DEBUG", False, raising=False)
    monkeypatch.setattr(settings, "ENVIRONMENT", "", raising=False)

    app = _build_app()
    with TestClient(app) as client:
        response = client.get("/whoami", headers={"X-User-ID": "spoofed-user"})

    assert response.status_code == 200
    assert response.json()["legacy_user_id"] is None
