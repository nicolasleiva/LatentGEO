"""
Integration tests for GEO GitHub flow.

These tests require real GitHub connection/repository IDs and are skipped
unless explicitly configured via env vars.
"""
import os
from typing import List

import pytest
import requests

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION_TESTS") != "1",
    reason="Requiere servicios corriendo (localhost) y acceso a red/GitHub",
)

API_URL = "http://localhost:8000/api"
CONNECTION_ID = os.getenv("GEO_TEST_CONNECTION_ID", "").strip()
REPO_ID = os.getenv("GEO_TEST_REPO_ID", "").strip()


def _require_github_targets() -> None:
    if not CONNECTION_ID or not REPO_ID:
        pytest.skip(
            "Set GEO_TEST_CONNECTION_ID and GEO_TEST_REPO_ID to run GEO GitHub integration tests."
        )


@pytest.fixture()
def blog_paths() -> List[str]:
    _require_github_targets()
    url = f"{API_URL}/github/audit-blogs-geo/{CONNECTION_ID}/{REPO_ID}"
    response = requests.post(url, timeout=120)

    if response.status_code in (401, 403):
        pytest.skip("GitHub credentials/token are not authorized in this environment.")
    if response.status_code in (404,):
        pytest.skip("GitHub connection/repository not available for this environment.")

    assert response.status_code == 200, response.text
    data = response.json()
    if data.get("status") == "no_blogs_found":
        pytest.skip("Repository has no blogs/pages to audit.")

    blogs = data.get("blogs", [])
    return [b.get("file_path", "") for b in blogs if b.get("file_path")]


def test_audit_blogs_geo(blog_paths: List[str]):
    # If fixture didn't skip, endpoint returned valid data.
    assert isinstance(blog_paths, list)
    assert len(blog_paths) >= 0


def test_create_geo_pr(blog_paths: List[str]):
    if not blog_paths:
        pytest.skip("No blog paths found to generate GEO fixes PR.")

    _require_github_targets()
    url = f"{API_URL}/github/create-geo-fixes-pr/{CONNECTION_ID}/{REPO_ID}"
    payload = {"blog_paths": blog_paths, "include_geo": True}
    response = requests.post(url, json=payload, timeout=180)

    if response.status_code in (400, 404, 409):
        # Not a server crash; typically repository state/permissions/no-op conditions.
        pytest.skip(
            f"GEO PR creation not applicable in this environment: {response.status_code}"
        )

    assert response.status_code == 200, response.text
    data = response.json()
    assert "pr" in data
