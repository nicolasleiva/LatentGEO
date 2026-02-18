from datetime import datetime, timedelta, timezone

from app.models import Audit, AuditStatus, CitationTracking, GeoArticleBatch, Keyword
from app.services.geo_article_engine_service import GeoArticleEngineService


def _seed_audit(db_session):
    audit = Audit(
        url="https://store.example.com",
        domain="store.example.com",
        status=AuditStatus.COMPLETED,
        user_id="test-user",
        user_email="test@example.com",
        market="US",
        category="running shoes",
        geo_score=34.2,
        target_audit={
            "site_metrics": {
                "schema_coverage_percent": 20.0,
                "faq_page_count": 0,
                "product_page_count": 4,
                "structure_score_percent": 42.0,
            },
            "audited_page_paths": [
                "/",
                "/products/nike-pegasus",
                "/products/nike-vomero",
            ],
            "benchmark": {"geo_score": 34.2},
        },
        search_results={
            "best nike running shoes": {
                "items": [
                    {
                        "title": "Nike Running Guide",
                        "link": "https://www.nike.com/running",
                        "snippet": "Guide to choosing running shoes",
                    },
                    {
                        "title": "Statista Sports Report",
                        "link": "https://www.statista.com/topics/1160/sports/",
                        "snippet": "Industry data and trends",
                    },
                ]
            },
            "nike pegasus review": {
                "items": [
                    {
                        "title": "Runner's World Review",
                        "link": "https://www.runnersworld.com/gear/a19872195/best-running-shoes/",
                        "snippet": "Expert review and benchmarks",
                    }
                ]
            },
        },
        competitor_audits=[
            {
                "url": "https://www.mercadolibre.com/",
                "domain": "mercadolibre.com",
                "geo_score": 62.1,
            },
            {
                "url": "https://www.amazon.com/",
                "domain": "amazon.com",
                "geo_score": 74.0,
            },
        ],
        competitors=["https://www.mercadolibre.com/", "https://www.amazon.com/"],
    )
    db_session.add(audit)
    db_session.flush()

    db_session.add(
        Keyword(
            audit_id=audit.id,
            term="nike running shoes",
            volume=8800,
            difficulty=62,
            intent="commercial",
        )
    )
    db_session.add(
        Keyword(
            audit_id=audit.id,
            term="nike pegasus review",
            volume=5400,
            difficulty=55,
            intent="informational",
        )
    )

    now = datetime.now(timezone.utc)
    db_session.add(
        CitationTracking(
            audit_id=audit.id,
            query="best nike running shoes",
            llm_name="kimi",
            is_mentioned=True,
            citation_text="store.example.com appears as direct recommendation",
            sentiment="positive",
            position=1,
            tracked_at=now,
        )
    )
    db_session.add(
        CitationTracking(
            audit_id=audit.id,
            query="nike pegasus alternatives",
            llm_name="kimi",
            is_mentioned=False,
            tracked_at=now - timedelta(days=30),
        )
    )

    db_session.commit()
    return audit.id


