"""
Tests para el API de Auditorías
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from app.core.config import settings
from app.models import Audit, AuditPageSpeedJob, AuditPdfJob, Competitor, Report
from app.schemas import AuditStatus
from app.services.audit_service import AuditService
from app.services.cache_service import cache
from app.services.pagespeed_job_service import PageSpeedJobService
from app.services.pdf_job_service import PDFJobService
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker


def test_create_audit_dispatches_task(client: TestClient):
    """
    Verifica que al crear una auditoría:
    1. Se retorna un estado 201 CREATED.
    2. El estado de la auditoría es PENDING.
    3. Se despacha una tarea de Celery 'run_audit_task'.
    """
    # Mock de la tarea de Celery
    with patch("app.api.routes.audits.run_audit_task.delay") as mock_delay:
        mock_delay.return_value = SimpleNamespace(id="test-task-id")

        # Datos para la nueva auditoría
        audit_data = {
            "url": "https://ceibo.digital",
            "max_crawl": 10,
            "max_audit": 2,
            "market": "AR",
        }

        # Realizar la petición
        response = client.post("/api/v1/audits/", json=audit_data)

        # 1. Verificar estado de la respuesta
        assert response.status_code == 202

        response_data = response.json()

        # 2. Verificar que el estado es PENDING
        assert response_data["status"] == AuditStatus.PENDING.value
        assert "id" in response_data

        audit_id = response_data["id"]

        # 3. Verificar que la tarea de Celery fue llamada
        mock_delay.assert_called_once_with(audit_id)


def test_get_audits_list(client: TestClient):
    """
    Verifica que se puede obtener una lista de auditorías.
    """
    response = client.get("/api/v1/audits/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_create_audit_respects_requested_language(client: TestClient):
    response = client.post(
        "/api/v1/audits/",
        json={
            "url": "https://example.com",
            "language": "es",
        },
    )
    assert response.status_code == 202
    assert response.json()["language"] == "es"


def test_create_audit_defaults_language_to_en(client: TestClient):
    response = client.post(
        "/api/v1/audits/",
        json={
            "url": "https://example.org",
        },
    )
    assert response.status_code == 202
    assert response.json()["language"] == "en"


def test_create_audit_ignores_odoo_delivery_preferences(client: TestClient):
    response = client.post(
        "/api/v1/audits/",
        json={
            "url": "https://example-intake.org",
            "add_articles": True,
            "article_count": 4,
            "improve_ecommerce_fixes": True,
        },
    )
    assert response.status_code == 202
    payload = response.json()
    assert payload["intake_profile"] is None


def test_create_audit_returns_503_when_database_is_unavailable(client: TestClient):
    with patch(
        "app.api.routes.audits.AuditService.create_audit",
        side_effect=OperationalError(
            "SELECT 1",
            {},
            Exception("connection to server timed out"),
        ),
    ):
        response = client.post(
            "/api/v1/audits/",
            json={
                "url": "https://example-db-timeout.com",
            },
        )

    assert response.status_code == 503
    assert response.json()["detail"] == {
        "error_code": "db_unavailable",
        "action": "create_audit",
        "message": "Database is temporarily unavailable. Retry in a few seconds.",
    }


def test_configure_chat_updates_language_when_provided(client: TestClient):
    create_response = client.post(
        "/api/v1/audits/",
        json={
            "url": "https://example.net",
            "language": "es",
        },
    )
    assert create_response.status_code == 202
    audit_id = create_response.json()["id"]

    with patch("app.api.routes.audits.run_audit_task.delay") as mock_delay:
        mock_delay.return_value = SimpleNamespace(id="chat-config-task-id")

        config_response = client.post(
            "/api/v1/audits/chat/config",
            json={"audit_id": audit_id, "language": "pt"},
        )

    assert config_response.status_code == 202
    detail_response = client.get(f"/api/v1/audits/{audit_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["language"] == "pt"


def test_configure_chat_preserves_language_when_omitted(client: TestClient):
    create_response = client.post(
        "/api/v1/audits/",
        json={
            "url": "https://example.edu",
            "language": "es",
        },
    )
    assert create_response.status_code == 202
    audit_id = create_response.json()["id"]

    with patch("app.api.routes.audits.run_audit_task.delay") as mock_delay:
        mock_delay.return_value = SimpleNamespace(id="chat-config-task-id-2")

        config_response = client.post(
            "/api/v1/audits/chat/config",
            json={"audit_id": audit_id, "market": "ar"},
        )

    assert config_response.status_code == 202
    detail_response = client.get(f"/api/v1/audits/{audit_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["language"] == "es"


def test_configure_chat_ignores_odoo_delivery_preferences_but_keeps_existing_profile(
    client: TestClient, db_session
):
    create_response = client.post(
        "/api/v1/audits/",
        json={
            "url": "https://example-chat-intake.com",
        },
    )
    assert create_response.status_code == 202
    audit_id = create_response.json()["id"]

    audit = db_session.query(Audit).filter(Audit.id == audit_id).first()
    audit.intake_profile = {
        "add_articles": True,
        "article_count": 5,
        "improve_ecommerce_fixes": True,
    }
    db_session.commit()

    with patch("app.api.routes.audits.run_audit_task.delay") as mock_delay:
        mock_delay.return_value = SimpleNamespace(id="chat-config-intake-task-id")

        config_response = client.post(
            "/api/v1/audits/chat/config",
            json={
                "audit_id": audit_id,
                "add_articles": True,
                "article_count": 5,
                "improve_ecommerce_fixes": True,
            },
        )

    assert config_response.status_code == 202
    detail_response = client.get(f"/api/v1/audits/{audit_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["intake_profile"] == {
        "add_articles": True,
        "article_count": 5,
        "improve_ecommerce_fixes": True,
    }


def test_get_audit_ignores_stale_cached_overview_snapshot(
    client: TestClient, db_session, monkeypatch
):
    audit = Audit(
        url="https://example-stale-overview.com",
        domain="example-stale-overview.com",
        status=AuditStatus.PENDING,
        user_id="test-user",
        user_email="test@example.com",
        language="es",
    )
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)

    monkeypatch.setattr(
        AuditService,
        "get_cached_overview_payload",
        staticmethod(
            lambda _audit_id: {
                "id": audit.id,
                "created_at": "2000-01-01T00:00:00Z",
                "language": "pt",
                "intake_profile": {"add_articles": True, "article_count": 9},
                "owner_user_id": "test-user",
                "owner_email": "test@example.com",
            }
        ),
    )

    response = client.get(f"/api/v1/audits/{audit.id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["language"] == "es"
    assert payload["intake_profile"] is None


def test_configure_chat_dispatch_failure_marks_audit_failed_but_keeps_config(
    setup_test_db, monkeypatch
):
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=setup_test_db
    )
    session = TestingSessionLocal()
    try:
        audit = Audit(
            url="https://example-chat-dispatch-failure.com",
            domain="example-chat-dispatch-failure.com",
            status=AuditStatus.PENDING,
            user_id="test-user",
            user_email="test@example.com",
            language="pt",
            market="ar",
        )
        session.add(audit)
        session.commit()
        session.refresh(audit)

        from app.api.routes.audits import (
            _dispatch_audit_after_chat_config,
            run_audit_task,
        )

        monkeypatch.setattr(
            "app.api.routes.audits.SessionLocal",
            TestingSessionLocal,
        )
        monkeypatch.setattr(
            run_audit_task,
            "delay",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                RuntimeError("broker unavailable")
            ),
        )

        _dispatch_audit_after_chat_config(audit.id)

        session.expire_all()
        stored_audit = session.query(Audit).filter(Audit.id == audit.id).first()
        assert stored_audit is not None
        assert stored_audit.language == "pt"
        assert stored_audit.market == "ar"
        assert stored_audit.status == AuditStatus.FAILED
        assert (
            stored_audit.error_message
            == "Background worker unavailable. Try again shortly."
        )
        diagnostics = stored_audit.runtime_diagnostics or []
        assert any(item.get("code") == "worker_unavailable" for item in diagnostics)
    finally:
        session.close()


def test_download_pdf_url_rejects_non_completed_audit(client: TestClient):
    create_response = client.post(
        "/api/v1/audits/",
        json={
            "url": "https://example-download-check.com",
        },
    )
    assert create_response.status_code == 202
    audit_id = create_response.json()["id"]

    download_response = client.get(f"/api/v1/audits/{audit_id}/download-pdf-url")
    assert download_response.status_code == 400
    assert "aún no está listo" in download_response.json()["detail"]


def test_delete_audit_removes_competitors_without_fk_error(
    client: TestClient, db_session
):
    create_response = client.post(
        "/api/v1/audits/",
        json={
            "url": "https://example-delete-check.com",
        },
    )
    assert create_response.status_code == 202
    audit_id = int(create_response.json()["id"])

    db_session.add(
        Competitor(
            audit_id=audit_id,
            url="https://competitor.example.com",
            domain="competitor.example.com",
            geo_score=55.0,
        )
    )
    db_session.commit()

    delete_response = client.delete(f"/api/v1/audits/{audit_id}")
    assert delete_response.status_code == 204

    detail_response = client.get(f"/api/v1/audits/{audit_id}")
    assert detail_response.status_code == 404

    competitors_remaining = (
        db_session.query(Competitor).filter(Competitor.audit_id == audit_id).count()
    )
    assert competitors_remaining == 0


def test_generate_pdf_returns_202_and_exposes_pdf_status(
    client: TestClient, db_session, monkeypatch
):
    audit = Audit(
        url="https://example-pdf-job-status.com",
        domain="example-pdf-job-status.com",
        status=AuditStatus.COMPLETED,
        user_id="test-user",
        user_email="test@example.com",
    )
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)
    monkeypatch.setattr(settings, "ENABLE_PAGESPEED", False, raising=False)
    monkeypatch.setattr(settings, "GOOGLE_PAGESPEED_API_KEY", None, raising=False)

    with patch("app.workers.tasks.run_pdf_generation_job_task.delay") as mock_delay:
        mock_delay.return_value = SimpleNamespace(id="pdf-job-task-id")

        response = client.post(f"/api/v1/audits/{audit.id}/generate-pdf")

    assert response.status_code == 202
    payload = response.json()
    assert payload["audit_id"] == audit.id
    assert payload["status"] == "queued"
    assert payload["download_ready"] is False
    assert payload["job_id"] is not None
    assert payload["retry_after_seconds"] == 3

    status_response = client.get(f"/api/v1/audits/{audit.id}/pdf-status")
    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["status"] == "queued"
    assert status_payload["job_id"] == payload["job_id"]


def test_generate_pdf_dispatch_failure_marks_job_failed_after_response(
    setup_test_db, monkeypatch
):
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=setup_test_db
    )
    session = TestingSessionLocal()
    try:
        audit = Audit(
            url="https://example-pdf-dispatch-failure.com",
            domain="example-pdf-dispatch-failure.com",
            status=AuditStatus.COMPLETED,
            user_id="test-user",
            user_email="test@example.com",
        )
        session.add(audit)
        session.commit()
        session.refresh(audit)
        monkeypatch.setattr(settings, "ENABLE_PAGESPEED", False, raising=False)
        monkeypatch.setattr(settings, "GOOGLE_PAGESPEED_API_KEY", None, raising=False)

        job = PDFJobService.queue_job(
            session,
            audit_id=audit.id,
            requested_by_user_id="test-user",
            force_pagespeed_refresh=False,
            force_report_refresh=False,
            force_external_intel_refresh=False,
        )
        from app.api.routes.audits import _dispatch_pdf_job_after_response
        from app.workers.tasks import run_pdf_generation_job_task

        monkeypatch.setattr(
            "app.api.routes.audits.SessionLocal",
            TestingSessionLocal,
        )
        calls = {"count": 0}

        def _fail_pdf_delay(*_args, **_kwargs):
            calls["count"] += 1
            raise RuntimeError("broker unavailable")

        monkeypatch.setattr(run_pdf_generation_job_task, "delay", _fail_pdf_delay)

        _dispatch_pdf_job_after_response(audit.id, job.id)

        session.expire_all()
        job = (
            session.query(AuditPdfJob).filter(AuditPdfJob.audit_id == audit.id).first()
        )
        assert calls["count"] >= 1
        assert job is not None
        assert job.status == "failed"
        assert job.error_code == "worker_unavailable"
    finally:
        session.close()


def test_generate_pdf_pagespeed_dispatch_failure_fails_waiting_pdf_job(
    setup_test_db, monkeypatch
):
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=setup_test_db
    )
    session = TestingSessionLocal()
    try:
        audit = Audit(
            url="https://example-pagespeed-dispatch-failure.com",
            domain="example-pagespeed-dispatch-failure.com",
            status=AuditStatus.COMPLETED,
            user_id="test-user",
            user_email="test@example.com",
        )
        session.add(audit)
        session.commit()
        session.refresh(audit)
        monkeypatch.setattr(settings, "ENABLE_PAGESPEED", True, raising=False)
        monkeypatch.setattr(
            settings, "GOOGLE_PAGESPEED_API_KEY", "test-pagespeed-key", raising=False
        )

        pagespeed_job = PageSpeedJobService.queue_job(
            session,
            audit=audit,
            requested_by_user_id="test-user",
            strategy="both",
            force_refresh=False,
        )
        pdf_job = PDFJobService.queue_job(
            session,
            audit_id=audit.id,
            requested_by_user_id="test-user",
            force_pagespeed_refresh=True,
            force_report_refresh=False,
            force_external_intel_refresh=False,
        )
        pdf_job = PDFJobService.mark_job_waiting(
            session,
            pdf_job,
            waiting_on="pagespeed",
            dependency_job_id=pagespeed_job.id,
        )

        from app.api.routes.audits import _dispatch_pagespeed_job_after_response
        from app.workers.tasks import (
            run_pagespeed_generation_job_task,
            run_pdf_generation_job_task,
        )

        monkeypatch.setattr(
            "app.api.routes.audits.SessionLocal",
            TestingSessionLocal,
        )
        calls = {"pagespeed": 0, "pdf": 0}

        def _fail_pagespeed_delay(*_args, **_kwargs):
            calls["pagespeed"] += 1
            raise RuntimeError("broker unavailable")

        def _record_pdf_delay(*_args, **_kwargs):
            calls["pdf"] += 1
            return SimpleNamespace(id="unexpected-pdf-dispatch")

        monkeypatch.setattr(
            run_pagespeed_generation_job_task, "delay", _fail_pagespeed_delay
        )
        monkeypatch.setattr(run_pdf_generation_job_task, "delay", _record_pdf_delay)

        _dispatch_pagespeed_job_after_response(audit.id, pagespeed_job.id)

        session.expire_all()
        pagespeed_job = (
            session.query(AuditPageSpeedJob)
            .filter(AuditPageSpeedJob.audit_id == audit.id)
            .first()
        )
        pdf_job = (
            session.query(AuditPdfJob).filter(AuditPdfJob.audit_id == audit.id).first()
        )
        assert calls["pagespeed"] >= 1
        assert pagespeed_job is not None
        assert pagespeed_job.status == "failed"
        assert pagespeed_job.error_code == "worker_unavailable"
        assert pdf_job is not None
        assert pdf_job.status == "failed"
        assert pdf_job.error_code == "worker_unavailable"
        assert calls["pdf"] == 0
    finally:
        session.close()


def test_artifact_status_endpoints_use_matching_cached_snapshot_without_rebuild(
    client: TestClient, db_session, monkeypatch
):
    audit = Audit(
        url="https://example-artifact-cache-hit.com",
        domain="example-artifact-cache-hit.com",
        status=AuditStatus.COMPLETED,
        user_id="test-user",
        user_email="test@example.com",
        pagespeed_data={"desktop": {"score": 0.91}},
    )
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)

    pagespeed_job = AuditPageSpeedJob(
        id=11,
        audit_id=audit.id,
        status="running",
        warnings=["PageSpeed still refreshing."],
    )
    pdf_job = AuditPdfJob(
        id=19,
        audit_id=audit.id,
        status="waiting",
        waiting_on="pagespeed",
        dependency_job_id=11,
    )
    pdf_report = Report(
        id=101,
        audit_id=audit.id,
        report_type="PDF",
        file_path=f"supabase://audits/{audit.id}/report.pdf",
    )
    snapshot = AuditService.build_artifact_payload(
        audit,
        pagespeed_job=pagespeed_job,
        pdf_job=pdf_job,
        pdf_report=pdf_report,
    )

    monkeypatch.setattr(
        AuditService,
        "get_cached_artifact_payload",
        staticmethod(lambda _audit_id: snapshot),
    )
    monkeypatch.setattr(
        AuditService,
        "rebuild_artifact_payload",
        staticmethod(
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError(
                    "rebuild_artifact_payload should not run for a matching cache hit"
                )
            )
        ),
    )

    pdf_response = client.get(f"/api/v1/audits/{audit.id}/pdf-status")
    pagespeed_response = client.get(f"/api/v1/audits/{audit.id}/pagespeed-status")
    artifacts_response = client.get(f"/api/v1/audits/{audit.id}/artifacts-status")

    assert pdf_response.status_code == 200
    assert pdf_response.json()["status"] == "waiting"
    assert pdf_response.json()["waiting_on"] == "pagespeed"

    assert pagespeed_response.status_code == 200
    assert pagespeed_response.json()["status"] == "running"
    assert pagespeed_response.json()["job_id"] == 11

    assert artifacts_response.status_code == 200
    artifacts_payload = artifacts_response.json()
    assert artifacts_payload["pdf_status"] == "waiting"
    assert artifacts_payload["pagespeed_status"] == "running"
    assert artifacts_payload["pdf_report_id"] == 101


def test_build_artifact_payload_normalizes_mixed_datetime_timezones():
    audit = Audit(
        id=74,
        url="https://example-artifact-datetime.com",
        domain="example-artifact-datetime.com",
        status=AuditStatus.COMPLETED,
        user_id="test-user",
        user_email="test@example.com",
    )
    pagespeed_job = AuditPageSpeedJob(
        id=12,
        audit_id=74,
        status="completed",
    )
    pagespeed_job.started_at = datetime(2026, 3, 11, 19, 56, tzinfo=timezone.utc)
    pagespeed_job.completed_at = datetime(2026, 3, 11, 19, 57, tzinfo=timezone.utc)
    pagespeed_job.updated_at = datetime(2026, 3, 11, 19, 57, tzinfo=timezone.utc)

    pdf_job = AuditPdfJob(
        id=20,
        audit_id=74,
        status="completed",
    )
    pdf_job.started_at = datetime(2026, 3, 11, 19, 58, tzinfo=timezone.utc)
    pdf_job.completed_at = datetime(2026, 3, 11, 19, 59, tzinfo=timezone.utc)
    pdf_job.updated_at = datetime(2026, 3, 11, 19, 59, tzinfo=timezone.utc)

    pdf_report = Report(
        id=102,
        audit_id=74,
        report_type="PDF",
        file_path="supabase://audits/74/report.pdf",
    )
    pdf_report.created_at = datetime(2026, 3, 11, 20, 0)

    payload = AuditService.build_artifact_payload(
        audit,
        pagespeed_job=pagespeed_job,
        pdf_job=pdf_job,
        pdf_report=pdf_report,
    )

    assert payload["pagespeed_started_at"] == "2026-03-11T19:56:00Z"
    assert payload["pagespeed_completed_at"] == "2026-03-11T19:57:00Z"
    assert payload["pdf_started_at"] == "2026-03-11T19:58:00Z"
    assert payload["pdf_completed_at"] == "2026-03-11T19:59:00Z"
    assert payload["updated_at"] == "2026-03-11T20:00:00Z"


def test_artifact_status_rebuilds_snapshot_on_cache_miss(
    client: TestClient, db_session, monkeypatch
):
    audit = Audit(
        url="https://example-artifact-cache-miss.com",
        domain="example-artifact-cache-miss.com",
        status=AuditStatus.COMPLETED,
        user_id="test-user",
        user_email="test@example.com",
        pagespeed_data={"desktop": {"score": 0.84}},
    )
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)

    db_session.add(
        AuditPageSpeedJob(
            audit_id=audit.id,
            status="queued",
            warnings=["Refresh queued"],
        )
    )
    db_session.add(
        Report(
            audit_id=audit.id,
            report_type="PDF",
            file_path="supabase://audits/cache-miss/report.pdf",
        )
    )
    db_session.commit()

    captured_cache = {}
    monkeypatch.setattr(cache, "enabled", True, raising=False)
    monkeypatch.setattr(cache, "get", lambda key: None, raising=False)

    def _capture_set(key, value, ttl=300):
        captured_cache["key"] = key
        captured_cache["value"] = value
        captured_cache["ttl"] = ttl

    monkeypatch.setattr(cache, "set", _capture_set, raising=False)

    response = client.get(f"/api/v1/audits/{audit.id}/artifacts-status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["pagespeed_status"] == "queued"
    assert payload["pdf_status"] == "completed"
    assert captured_cache["key"] == AuditService.artifact_snapshot_key(audit.id)
    assert captured_cache["value"]["audit_id"] == audit.id
    assert captured_cache["value"]["owner_user_id"] == "test-user"


def test_artifact_status_authorizes_from_cached_snapshot(
    client: TestClient, db_session, monkeypatch
):
    audit = Audit(
        url="https://example-artifact-cache-auth.com",
        domain="example-artifact-cache-auth.com",
        status=AuditStatus.COMPLETED,
        user_id="test-user",
        user_email="test@example.com",
    )
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)

    snapshot = {
        "audit_id": audit.id,
        "audit_created_at": AuditService._serialize_artifact_datetime(audit.created_at),
        "owner_user_id": "different-user",
        "owner_email": "different@example.com",
        "pagespeed_status": "idle",
        "pagespeed_job_id": None,
        "pagespeed_available": False,
        "pagespeed_warnings": [],
        "pagespeed_error": None,
        "pagespeed_started_at": None,
        "pagespeed_completed_at": None,
        "pagespeed_retry_after_seconds": 0,
        "pagespeed_message": None,
        "pdf_status": "idle",
        "pdf_job_id": None,
        "pdf_available": False,
        "pdf_report_id": None,
        "pdf_waiting_on": None,
        "pdf_dependency_job_id": None,
        "pdf_warnings": [],
        "pdf_error": None,
        "pdf_started_at": None,
        "pdf_completed_at": None,
        "pdf_retry_after_seconds": 0,
        "pdf_message": None,
        "updated_at": "2026-03-11T00:00:00Z",
    }

    monkeypatch.setattr(
        AuditService,
        "get_cached_artifact_payload",
        staticmethod(lambda _audit_id: snapshot),
    )
    monkeypatch.setattr(
        AuditService,
        "rebuild_artifact_payload",
        staticmethod(
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError(
                    "rebuild_artifact_payload should not run for a matching cache hit"
                )
            )
        ),
    )

    response = client.get(f"/api/v1/audits/{audit.id}/artifacts-status")
    assert response.status_code == 403


def test_artifact_status_keeps_running_snapshot_in_cache(
    client: TestClient, db_session, monkeypatch
):
    monkeypatch.setattr(settings, "BROKER_DISPATCH_GRACE_SECONDS", 1, raising=False)
    audit = Audit(
        url="https://example-artifact-running-cache.com",
        domain="example-artifact-running-cache.com",
        status=AuditStatus.COMPLETED,
        user_id="test-user",
        user_email="test@example.com",
    )
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)

    snapshot = {
        "audit_id": audit.id,
        "audit_created_at": AuditService._serialize_artifact_datetime(audit.created_at),
        "owner_user_id": "test-user",
        "owner_email": "test@example.com",
        "pagespeed_status": "running",
        "pagespeed_job_id": 14,
        "pagespeed_available": False,
        "pagespeed_warnings": [],
        "pagespeed_error": None,
        "pagespeed_started_at": "2026-03-11T00:00:00Z",
        "pagespeed_completed_at": None,
        "pagespeed_retry_after_seconds": 3,
        "pagespeed_message": None,
        "pdf_status": "waiting",
        "pdf_job_id": 9,
        "pdf_available": False,
        "pdf_report_id": None,
        "pdf_waiting_on": "pagespeed",
        "pdf_dependency_job_id": 14,
        "pdf_warnings": [],
        "pdf_error": None,
        "pdf_started_at": None,
        "pdf_completed_at": None,
        "pdf_retry_after_seconds": 3,
        "pdf_message": None,
        "updated_at": "2026-03-11T00:00:00Z",
    }

    monkeypatch.setattr(
        AuditService,
        "get_cached_artifact_payload",
        staticmethod(lambda _audit_id: snapshot),
    )
    monkeypatch.setattr(
        AuditService,
        "rebuild_artifact_payload",
        staticmethod(
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError(
                    "rebuild_artifact_payload should not run for a matching cache hit"
                )
            )
        ),
    )

    response = client.get(f"/api/v1/audits/{audit.id}/artifacts-status")

    assert response.status_code == 200
    assert response.json()["pagespeed_status"] == "running"
    assert response.json()["pdf_status"] == "waiting"


def test_generate_pdf_waits_for_active_pagespeed_without_duplicating_provider_work(
    client: TestClient, db_session, monkeypatch
):
    fresh_fetch_time = datetime.now(timezone.utc).isoformat()
    audit = Audit(
        url="https://example-pdf-waits-pagespeed.com",
        domain="example-pdf-waits-pagespeed.com",
        status=AuditStatus.COMPLETED,
        user_id="test-user",
        user_email="test@example.com",
        pagespeed_data={
            "mobile": {"metadata": {"fetch_time": fresh_fetch_time}},
            "desktop": {"metadata": {"fetch_time": fresh_fetch_time}},
        },
    )
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)
    monkeypatch.setattr(settings, "ENABLE_PAGESPEED", False, raising=False)
    monkeypatch.setattr(settings, "GOOGLE_PAGESPEED_API_KEY", None, raising=False)
    monkeypatch.setattr(settings, "ENABLE_PAGESPEED", True, raising=False)
    monkeypatch.setattr(
        settings, "GOOGLE_PAGESPEED_API_KEY", "test-pagespeed-key", raising=False
    )

    pagespeed_job = PageSpeedJobService.queue_job(
        db_session,
        audit=audit,
        requested_by_user_id="test-user",
        strategy="both",
        force_refresh=False,
    )

    with patch(
        "app.workers.tasks.run_pagespeed_generation_job_task.delay"
    ) as mock_pagespeed_delay, patch(
        "app.workers.tasks.run_pdf_generation_job_task.delay"
    ) as mock_pdf_delay:
        response = client.post(f"/api/v1/audits/{audit.id}/generate-pdf")

    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "waiting"
    assert payload["waiting_on"] == "pagespeed"
    assert payload["dependency_job_id"] == pagespeed_job.id
    mock_pagespeed_delay.assert_not_called()
    mock_pdf_delay.assert_not_called()

    status_response = client.get(f"/api/v1/audits/{audit.id}/pdf-status")
    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["status"] == "waiting"
    assert status_payload["waiting_on"] == "pagespeed"


def test_pdf_worker_rechecks_active_pagespeed_before_starting_pipeline(
    db_session, monkeypatch
):
    audit = Audit(
        url="https://example-pdf-worker-waits-pagespeed.com",
        domain="example-pdf-worker-waits-pagespeed.com",
        status=AuditStatus.COMPLETED,
        user_id="test-user",
        user_email="test@example.com",
    )
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)

    pagespeed_job = PageSpeedJobService.queue_job(
        db_session,
        audit=audit,
        requested_by_user_id="test-user",
        strategy="both",
        force_refresh=False,
    )
    pdf_job = PDFJobService.queue_job(
        db_session,
        audit_id=audit.id,
        requested_by_user_id="test-user",
        force_pagespeed_refresh=False,
        force_report_refresh=False,
        force_external_intel_refresh=False,
    )

    monkeypatch.setattr(settings, "DEBUG", True, raising=False)
    monkeypatch.setattr(cache, "enabled", False, raising=False)
    monkeypatch.setattr(cache, "redis_client", None, raising=False)

    with patch("app.workers.tasks.get_db_session") as mock_get_db, patch(
        "app.services.pdf_service.PDFService.generate_pdf_with_complete_context"
    ) as mock_generate_pdf:
        mock_get_db.return_value.__enter__.return_value = db_session
        from app.workers.tasks import run_pdf_generation_job_task

        result = run_pdf_generation_job_task.run(pdf_job.id)

    assert result["status"] == "waiting"
    db_session.refresh(pdf_job)
    assert pdf_job.status == "waiting"
    assert pdf_job.waiting_on == "pagespeed"
    assert pdf_job.dependency_job_id == pagespeed_job.id
    mock_generate_pdf.assert_not_called()


def test_pdf_job_execution_persists_runtime_warnings_in_overview_and_diagnostics(
    client: TestClient, db_session, monkeypatch
):
    audit = Audit(
        url="https://example-pdf-warnings.com",
        domain="example-pdf-warnings.com",
        status=AuditStatus.COMPLETED,
        user_id="test-user",
        user_email="test@example.com",
    )
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)

    job = PDFJobService.queue_job(
        db_session,
        audit_id=audit.id,
        requested_by_user_id="test-user",
        force_pagespeed_refresh=False,
        force_report_refresh=False,
        force_external_intel_refresh=False,
    )

    async def _fake_generate_pdf_with_complete_context(*args, **kwargs):
        return {
            "pdf_path": f"supabase://audits/{audit.id}/report.pdf",
            "file_size": 128,
            "report_cache_hit": False,
            "report_regenerated": True,
            "report_persisted": True,
            "generation_mode": "report_regenerated",
            "external_intel_refreshed": False,
            "external_intel_refresh_reason": "not_needed",
            "missing_context": [],
            "generation_warnings": [
                "PageSpeed data could not be refreshed in time for this PDF run."
            ],
        }

    monkeypatch.setattr(settings, "DEBUG", True, raising=False)
    monkeypatch.setattr(cache, "enabled", False, raising=False)
    monkeypatch.setattr(cache, "redis_client", None, raising=False)

    with patch("app.workers.tasks.get_db_session") as mock_get_db, patch(
        "app.services.pdf_service.PDFService.generate_pdf_with_complete_context",
        side_effect=_fake_generate_pdf_with_complete_context,
    ):
        mock_get_db.return_value.__enter__.return_value = db_session
        from app.workers.tasks import run_pdf_generation_job_task

        result = run_pdf_generation_job_task.run(job.id)

    assert result["status"] == "completed"
    db_session.refresh(job)
    assert job.status == "completed"
    report = db_session.query(Report).filter(Report.audit_id == audit.id).first()
    assert report is not None
    assert report.file_path == f"supabase://audits/{audit.id}/report.pdf"

    overview_response = client.get(f"/api/v1/audits/{audit.id}/overview")
    assert overview_response.status_code == 200
    diagnostics_summary = overview_response.json()["diagnostics_summary"]
    assert diagnostics_summary
    assert diagnostics_summary[0]["source"] == "pdf"
    assert diagnostics_summary[0]["severity"] == "warning"
    assert "PageSpeed data could not be refreshed" in diagnostics_summary[0]["message"]

    diagnostics_response = client.get(f"/api/v1/audits/{audit.id}/diagnostics")
    assert diagnostics_response.status_code == 200
    diagnostics = diagnostics_response.json()["diagnostics"]
    assert diagnostics[0]["code"] == "pdf_generation_warning_1"


def test_get_audit_and_summary_return_slim_shell_and_keep_heavy_aliases(
    client: TestClient, db_session, monkeypatch
):
    monkeypatch.setattr(cache, "enabled", False, raising=False)
    audit = Audit(
        url="https://example-audit-shell.com",
        domain="example-audit-shell.com",
        status=AuditStatus.COMPLETED,
        user_id="test-user",
        user_email="test@example.com",
        target_audit={"content": {"h1": "Hidden from shell"}},
        external_intelligence={
            "status": "ok",
            "category": "Education",
            "market": "AR",
            "warning_code": "AGENT1_CORE_FILTER_DEGRADED",
            "warning_message": "Used fallback query selection.",
        },
        competitor_audits=[{"url": "https://competitor.example.com"}],
        fix_plan=[{"issue_code": "TITLE_MISSING", "priority": "HIGH"}],
        report_markdown="# Report",
        pagespeed_data={"desktop": {"score": 0.91}},
        category="Education",
        market="AR",
    )
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)

    shell_response = client.get(f"/api/v1/audits/{audit.id}")
    summary_response = client.get(f"/api/v1/audits/{audit.id}/summary")
    issues_response = client.get(f"/api/v1/audits/{audit.id}/issues")
    fix_plan_response = client.get(f"/api/v1/audits/{audit.id}/fix_plan")
    report_response = client.get(f"/api/v1/audits/{audit.id}/report")

    assert shell_response.status_code == 200
    assert summary_response.status_code == 200
    assert issues_response.status_code == 200
    assert fix_plan_response.status_code == 200
    assert report_response.status_code == 200

    for payload in (shell_response.json(), summary_response.json()):
        assert "target_audit" not in payload
        assert "competitor_audits" not in payload
        assert "fix_plan" not in payload
        assert "report_markdown" not in payload
        assert "pagespeed_data" not in payload
        assert payload["category"] == "Education"
        assert payload["market"] == "AR"
        assert payload["fix_plan_count"] == 1
        assert payload["report_ready"] is True
        assert payload["pagespeed_available"] is True
        assert payload["external_intelligence"]["status"] == "ok"
        assert payload["external_intelligence"]["warning_code"] == (
            "AGENT1_CORE_FILTER_DEGRADED"
        )
        assert "category" not in payload["external_intelligence"]

    assert issues_response.json()["fix_plan"][0]["issue_code"] == "TITLE_MISSING"
    assert fix_plan_response.json() == issues_response.json()
    assert report_response.json()["report_markdown"] == "# Report"


def test_summary_and_overview_use_cached_overview_snapshot(
    client: TestClient, db_session, monkeypatch
):
    audit = Audit(
        url="https://example-overview-cache.com",
        domain="example-overview-cache.com",
        status=AuditStatus.COMPLETED,
        user_id="test-user",
        user_email="test@example.com",
        language="en",
    )
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)

    snapshot = {
        "id": audit.id,
        "url": "https://example-overview-cache.com",
        "domain": "example-overview-cache.com",
        "status": "completed",
        "progress": 100,
        "created_at": AuditService._serialize_artifact_datetime(audit.created_at),
        "started_at": "2026-03-11T00:00:10Z",
        "completed_at": "2026-03-11T00:03:10Z",
        "geo_score": 87.5,
        "total_pages": 12,
        "critical_issues": 1,
        "high_issues": 2,
        "medium_issues": 3,
        "source": "manual",
        "language": "en",
        "category": "Software",
        "market": "US",
        "intake_profile": {"add_articles": True, "article_count": 3},
        "diagnostics_summary": [],
        "odoo_connection_id": None,
        "error_message": None,
        "competitor_count": 2,
        "fix_plan_count": 4,
        "report_ready": True,
        "pagespeed_available": True,
        "pagespeed_status": "completed",
        "pagespeed_warnings": [],
        "pdf_available": True,
        "pdf_status": "completed",
        "pdf_warnings": [],
        "external_intelligence": {"status": "ok", "warning_code": None},
        "owner_user_id": "test-user",
        "owner_email": "test@example.com",
    }

    monkeypatch.setattr(
        AuditService,
        "get_cached_overview_payload",
        staticmethod(lambda _audit_id: snapshot),
    )
    monkeypatch.setattr(
        AuditService,
        "rebuild_overview_payload",
        staticmethod(
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError(
                    "rebuild_overview_payload should not run for a matching cache hit"
                )
            )
        ),
    )

    summary_response = client.get(f"/api/v1/audits/{audit.id}/summary")
    overview_response = client.get(f"/api/v1/audits/{audit.id}/overview")

    assert summary_response.status_code == 200
    assert summary_response.json()["id"] == audit.id
    assert summary_response.json()["fix_plan_count"] == 4
    assert overview_response.status_code == 200
    assert overview_response.json()["domain"] == "example-overview-cache.com"


def test_pdf_job_failure_persists_sanitized_exception_detail(
    setup_test_db, monkeypatch
):
    testing_session_local = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=setup_test_db,
    )
    session = testing_session_local()
    try:
        audit = Audit(
            url="https://example-pdf-failure.com",
            domain="example-pdf-failure.com",
            status=AuditStatus.COMPLETED,
            user_id="test-user",
            user_email="test@example.com",
        )
        session.add(audit)
        session.commit()
        session.refresh(audit)
        audit_id = audit.id

        job = PDFJobService.queue_job(
            session,
            audit_id=audit_id,
            requested_by_user_id="test-user",
            force_pagespeed_refresh=False,
            force_report_refresh=False,
            force_external_intel_refresh=False,
        )
        job_id = job.id

        async def _raise_renderer_failure(*args, **kwargs):
            raise RuntimeError("renderer exploded")

        monkeypatch.setattr(settings, "DEBUG", True, raising=False)
        monkeypatch.setattr(cache, "enabled", False, raising=False)
        monkeypatch.setattr(cache, "redis_client", None, raising=False)

        with patch("app.workers.tasks.get_db_session") as mock_get_db, patch(
            "app.services.pdf_service.PDFService.generate_pdf_with_complete_context",
            side_effect=_raise_renderer_failure,
        ):
            mock_get_db.return_value.__enter__.return_value = session
            from app.workers.tasks import run_pdf_generation_job_task

            result = run_pdf_generation_job_task.run(job_id)

        assert result["job_id"] == job_id
        session.expire_all()
        stored_job = session.query(AuditPdfJob).filter(AuditPdfJob.id == job_id).first()
        assert stored_job is not None
        assert stored_job.status == "failed"
        stored_audit = session.query(Audit).filter(Audit.id == audit_id).first()
        assert stored_audit is not None
        diagnostics = stored_audit.runtime_diagnostics or []
        assert diagnostics
        assert diagnostics[-1]["technical_detail"] == "RuntimeError"
    finally:
        session.close()


def test_run_pagespeed_returns_202_and_exposes_status(client: TestClient, db_session):
    audit = Audit(
        url="https://example-pagespeed-status.com",
        domain="example-pagespeed-status.com",
        status=AuditStatus.COMPLETED,
        user_id="test-user",
        user_email="test@example.com",
    )
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)

    with patch(
        "app.workers.tasks.run_pagespeed_generation_job_task.delay"
    ) as mock_delay:
        mock_delay.return_value = SimpleNamespace(id="pagespeed-job-task-id")

        response = client.post(
            f"/api/v1/audits/{audit.id}/run-pagespeed?strategy=desktop"
        )

    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "queued"
    assert payload["job_id"] is not None

    status_response = client.get(f"/api/v1/audits/{audit.id}/pagespeed-status")
    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["status"] == "queued"
    assert status_payload["job_id"] == payload["job_id"]


def test_stale_queued_pdf_job_is_reconciled_on_status_lookup(
    client: TestClient, db_session, monkeypatch
):
    audit = Audit(
        url="https://example-stale-pdf-job.com",
        domain="example-stale-pdf-job.com",
        status=AuditStatus.COMPLETED,
        user_id="test-user",
        user_email="test@example.com",
    )
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)
    monkeypatch.setattr(settings, "BROKER_DISPATCH_GRACE_SECONDS", 1, raising=False)

    stale_job = AuditPdfJob(
        audit_id=audit.id,
        status="queued",
        celery_task_id=None,
        updated_at=datetime.now(timezone.utc) - timedelta(seconds=30),
    )
    db_session.add(stale_job)
    db_session.commit()

    response = client.get(f"/api/v1/audits/{audit.id}/pdf-status")

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    reconciled_job = (
        db_session.query(AuditPdfJob).filter(AuditPdfJob.audit_id == audit.id).first()
    )
    assert reconciled_job is not None
    assert reconciled_job.status == "failed"
    assert reconciled_job.error_code == "worker_unavailable"


def test_pdf_status_ignores_stale_cached_artifact_snapshot(
    client: TestClient, db_session, monkeypatch
):
    audit = Audit(
        url="https://example-stale-pdf-cache.com",
        domain="example-stale-pdf-cache.com",
        status=AuditStatus.COMPLETED,
        user_id="test-user",
        user_email="test@example.com",
    )
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)
    monkeypatch.setattr(settings, "BROKER_DISPATCH_GRACE_SECONDS", 1, raising=False)

    stale_job = AuditPdfJob(
        audit_id=audit.id,
        status="queued",
        celery_task_id=None,
        updated_at=datetime.now(timezone.utc) - timedelta(seconds=30),
    )
    db_session.add(stale_job)
    db_session.commit()

    monkeypatch.setattr(
        AuditService,
        "get_cached_artifact_payload",
        staticmethod(
            lambda _audit_id: {
                "audit_id": audit.id,
                "audit_created_at": "2000-01-01T00:00:00Z",
                "pdf_status": "completed",
                "pdf_available": True,
                "pdf_warnings": [],
                "pdf_retry_after_seconds": 0,
                "pagespeed_status": "idle",
                "pagespeed_available": False,
                "pagespeed_warnings": [],
                "pagespeed_retry_after_seconds": 0,
                "owner_user_id": "test-user",
                "owner_email": "test@example.com",
            }
        ),
    )

    response = client.get(f"/api/v1/audits/{audit.id}/pdf-status")

    assert response.status_code == 200
    assert response.json()["status"] == "failed"


def test_stale_queued_pagespeed_job_is_reconciled_on_status_lookup(
    client: TestClient, db_session, monkeypatch
):
    audit = Audit(
        url="https://example-stale-pagespeed-job.com",
        domain="example-stale-pagespeed-job.com",
        status=AuditStatus.COMPLETED,
        user_id="test-user",
        user_email="test@example.com",
    )
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)
    monkeypatch.setattr(settings, "BROKER_DISPATCH_GRACE_SECONDS", 1, raising=False)

    stale_job = AuditPageSpeedJob(
        audit_id=audit.id,
        status="queued",
        celery_task_id=None,
        updated_at=datetime.now(timezone.utc) - timedelta(seconds=30),
    )
    db_session.add(stale_job)
    db_session.commit()

    response = client.get(f"/api/v1/audits/{audit.id}/pagespeed-status")

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    reconciled_job = (
        db_session.query(AuditPageSpeedJob)
        .filter(AuditPageSpeedJob.audit_id == audit.id)
        .first()
    )
    assert reconciled_job is not None
    assert reconciled_job.status == "failed"
    assert reconciled_job.error_code == "worker_unavailable"


def test_pagespeed_job_provider_warning_persists_runtime_warning(
    client: TestClient, db_session, monkeypatch
):
    audit = Audit(
        url="https://example-pagespeed-provider-warning.com",
        domain="example-pagespeed-provider-warning.com",
        status=AuditStatus.COMPLETED,
        user_id="test-user",
        user_email="test@example.com",
    )
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)

    job = PageSpeedJobService.queue_job(
        db_session,
        audit=audit,
        requested_by_user_id="test-user",
        strategy="desktop",
        force_refresh=False,
    )

    async def _fake_analyze_url(*args, **kwargs):
        return {
            "error": "timeout",
            "public_message": "PageSpeed request timed out before a response was received.",
            "strategy": "desktop",
            "url": str(audit.url),
        }

    monkeypatch.setattr(settings, "DEBUG", True, raising=False)
    monkeypatch.setattr(cache, "enabled", False, raising=False)
    monkeypatch.setattr(cache, "redis_client", None, raising=False)

    with patch("app.workers.tasks.get_db_session") as mock_get_db, patch(
        "app.services.pagespeed_service.PageSpeedService.analyze_url",
        side_effect=_fake_analyze_url,
    ):
        mock_get_db.return_value.__enter__.return_value = db_session
        from app.workers.tasks import run_pagespeed_generation_job_task

        result = run_pagespeed_generation_job_task.run(job.id)

    assert result["status"] == "completed"
    db_session.refresh(job)
    assert job.status == "completed"
    assert job.warnings
    assert (
        job.warnings[0] == "Desktop PageSpeed unavailable: "
        "PageSpeed request timed out before a response was received."
    )

    diagnostics_response = client.get(f"/api/v1/audits/{audit.id}/diagnostics")
    assert diagnostics_response.status_code == 200
    diagnostics = diagnostics_response.json()["diagnostics"]
    assert diagnostics
    assert diagnostics[0]["source"] == "pagespeed"
    assert diagnostics[0]["severity"] == "warning"
    assert diagnostics[0]["code"] == "pagespeed_warning_1"
    assert (
        diagnostics[0]["message"] == "Desktop PageSpeed unavailable: "
        "PageSpeed request timed out before a response was received."
    )


def test_pagespeed_job_warnings_ignore_legacy_provider_message():
    warnings, successful_results = PageSpeedJobService.extract_provider_warnings(
        {
            "desktop": {
                "error": "timeout",
                "provider_message": "Traceback: upstream details should stay internal",
            }
        },
        strategy="desktop",
    )

    assert successful_results == {}
    assert warnings == [
        "Desktop PageSpeed unavailable: "
        "PageSpeed provider returned an error before any performance data was available."
    ]
