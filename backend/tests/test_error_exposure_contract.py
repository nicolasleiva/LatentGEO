from fastapi.testclient import TestClient

from app.core.database import get_db
from app.core.llm_kimi import KimiSearchError
from app.main import app
from app.models import Audit, AuditStatus
from app.services.geo_commerce_service import GeoCommerceService


def _seed_audit(db_session) -> int:
    audit = Audit(
        url="https://www.robot.com",
        domain="www.robot.com",
        status=AuditStatus.COMPLETED,
        user_id="test-user",
        user_email="test@example.com",
    )
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)
    return audit.id


def test_geo_commerce_query_hides_internal_exception_details(
    client, db_session, monkeypatch
):
    audit_id = _seed_audit(db_session)

    async def fake_analyze_query(**kwargs):
        raise KimiSearchError("upstream timeout with token=super-secret-value")

    monkeypatch.setattr(GeoCommerceService, "analyze_query", fake_analyze_query)

    response = client.post(
        "/api/v1/geo/commerce-query/analyze",
        json={
            "audit_id": audit_id,
            "query": "robot vacuum",
            "market": "US",
            "top_k": 5,
            "language": "en",
        },
    )

    assert response.status_code == 502
    detail = response.json()["detail"]
    assert detail["code"] == "KIMI_GENERATION_FAILED"
    assert detail["message"] == "Upstream generation dependency failed."
    assert "secret" not in str(detail).lower()
    assert "timeout" not in str(detail).lower()


def test_health_readiness_hides_database_error_details():
    class FailingDb:
        def execute(self, _query):
            raise RuntimeError("db password=leaked-value")

    def override_get_db():
        yield FailingDb()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            response = test_client.get("/health/ready")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready", "error": "dependency_unavailable"}
