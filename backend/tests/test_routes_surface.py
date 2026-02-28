from unittest.mock import patch

from fastapi.testclient import TestClient

from app import main as main_module
from app.core.config import settings


def _build_app(*, debug: bool, legacy_redirect_enabled: bool):
    with patch.object(settings, "DEBUG", debug), patch.object(
        settings, "LEGACY_API_REDIRECT_ENABLED", legacy_redirect_enabled
    ), patch.object(main_module, "RATE_LIMIT_AVAILABLE", False):
        return main_module.create_app()


def test_prod_legacy_api_path_returns_404_and_v1_is_registered():
    app = _build_app(debug=False, legacy_redirect_enabled=False)
    client = TestClient(app)

    legacy_response = client.get("/api/audits", follow_redirects=False)
    canonical_response = client.get("/api/v1/audits", follow_redirects=False)
    health_legacy_response = client.get("/api/health", follow_redirects=False)
    health_live_response = client.get("/health/live", follow_redirects=False)

    assert legacy_response.status_code == 404
    assert health_legacy_response.status_code == 404
    assert canonical_response.status_code != 404
    assert health_live_response.status_code == 200


def test_debug_legacy_redirect_is_307_before_auth_or_rate_limit():
    app = _build_app(debug=True, legacy_redirect_enabled=True)
    client = TestClient(app)

    response = client.get("/api/audits", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers.get("location") == "/api/v1/audits"


def test_no_duplicate_method_path_pairs():
    app = _build_app(debug=False, legacy_redirect_enabled=False)

    seen: dict[tuple[str, str], str] = {}
    for route in app.routes:
        methods = getattr(route, "methods", None)
        path = getattr(route, "path", None)
        if not methods or not path:
            continue

        for method in methods:
            if method in {"HEAD", "OPTIONS"}:
                continue

            key = (method, path)
            assert key not in seen, (
                f"Duplicate method+path detected: {method} {path} "
                f"(existing route: {seen[key]}, duplicate: {route.name})"
            )
            seen[key] = route.name