def test_generate_commerce_campaign_and_latest(client, db_session):
    audit_id = _seed_audit(db_session)

    response = client.post(
        "/api/geo/commerce-campaign/generate",
        json={
            "audit_id": audit_id,
            "market": "US",
            "channels": ["chatgpt", "perplexity", "google-ai"],
            "competitor_domains": ["mercadolibre.com"],
            "use_ai_playbook": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["campaign_id"] > 0
    assert payload["payload"]["kpis"]["primary_kpi"] == "Citation Share"
    assert len(payload["payload"]["opportunities"]) >= 3

    latest = client.get(f"/api/geo/commerce-campaign/latest/{audit_id}")
    assert latest.status_code == 200
    latest_json = latest.json()
    assert latest_json["has_data"] is True
    assert latest_json["payload"]["market"] == "US"


def test_generate_article_engine_batch_and_latest(client, db_session, monkeypatch):
    audit_id = _seed_audit(db_session)

    def fake_create_batch(
        *, db, audit, article_count, language, tone, include_schema, market=None
    ):
        row = GeoArticleBatch(
            audit_id=audit.id,
            requested_count=article_count,
            language=language,
            tone=tone,
            include_schema=include_schema,
            status="processing",
            summary={
                "generated_count": 0,
                "failed_count": 0,
                "average_citation_readiness_score": 0.0,
            },
            articles=[],
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    async def fake_process_batch(db, batch_id):
        row = db.query(GeoArticleBatch).filter(GeoArticleBatch.id == batch_id).first()
        row.status = "completed"
        row.summary = {
            "generated_count": 2,
            "failed_count": 0,
            "average_citation_readiness_score": 88.0,
        }
        row.articles = [
            {
                "index": 1,
                "title": "Articulo 1",
                "target_keyword": "nike running shoes",
                "focus_url": "https://store.example.com/",
                "generation_status": "completed",
                "citation_readiness_score": 90,
                "keyword_strategy": {
                    "primary_keyword": "nike running shoes",
                    "secondary_keywords": ["nike pegasus", "running shoes guide"],
                    "search_intent": "commercial",
                },
                "competitor_gap_map": {"schema": [{"gap": "Missing Product schema"}]},
                "evidence_summary": [
                    {
                        "claim": "Market benchmark",
                        "source_url": "https://www.statista.com/",
                    }
                ],
                "markdown": "# Articulo 1",
                "sources": [{"title": "Statista", "url": "https://www.statista.com/"}],
            },
            {
                "index": 2,
                "title": "Articulo 2",
                "target_keyword": "nike pegasus review",
                "focus_url": "https://store.example.com/products/nike-pegasus",
                "generation_status": "completed",
                "citation_readiness_score": 86,
                "keyword_strategy": {
                    "primary_keyword": "nike pegasus review",
                    "secondary_keywords": [
                        "nike pegasus comparison",
                        "nike pegasus pricing",
                    ],
                    "search_intent": "comparison",
                },
                "competitor_gap_map": {"content": [{"gap": "Weak comparison copy"}]},
                "evidence_summary": [
                    {
                        "claim": "Review benchmark",
                        "source_url": "https://www.runnersworld.com/",
                    }
                ],
                "markdown": "# Articulo 2",
                "sources": [
                    {"title": "Runner's World", "url": "https://www.runnersworld.com/"}
                ],
            },
        ]
        db.commit()
        db.refresh(row)
        return row

    monkeypatch.setattr(
        GeoArticleEngineService, "create_batch", staticmethod(fake_create_batch)
    )
    monkeypatch.setattr(
        GeoArticleEngineService, "process_batch", staticmethod(fake_process_batch)
    )

    response = client.post(
        "/api/geo/article-engine/generate",
        json={
            "audit_id": audit_id,
            "article_count": 2,
            "language": "es",
            "tone": "growth",
            "include_schema": True,
            "run_async": False,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["batch_id"] > 0
    assert body["summary"]["generated_count"] == 2
    assert len(body["articles"]) == 2
    assert body["articles"][0]["citation_readiness_score"] > 0
    assert body["articles"][0]["generation_status"] == "completed"
    assert body["articles"][0]["keyword_strategy"]["primary_keyword"]
    assert "competitor_gap_map" in body["articles"][0]

    latest = client.get(f"/api/geo/article-engine/latest/{audit_id}")
    assert latest.status_code == 200
    latest_json = latest.json()
    assert latest_json["has_data"] is True
    assert latest_json["summary"]["generated_count"] == 2


def test_geo_legacy_endpoints_shapes(client, db_session):
    audit_id = _seed_audit(db_session)

    citations = client.get(f"/api/geo/citations/{audit_id}?limit=10")
    assert citations.status_code == 200
    citations_json = citations.json()
    assert "citations" in citations_json
    assert isinstance(citations_json["citations"], list)

    history = client.get(f"/api/geo/citation-history/{audit_id}")
    assert history.status_code == 200
    history_json = history.json()
    assert "history" in history_json
    assert isinstance(history_json["history"], list)

    templates = client.get("/api/geo/content-templates?category=blog")
    assert templates.status_code == 200
    templates_json = templates.json()
    assert "templates" in templates_json
    assert isinstance(templates_json["templates"], list)

    analyze = client.post(
        "/api/geo/analyze-content",
        json={"content": "## FAQ\nHow to cite sources?\nUse trusted references."},
    )
    assert analyze.status_code == 200
    analyze_json = analyze.json()
    assert "score" in analyze_json
    assert "geo_readiness" in analyze_json
