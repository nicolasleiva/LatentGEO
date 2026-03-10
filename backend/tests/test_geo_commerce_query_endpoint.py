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

    async def fake_analyze_query(
        *, db, audit, query, market, top_k, language, llm_function
    ):
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
                {
                    "area": "Schema",
                    "gap": "No Product schema on PDP",
                    "impact": "Lower citation eligibility",
                }
            ],
            "action_plan": [
                {
                    "priority": "P1",
                    "action": "Deploy Product + FAQ schema",
                    "expected_impact": "High",
                    "evidence": "Audit site metrics",
                }
            ],
            "evidence": [
                {
                    "title": "SERP #1",
                    "url": "https://www.mercadolibre.com.ar/zapatillas",
                }
            ],
            "site_root_summary": {
                "path": "/",
                "url": "https://store.example.com",
                "overall_score": 58,
                "schema_score": 20,
                "content_score": 42,
                "h1_score": 30,
                "critical_issues": 3,
                "high_issues": 2,
            },
            "product_intelligence": {
                "is_ecommerce": True,
                "confidence_score": 88,
                "platform": "shopify",
                "product_pages_count": 12,
                "category_pages_count": 4,
                "schema_analysis": {"average_completeness": 51},
            },
            "root_cause_summary": [
                {
                    "title": "Root authority is weak",
                    "finding": "Homepage schema coverage is too low.",
                    "owner": "SEO",
                }
            ],
            "search_engine_fixes": [
                {
                    "priority": "P1",
                    "action": "Tighten the query-intent block on the root page.",
                    "expected_impact": "High",
                    "evidence": "Root page snapshot.",
                }
            ],
            "merchandising_fixes": [
                {
                    "priority": "P1",
                    "action": "Expose price and stock details on PDPs.",
                    "expected_impact": "High",
                    "evidence": "Offer data gap.",
                }
            ],
            "technical_watchouts": [
                {
                    "priority": "HIGH",
                    "owner": "DevOps",
                    "action": "Reduce origin response time.",
                    "evidence": "TTFB > 800ms.",
                }
            ],
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
        "/api/v1/geo/commerce-query/analyze",
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
    assert payload["site_root_summary"]["path"] == "/"
    assert payload["product_intelligence"]["is_ecommerce"] is True
    assert payload["root_cause_summary"][0]["title"] == "Root authority is weak"
    assert payload["technical_watchouts"][0]["owner"] == "DevOps"


def test_commerce_query_requires_query_and_market(client, db_session):
    audit_id = _seed_audit(db_session)

    missing_query = client.post(
        "/api/v1/geo/commerce-query/analyze",
        json={"audit_id": audit_id, "market": "AR"},
    )
    assert missing_query.status_code == 422

    missing_market = client.post(
        "/api/v1/geo/commerce-query/analyze",
        json={"audit_id": audit_id, "query": "zapatilla nike"},
    )
    assert missing_market.status_code == 422
