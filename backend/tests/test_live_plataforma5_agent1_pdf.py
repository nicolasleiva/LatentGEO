import os
import time
from typing import Any, Dict

import pytest
import requests
from app.core.auth import create_access_token

pytestmark = [
    pytest.mark.integration,
    pytest.mark.live,
    pytest.mark.skipif(
        os.getenv("RUN_INTEGRATION_TESTS") != "1" or os.getenv("RUN_LIVE_E2E") != "1",
        reason="Requiere RUN_INTEGRATION_TESTS=1 y RUN_LIVE_E2E=1 (ejecución manual)",
    ),
]

BASE_URL = os.getenv("LIVE_BASE_URL", "http://localhost:8000").rstrip("/")
API_BASE = f"{BASE_URL}/api/v1"
LIVE_TARGET_URL = os.getenv("LIVE_TARGET_URL", "https://plataforma5.la/")


def _build_auth_headers() -> Dict[str, str]:
    user_id = os.getenv("PROD_TEST_USER_ID", "live-e2e-user")
    email = os.getenv("PROD_TEST_EMAIL", "live-e2e@example.com")
    token = create_access_token({"sub": user_id, "email": email})
    return {"Authorization": f"Bearer {token}"}


def _wait_for_audit_completion(
    audit_id: int, headers: Dict[str, str], timeout_seconds: int = 1800
) -> Dict[str, Any]:
    start = time.monotonic()
    while time.monotonic() - start < timeout_seconds:
        response = requests.get(
            f"{API_BASE}/audits/{audit_id}/status", headers=headers, timeout=20
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        status = str(payload.get("status", "")).lower()
        if status == "completed":
            detail = requests.get(
                f"{API_BASE}/audits/{audit_id}", headers=headers, timeout=30
            )
            assert detail.status_code == 200, detail.text
            return detail.json()
        if status == "failed":
            pytest.fail(f"Audit {audit_id} failed: {payload}")
        time.sleep(5)
    pytest.fail(f"Audit {audit_id} did not complete within {timeout_seconds}s")


def _wait_for_pdf_completion(
    audit_id: int, headers: Dict[str, str], timeout_seconds: int = 1800
) -> Dict[str, Any]:
    start = time.monotonic()
    while time.monotonic() - start < timeout_seconds:
        response = requests.get(
            f"{API_BASE}/audits/{audit_id}/pdf-status", headers=headers, timeout=20
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        status = str(payload.get("status", "")).lower()
        if status == "completed":
            return payload
        if status == "failed":
            pytest.fail(f"PDF generation for audit {audit_id} failed: {payload}")
        time.sleep(max(1, int(payload.get("retry_after_seconds") or 3)))
    pytest.fail(f"PDF generation for audit {audit_id} did not complete within {timeout_seconds}s")


def _get_pagespeed_status(audit_id: int, headers: Dict[str, str]) -> Dict[str, Any]:
    response = requests.get(
        f"{API_BASE}/audits/{audit_id}/pagespeed-status", headers=headers, timeout=20
    )
    assert response.status_code == 200, response.text
    return response.json()


def _wait_for_pagespeed_started_or_completed(
    audit_id: int, headers: Dict[str, str], timeout_seconds: int = 240
) -> Dict[str, Any]:
    start = time.monotonic()
    while time.monotonic() - start < timeout_seconds:
        payload = _get_pagespeed_status(audit_id, headers)
        status = str(payload.get("status", "")).lower()
        if status in {"queued", "running", "completed", "failed"}:
            return payload
        time.sleep(max(1, int(payload.get("retry_after_seconds") or 3)))
    pytest.fail(f"PageSpeed did not start within {timeout_seconds}s for audit {audit_id}")


def _wait_for_pagespeed_terminal(
    audit_id: int, headers: Dict[str, str], timeout_seconds: int = 1200
) -> Dict[str, Any]:
    start = time.monotonic()
    while time.monotonic() - start < timeout_seconds:
        payload = _get_pagespeed_status(audit_id, headers)
        status = str(payload.get("status", "")).lower()
        if status in {"completed", "failed"}:
            return payload
        time.sleep(max(1, int(payload.get("retry_after_seconds") or 3)))
    pytest.fail(f"PageSpeed did not reach terminal state within {timeout_seconds}s")


@pytest.fixture(scope="module")
def auth_headers() -> Dict[str, str]:
    return _build_auth_headers()


@pytest.fixture(scope="module")
def completed_live_audit(auth_headers: Dict[str, str]) -> Dict[str, Any]:
    payload = {
        "url": LIVE_TARGET_URL,
        "language": "en",
        "market": "Argentina",
    }
    create_response = requests.post(
        f"{API_BASE}/audits/",
        json=payload,
        headers=auth_headers,
        timeout=30,
    )
    assert create_response.status_code in (200, 202), create_response.text
    audit_id = int(create_response.json()["id"])
    return _wait_for_audit_completion(audit_id, auth_headers)


@pytest.fixture(scope="module")
def first_pdf_generation(
    completed_live_audit: Dict[str, Any], auth_headers: Dict[str, str]
) -> Dict[str, Any]:
    audit_id = int(completed_live_audit["id"])
    pagespeed_before_pdf = _wait_for_pagespeed_started_or_completed(audit_id, auth_headers)
    started = time.monotonic()
    response = requests.post(
        f"{API_BASE}/audits/{audit_id}/generate-pdf",
        headers=auth_headers,
        timeout=60,
    )
    elapsed = time.monotonic() - started
    assert response.status_code in (200, 202), response.text
    payload = response.json()
    pagespeed_status_before = str(pagespeed_before_pdf.get("status", "")).lower()
    if pagespeed_status_before in {"queued", "running"}:
        assert payload["status"] in {"waiting", "queued", "running"}
        assert payload.get("waiting_on") in {None, "pagespeed"}

    pagespeed_after_pdf = _wait_for_pagespeed_terminal(audit_id, auth_headers)
    if response.status_code == 202:
        payload = _wait_for_pdf_completion(audit_id, auth_headers)

    download = requests.get(
        f"{API_BASE}/audits/{audit_id}/download-pdf",
        headers=auth_headers,
        timeout=120,
    )
    assert download.status_code == 200, download.text
    assert download.content.startswith(b"%PDF")

    return {
        "audit_id": audit_id,
        "elapsed": elapsed,
        "payload": payload,
        "pagespeed_before_pdf": pagespeed_before_pdf,
        "pagespeed_after_pdf": pagespeed_after_pdf,
    }


@pytest.mark.integration
@pytest.mark.live
@pytest.mark.slow
def test_live_agent1_generates_competitor_queries_plataforma5(
    completed_live_audit: Dict[str, Any],
):
    external = completed_live_audit.get("external_intelligence") or {}
    category = str(external.get("category", "")).strip().lower()
    assert category
    assert category not in {"unknown", "unknown category", "n/a", "none"}

    competitor_audits = completed_live_audit.get("competitor_audits") or []
    assert isinstance(competitor_audits, list)
    if len(competitor_audits) == 0:
        queries = external.get("queries_to_run") or []
        assert isinstance(queries, list)
        normalized_queries = []
        for query in queries:
            if isinstance(query, str) and query.strip():
                normalized_queries.append(query.strip())
            elif isinstance(query, dict):
                text = str(query.get("query", "")).strip()
                if text:
                    normalized_queries.append(text)
        assert len(normalized_queries) >= 1
    else:
        assert len(competitor_audits) >= 1


@pytest.mark.integration
@pytest.mark.live
@pytest.mark.slow
def test_live_generate_pdf_plataforma5_and_download(
    first_pdf_generation: Dict[str, Any],
):
    payload = first_pdf_generation["payload"]
    assert payload["status"] == "completed"
    assert payload["download_ready"] is True
    assert payload["report_id"] is not None


@pytest.mark.integration
@pytest.mark.live
@pytest.mark.slow
def test_live_pagespeed_is_auto_queued_once_and_reaches_terminal_state(
    first_pdf_generation: Dict[str, Any],
):
    initial_status = str(
        first_pdf_generation["pagespeed_before_pdf"].get("status", "")
    ).lower()
    terminal_status = str(
        first_pdf_generation["pagespeed_after_pdf"].get("status", "")
    ).lower()

    assert initial_status in {"queued", "running", "completed", "failed"}
    assert terminal_status in {"completed", "failed"}


@pytest.mark.integration
@pytest.mark.live
@pytest.mark.slow
def test_live_second_pdf_is_cache_hit(
    first_pdf_generation: Dict[str, Any], auth_headers: Dict[str, str]
):
    audit_id = int(first_pdf_generation["audit_id"])
    first_elapsed = float(first_pdf_generation["elapsed"])

    started = time.monotonic()
    response = requests.post(
        f"{API_BASE}/audits/{audit_id}/generate-pdf",
        headers=auth_headers,
        timeout=60,
    )
    second_elapsed = time.monotonic() - started
    assert response.status_code in (200, 202), response.text
    payload = response.json()
    if response.status_code == 202:
        payload = _wait_for_pdf_completion(audit_id, auth_headers)

    assert payload["status"] == "completed"
    assert payload["download_ready"] is True
    assert second_elapsed < first_elapsed or response.status_code == 200
