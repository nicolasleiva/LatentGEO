from app.models import Audit, AuditStatus, Competitor


def test_competitor_analytics_excludes_incomplete_competitors_from_averages(
    client, db_session
):
    audit = Audit(
        url="https://example.com",
        domain="example.com",
        status=AuditStatus.COMPLETED,
        user_id="test-user",
        user_email="test@example.com",
        target_audit={"schema": {"schema_types": ["Organization"]}},
        fix_plan=[{"priority": "HIGH"}],
    )
    db_session.add(audit)
    db_session.flush()

    db_session.add(
        Competitor(
            audit_id=audit.id,
            url="https://leader.example.com",
            domain="leader.example.com",
            geo_score=0,
            audit_data={
                "url": "https://leader.example.com",
                "status": 200,
                "schema_types": ["Organization", "FAQPage"],
                "schema": {"schema_presence": {"status": "present"}},
                "structure": {
                    "semantic_html": {"score_percent": 80},
                    "h1_check": {"status": "pass"},
                },
                "eeat": {"author_presence": {"status": "pass"}},
                "content": {"conversational_tone": {"score": 7}},
            },
        )
    )
    db_session.add(
        Competitor(
            audit_id=audit.id,
            url="https://incomplete.example.com",
            domain="incomplete.example.com",
            geo_score=0,
            audit_data={
                "url": "https://incomplete.example.com",
                "status": 200,
            },
        )
    )
    db_session.commit()

    response = client.get(f"/api/v1/analytics/competitors/{audit.id}")
    assert response.status_code == 200
    payload = response.json()

    assert payload["total_competitors"] == 1
    assert len(payload["competitors"]) == 1
    assert payload["competitors"][0]["domain"] == "leader.example.com"
    assert payload["average_competitor_score"] > 0
    assert "Schema faltante: FAQPage" in payload["identified_gaps"]
