import os
from urllib.parse import urlparse

from app.models import Audit, AuditStatus
from app.services.citation_tracker_service import CitationTrackerService
from app.services.competitor_citation_service import CompetitorCitationService


def _test_target_url() -> str:
    return os.getenv("TEST_TARGET_URL", "https://robot.com").strip()


def _test_target_domain(url: str) -> str:
    parsed = urlparse(url if "://" in url else f"https://{url}")
    return (parsed.hostname or "robot.com").strip().lower()


def _seed_audit(db_session) -> int:
    test_url = _test_target_url()
    audit = Audit(
        url=test_url,
        domain=_test_target_domain(test_url),
        status=AuditStatus.COMPLETED,
        user_id="test-user",
        user_email="test@example.com",
        geo_score=41.2,
        target_audit={
            "site_metrics": {
                "schema_coverage_percent": 22.0,
                "structure_score_percent": 47.5,
                "h1_coverage_percent": 61.0,
                "faq_page_count": 0,
                "product_page_count": 8,
                "pages_analyzed": 12,
            }
        },
    )
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)
    return audit.id


def test_geo_dashboard_survives_citation_history_failures(
    client, db_session, monkeypatch
):
    audit_id = _seed_audit(db_session)

    def explode(*args, **kwargs):
        raise RuntimeError("history unavailable")

    monkeypatch.setattr(CitationTrackerService, "get_citation_history", explode)

    response = client.get(f"/api/v1/geo/dashboard/{audit_id}")
    assert response.status_code == 200

    payload = response.json()
    assert payload["audit_id"] == audit_id
    assert payload["citation_tracking"]["citation_rate"] == 0
    assert payload["citation_tracking"]["mentions"] == 0
    assert "commerce_query_analyzer" in payload


def test_geo_dashboard_sanitizes_competitor_error_payload(
    client, db_session, monkeypatch
):
    audit_id = _seed_audit(db_session)

    monkeypatch.setattr(
        CompetitorCitationService,
        "get_citation_benchmark",
        lambda *_args, **_kwargs: {
            "has_data": False,
            "error": "Traceback (most recent call last): hidden",
            "error_code": "raw_backend_failure",
        },
    )

    response = client.get(f"/api/v1/geo/dashboard/{audit_id}")
    assert response.status_code == 200

    payload = response.json()
    gap_analysis = payload["competitor_benchmark"]["gap_analysis"]
    assert gap_analysis == {
        "has_data": False,
        "has_gaps": None,
        "error": "internal_error",
        "error_code": "dependency_error",
    }


def test_competitor_benchmark_endpoint_sanitizes_error_payload(
    client, db_session, monkeypatch
):
    audit_id = _seed_audit(db_session)

    monkeypatch.setattr(
        CompetitorCitationService,
        "get_citation_benchmark",
        lambda *_args, **_kwargs: {
            "has_data": False,
            "has_gaps": None,
            "error": "Traceback secret details",
            "error_code": "totally_unknown_code",
        },
    )

    response = client.get(f"/api/v1/geo/competitor-analysis/benchmark/{audit_id}")
    assert response.status_code == 200
    assert response.json() == {
        "has_data": False,
        "has_gaps": None,
        "error": "internal_error",
        "error_code": "dependency_error",
    }

