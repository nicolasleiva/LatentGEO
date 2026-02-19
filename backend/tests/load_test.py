"""
Locust load profile for GEO endpoints.

Usage example:
  locust -f tests/load_test.py --host=https://staging.example.com --headless -u 50 -r 5 --run-time 5m
"""

from __future__ import annotations

import os
from typing import Dict

from locust import HttpUser, between, task


def _build_headers() -> Dict[str, str]:
    token = os.getenv("PERF_BEARER_TOKEN", "").strip()
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


class GeoLoadUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self) -> None:
        self.audit_id = os.getenv("PERF_AUDIT_ID", "").strip()
        self.headers = _build_headers()

    @task(2)
    def health_check(self) -> None:
        self.client.get("/health", name="/health", headers=self.headers)

    @task(5)
    def geo_dashboard(self) -> None:
        if not self.audit_id:
            # Keep a stable request profile even if audit id is not configured.
            self.client.get("/health", name="/health-fallback", headers=self.headers)
            return
        self.client.get(
            f"/api/geo/dashboard/{self.audit_id}",
            name="/api/geo/dashboard/:id",
            headers=self.headers,
        )
