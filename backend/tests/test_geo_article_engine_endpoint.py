from datetime import datetime, timedelta, timezone

from app.core.config import settings
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

    async def fake_prepare_batch_seed_data(*args, **kwargs):
        return {
            "strategy_run_id": "strategy-auto",
            "strategy_items": [
                {
                    "title": "Auto title",
                    "target_keyword": "auto keyword",
                    "strategy_run_id": "strategy-auto",
                }
            ],
            "strategy_source": "generated_auto",
            "article_authority_assignments": {1: []},
            "global_authority_urls": [],
            "unmatched_authority_urls": [],
            "authority_source_cache": [],
        }

    def fake_create_batch(**kwargs):
        raise ArticleDataPackIncompleteError(
            "ARTICLE_DATA_PACK_INCOMPLETE: missing required fields"
        )

    monkeypatch.setattr(
        GeoArticleEngineService,
        "prepare_batch_seed_data",
        staticmethod(fake_prepare_batch_seed_data),
    )
    monkeypatch.setattr(
        GeoArticleEngineService, "create_batch", staticmethod(fake_create_batch)
    )

    response = client.post(
        "/api/v1/geo/article-engine/generate",
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


def test_article_engine_generate_auto_builds_strategy_when_missing(
    client, db_session, monkeypatch
):
    audit_id = _seed_audit(db_session)

    async def fake_prepare_batch_seed_data(*args, **kwargs):
        return {
            "strategy_run_id": "strategy-auto",
            "strategy_items": [
                {
                    "title": "Auto title",
                    "target_keyword": "auto keyword",
                    "strategy_run_id": "strategy-auto",
                }
            ],
            "strategy_source": "generated_auto",
            "article_authority_assignments": {1: []},
            "global_authority_urls": [],
            "unmatched_authority_urls": [],
            "authority_source_cache": [],
        }

    def fake_create_batch(**kwargs):
        row = GeoArticleBatch(
            audit_id=kwargs["audit"].id,
            requested_count=kwargs["article_count"],
            language=kwargs["language"],
            tone=kwargs["tone"],
            include_schema=kwargs["include_schema"],
            status="processing",
            summary={
                "generated_count": 0,
                "failed_count": 0,
                "strategy_run_id": kwargs["strategy_run_id"],
                "strategy_source": kwargs["strategy_source"],
                "generated_titles": kwargs["strategy_items"],
            },
            articles=[
                {
                    "index": 1,
                    "title": "Auto title",
                    "target_keyword": "auto keyword",
                    "focus_url": "https://store.example.com/",
                    "generation_status": "queued",
                    "user_authority_urls": [],
                }
            ],
        )
        kwargs["db"].add(row)
        kwargs["db"].commit()
        kwargs["db"].refresh(row)
        return row

    class DummyResult:
        id = "celery-task-auto"

    monkeypatch.setattr(
        GeoArticleEngineService,
        "prepare_batch_seed_data",
        staticmethod(fake_prepare_batch_seed_data),
    )
    monkeypatch.setattr(
        GeoArticleEngineService, "create_batch", staticmethod(fake_create_batch)
    )
    monkeypatch.setattr(
        "app.workers.tasks.generate_article_batch_task.delay",
        lambda _batch_id: DummyResult(),
    )

    response = client.post(
        "/api/v1/geo/article-engine/generate",
        json={
            "audit_id": audit_id,
            "article_count": 1,
            "language": "es",
            "tone": "growth",
            "include_schema": True,
            "run_async": True,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["strategy_run_id"] == "strategy-auto"
    assert payload["summary"]["strategy_source"] == "generated_auto"


def test_article_engine_async_generate_and_status_endpoint(
    client, db_session, monkeypatch
):
    audit_id = _seed_audit(db_session)

    async def fake_prepare_batch_seed_data(*args, **kwargs):
        return {
            "strategy_run_id": "strategy-test",
            "strategy_items": [
                {
                    "title": f"Queued article {idx + 1}",
                    "target_keyword": f"keyword {idx + 1}",
                    "strategy_run_id": "strategy-test",
                }
                for idx in range(kwargs["article_count"])
            ],
            "strategy_source": "generated_auto",
            "article_authority_assignments": {
                idx + 1: [] for idx in range(kwargs["article_count"])
            },
            "global_authority_urls": [],
            "unmatched_authority_urls": [],
            "authority_source_cache": [],
        }

    def fake_create_batch(
        *,
        db,
        audit,
        article_count,
        language,
        tone,
        include_schema,
        market=None,
        strategy_run_id=None,
        strategy_items=None,
        strategy_source="generated_auto",
        article_authority_assignments=None,
        global_authority_urls=None,
        unmatched_authority_urls=None,
        authority_source_cache=None,
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
                "strategy_run_id": strategy_run_id or "strategy-test",
                "strategy_source": strategy_source,
                "generated_titles": strategy_items or [],
            },
            articles=[
                {
                    "index": 1,
                    "title": "Queued title",
                    "target_keyword": "queued keyword",
                    "focus_url": "https://store.example.com/",
                    "generation_status": "queued",
                }
            ],
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
        GeoArticleEngineService,
        "prepare_batch_seed_data",
        staticmethod(fake_prepare_batch_seed_data),
    )
    monkeypatch.setattr(
        GeoArticleEngineService, "create_batch", staticmethod(fake_create_batch)
    )
    monkeypatch.setattr(
        "app.workers.tasks.generate_article_batch_task.delay", fake_delay
    )

    response = client.post(
        "/api/v1/geo/article-engine/generate",
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

    status_res = client.get(f"/api/v1/geo/article-engine/status/{payload['batch_id']}")
    assert status_res.status_code == 200
    status_payload = status_res.json()
    assert status_payload["has_data"] is True
    assert status_payload["status"] == "processing"
    assert "markdown" not in status_payload["articles"][0]
    assert "sources" not in status_payload["articles"][0]
    assert "keyword_strategy" not in status_payload["articles"][0]
    assert "competitor_gap_map" not in status_payload["articles"][0]


def test_article_engine_status_reconciles_task_failure_to_failed(
    client, db_session, monkeypatch
):
    audit_id = _seed_audit(db_session)
    batch = GeoArticleBatch(
        audit_id=audit_id,
        requested_count=2,
        language="en",
        tone="executive",
        include_schema=True,
        status="processing",
        summary={
            "task_id": "celery-task-failure",
            "generated_count": 0,
            "failed_count": 0,
            "last_progress_at": datetime.now(timezone.utc).isoformat(),
        },
        articles=[],
    )
    db_session.add(batch)
    db_session.commit()
    db_session.refresh(batch)

    class DummyResult:
        state = "FAILURE"

    monkeypatch.setattr(
        "app.api.routes.geo.celery_app.AsyncResult", lambda _task_id: DummyResult()
    )

    response = client.get(f"/api/v1/geo/article-engine/status/{batch.id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["summary"]["task_state"] == "FAILURE"
    assert "BATCH_TASK_FAILURE" in payload["summary"]["failure_reason"]
    assert payload["articles"] == []


def test_article_engine_status_reconciles_stale_processing_to_failed(
    client, db_session, monkeypatch
):
    audit_id = _seed_audit(db_session)
    batch = GeoArticleBatch(
        audit_id=audit_id,
        requested_count=1,
        language="en",
        tone="executive",
        include_schema=True,
        status="processing",
        summary={
            "generated_count": 0,
            "failed_count": 0,
            "last_progress_at": (
                datetime.now(timezone.utc) - timedelta(seconds=3600)
            ).isoformat(),
        },
        articles=[],
    )
    db_session.add(batch)
    db_session.commit()
    db_session.refresh(batch)

    monkeypatch.setattr(settings, "GEO_ARTICLE_STALE_SECONDS", 1200, raising=False)

    response = client.get(f"/api/v1/geo/article-engine/status/{batch.id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["summary"]["task_state"] == "UNKNOWN"
    assert payload["summary"]["failure_reason"].startswith("BATCH_STALLED")
    assert payload["articles"] == []


def test_article_engine_status_marks_legacy_batches_read_only(client, db_session):
    audit_id = _seed_audit(db_session)
    batch = GeoArticleBatch(
        audit_id=audit_id,
        requested_count=1,
        language="en",
        tone="executive",
        include_schema=True,
        status="completed",
        summary={"generated_count": 1, "failed_count": 0},
        articles=[
            {
                "index": 1,
                "title": "Legacy article",
                "target_keyword": "legacy keyword",
                "focus_url": "https://store.example.com/",
                "generation_status": "completed",
            }
        ],
    )
    db_session.add(batch)
    db_session.commit()
    db_session.refresh(batch)

    response = client.get(f"/api/v1/geo/article-engine/status/{batch.id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["is_legacy"] is True
    assert payload["can_regenerate"] is False
    assert "markdown" not in payload["articles"][0]


def test_article_engine_latest_keeps_full_article_payload(client, db_session):
    audit_id = _seed_audit(db_session)
    batch = GeoArticleBatch(
        audit_id=audit_id,
        requested_count=1,
        language="en",
        tone="executive",
        include_schema=True,
        status="completed",
        summary={"generated_count": 1, "failed_count": 0},
        articles=[
            {
                "index": 1,
                "title": "Full article",
                "target_keyword": "full keyword",
                "focus_url": "https://store.example.com/",
                "generation_status": "completed",
                "citation_readiness_score": 88,
                "markdown": "# Full markdown",
                "sources": [
                    {"title": "Authority", "url": "https://authority.example.com/guide"}
                ],
                "keyword_strategy": {
                    "primary_keyword": "full keyword",
                    "secondary_keywords": ["full keyword guide"],
                    "search_intent": "informational",
                },
                "competitor_gap_map": {"content": [{"gap": "Need more detail"}]},
                "evidence_summary": [
                    {
                        "claim": "Authority benchmark",
                        "source_url": "https://authority.example.com/guide",
                    }
                ],
            }
        ],
    )
    db_session.add(batch)
    db_session.commit()
    db_session.refresh(batch)

    response = client.get(f"/api/v1/geo/article-engine/latest/{audit_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["has_data"] is True
    assert payload["articles"][0]["markdown"] == "# Full markdown"
    assert (
        payload["articles"][0]["sources"][0]["url"]
        == "https://authority.example.com/guide"
    )
    assert (
        payload["articles"][0]["keyword_strategy"]["primary_keyword"] == "full keyword"
    )


def test_article_engine_regenerate_rejects_legacy_batches(client, db_session):
    audit_id = _seed_audit(db_session)
    batch = GeoArticleBatch(
        audit_id=audit_id,
        requested_count=1,
        language="en",
        tone="executive",
        include_schema=True,
        status="completed",
        summary={"generated_count": 1, "failed_count": 0},
        articles=[
            {
                "index": 1,
                "title": "Legacy article",
                "target_keyword": "legacy keyword",
                "focus_url": "https://store.example.com/",
                "generation_status": "completed",
            }
        ],
    )
    db_session.add(batch)
    db_session.commit()
    db_session.refresh(batch)

    response = client.post(
        f"/api/v1/geo/article-engine/{batch.id}/articles/1/regenerate",
        json={"authority_urls": ["https://authority.example.com/guide"]},
    )
    assert response.status_code == 422
    payload = response.json()
    assert payload["detail"]["code"] == "LEGACY_BATCH_READ_ONLY"
