
import requests
import time
import os
import sys
import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION_TESTS") != "1",
    reason="Requires backend running on localhost",
)

BASE_URL = "http://localhost:8000"
def wait_for_backend():
    print("Waiting for backend to be ready...")
    for _ in range(30):
        try:
            r = requests.get(f"{BASE_URL}/health")
            if r.status_code == 200:
                print("Backend is ready!")
                return True
        except:
            pass
        time.sleep(2)
    return False

def test_docker_pdf_generation():
    if not wait_for_backend():
        pytest.skip("Backend not available for integration test")

    # List audits and prefer a completed one
    r = requests.get(f"{BASE_URL}/api/audits?limit=1")
    assert r.status_code == 200, f"Failed to list audits: {r.status_code}"
    response_data = r.json()
    audits = response_data.get('audits', []) if isinstance(response_data, dict) else response_data

    target_audit_id = None

    if audits:
        audit = audits[0]
        target_audit_id = audit.get('id')
        status = audit.get('status')
        if status != "completed":
            pytest.skip("No completed audit available to generate PDF in test environment")
    else:
        # Create one and assert creation succeeded
        r = requests.post(f"{BASE_URL}/api/audits", json={"url": "https://docker-test.com"})
        assert r.status_code in (200, 201, 202), f"Failed to create audit: {r.status_code} {r.text}"
        audit = r.json()
        target_audit_id = audit.get('id')
        assert target_audit_id, "Created audit has no id"

    # Attempt to generate PDF
    url = f"{BASE_URL}/api/audits/{target_audit_id}/generate-pdf"
    r = requests.post(url, timeout=60)
    assert r.status_code == 200, f"PDF generation failed: {r.status_code} {r.text}"
    data = r.json()
    assert 'pdf_path' in data or 'file_size' in data
    assert data.get('file_size', 0) >= 0

