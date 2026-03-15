import os

from locust import HttpUser, between, task


class BackendUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        token = os.getenv("PERF_BEARER_TOKEN", "").strip()
        self.auth_headers = {"Authorization": f"Bearer {token}"} if token else {}

    @task(3)
    def health(self):
        self.client.get("/api/v1/health/", name="/api/v1/health/")

    @task(2)
    def audits_list(self):
        self.client.get(
            "/api/v1/audits/", headers=self.auth_headers, name="/api/v1/audits/"
        )

    @task(1)
    def geo_dashboard(self):
        audit_id = os.getenv("PERF_AUDIT_ID", "").strip()
        if not audit_id:
            return
        self.client.get(
            f"/api/v1/geo/dashboard/{audit_id}",
            headers=self.auth_headers,
            name="/api/v1/geo/dashboard/{audit_id}",
        )
