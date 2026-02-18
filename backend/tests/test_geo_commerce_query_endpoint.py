from datetime import datetime, timezone

from app.models import Audit, AuditStatus, GeoCommerceCampaign
from app.services.geo_commerce_service import GeoCommerceService


def _seed_audit(db_session) -> int:
    audit = Audit(
        url="https://store.example.com",
        domain="store.example.com",
        status=AuditStatus.COMPLETED,
        user_id="test-user",
        user_email="test@example.com",
        category="running shoes",
        market="AR",
        geo_score=35.0,
        target_audit={
            "site_metrics": {
                "schema_coverage_percent": 12.0,
                "structure_score_percent": 40.0,
                "h1_coverage_percent": 20.0,
                "faq_page_count": 0,
                "product_page_count": 3,
            }
        },
    )
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)
    return audit.id


def test_commerce_query_analyze_endpoint_shape(client, db_session, monkeypatch):
    audit_id = _seed_audit(db_session)

    async def fake_analyze_query(*, db, audit, query, market, top_k, language, llm_function):
        payload = {
            "mode": "query_analyzer",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "query": query,
            "market": market,
            "audited_domain": audit.domain,
            "target_position": 4,
            "top_result": {
                "position": 1,
                "title": "Mercado Libre Zapatillas",
                "url": "https://www.mercadolibre.com.ar/zapatillas",
                "domain": "mercadolibre.com.ar",
                "snippet": "Top result",
            },
            "results": [
                {
                    "position": 1,
                    "title": "Mercado Libre Zapatillas",
                    "url": "https://www.mercadolibre.com.ar/zapatillas",
                    "domain": "mercadolibre.com.ar",
                    "snippet": "Top result",
                },
                {
                    "position": 4,
                    "title": "Store Example Nike",
                    "url": "https://store.example.com/nike",
                    "domain": "store.example.com",
                    "snippet": "Your page",
                },
            ],
            "why_not_first": ["Low schema coverage."],
            "disadvantages_vs_top1": [
                {"area": "Schema", "gap": "No Product schema on PDP", "impact": "Lower citation eligibility"}
            ],
            "action_plan": [
                {
                    "priority": "P1",
                    "action": "Deploy Product + FAQ schema",
                    "expected_impact": "High",
                    "evidence": "Audit site metrics",
                }
            ],
            "evidence": [{"title": "SERP #1", "url": "https://www.mercadolibre.com.ar/zapatillas"}],
            "provider": "kimi-2.5-search",
        }
        row = GeoCommerceCampaign(
            audit_id=audit.id,
            market=market,
            channels=["kimi-search"],
            objective="Query test",
            payload=payload,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    monkeypatch.setattr(GeoCommerceService, "analyze_query", fake_analyze_query)

    response = client.post(
        "/api/geo/commerce-query/analyze",
        json={
            "audit_id": audit_id,
            "query": "zapatilla nike",
            "market": "AR",
            "top_k": 10,
            "language": "es",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "zapatilla nike"
    assert payload["market"] == "AR"
    assert payload["audited_domain"] == "store.example.com"
    assert payload["target_position"] == 4
    assert payload["top_result"]["domain"] == "mercadolibre.com.ar"
    assert payload["why_not_first"]
    assert payload["action_plan"]


def test_commerce_query_requires_query_and_market(client, db_session):
    audit_id = _seed_audit(db_session)

    missing_query = client.post(
        "/api/geo/commerce-query/analyze",
        json={"audit_id": audit_id, "market": "AR"},
    )
    assert missing_query.status_code == 422

    missing_market = client.post(
        "/api/geo/commerce-query/analyze",
        json={"audit_id": audit_id, "query": "zapatilla nike"},
    )
    assert missing_market.status_code == 422

