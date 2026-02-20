"""
External smoke suite for strict release gating.

Runs against a deployed environment using SMOKE_BASE_URL.
"""

import os

import httpx
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.live]

SMOKE_BASE_URL = os.getenv("SMOKE_BASE_URL", "").strip()
SMOKE_BEARER_TOKEN = os.getenv("SMOKE_BEARER_TOKEN", "").strip()


@pytest.fixture(scope="session")
def smoke_client() -> httpx.Client:
    if not SMOKE_BASE_URL:
        pytest.skip("SMOKE_BASE_URL is required for external smoke tests.")

    base_url = SMOKE_BASE_URL.rstrip("/")
    with httpx.Client(base_url=base_url, timeout=30.0, follow_redirects=True) as client:
        yield client


def _auth_headers() -> dict:
    if not SMOKE_BEARER_TOKEN:
        return {}
    return {"Authorization": f"Bearer {SMOKE_BEARER_TOKEN}"}


def test_smoke_health(smoke_client: httpx.Client):
    response = smoke_client.get("/health")
    assert response.status_code == 200, response.text


def test_smoke_docs(smoke_client: httpx.Client):
    response = smoke_client.get("/docs")
    assert response.status_code == 200, response.text


def test_smoke_webhooks_health(smoke_client: httpx.Client):
    response = smoke_client.get("/api/webhooks/health")
    assert response.status_code == 200, response.text


def test_smoke_geo_content_templates(smoke_client: httpx.Client):
    response = smoke_client.get("/api/geo/content-templates", headers=_auth_headers())
    assert response.status_code != 404, response.text
    assert response.status_code < 500, response.text

    if SMOKE_BEARER_TOKEN:
        assert response.status_code == 200, response.text
    else:
        assert response.status_code in (401, 403), response.text
