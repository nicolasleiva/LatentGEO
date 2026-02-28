from app.models import Audit, AuditStatus
from app.services.citation_tracker_service import CitationTrackerService


def _seed_audit(db_session) -> int:
    audit = Audit(
        url="https://shop.example.com",
        domain="shop.example.com",
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

