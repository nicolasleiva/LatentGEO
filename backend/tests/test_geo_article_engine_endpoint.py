from app.models import Audit, AuditStatus, GeoArticleBatch
from app.services.geo_article_engine_service import (
    ArticleDataPackIncompleteError,
    GeoArticleEngineService,
)


def _seed_audit(db_session) -> int:
    audit = Audit(
        url="https://store.example.com",
        domain="store.example.com",
        status=AuditStatus.COMPLETED,
        user_id="test-user",
        user_email="test@example.com",
        market="AR",
        target_audit={
            "audited_page_paths": ["/", "/products/nike-air"],
            "site_metrics": {"structure_score_percent": 44.0},
        },
    )
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)
    return audit.id


def test_article_engine_generate_returns_422_when_data_pack_incomplete(
    client, db_session, monkeypatch
):
    audit_id = _seed_audit(db_session)

    def fake_create_batch(**kwargs):
        raise ArticleDataPackIncompleteError(
            "ARTICLE_DATA_PACK_INCOMPLETE: missing required fields"
        )

    monkeypatch.setattr(
        GeoArticleEngineService, "create_batch", staticmethod(fake_create_batch)
    )

    response = client.post(
        "/api/geo/article-engine/generate",
        json={
            "audit_id": audit_id,
            "article_count": 1,
            "language": "es",
            "tone": "growth",
            "include_schema": True,
            "run_async": True,
        },
    )
    assert response.status_code == 422
    payload = response.json()
    assert payload["detail"]["code"] == "ARTICLE_DATA_PACK_INCOMPLETE"


def test_article_engine_async_generate_and_status_endpoint(
    client, db_session, monkeypatch
):
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
            },
            articles=[],
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    class DummyResult:
        id = "celery-task-123"

    def fake_delay(_batch_id):
        return DummyResult()

    monkeypatch.setattr(
        GeoArticleEngineService, "create_batch", staticmethod(fake_create_batch)
    )
    monkeypatch.setattr(
        "app.workers.tasks.generate_article_batch_task.delay", fake_delay
    )

    response = client.post(
        "/api/geo/article-engine/generate",
        json={
            "audit_id": audit_id,
            "article_count": 2,
            "language": "en",
            "tone": "executive",
            "include_schema": True,
            "run_async": True,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "processing"
    assert payload["summary"]["task_id"] == "celery-task-123"

    status_res = client.get(f"/api/geo/article-engine/status/{payload['batch_id']}")
    assert status_res.status_code == 200
    status_payload = status_res.json()
    assert status_payload["has_data"] is True
    assert status_payload["status"] == "processing"
