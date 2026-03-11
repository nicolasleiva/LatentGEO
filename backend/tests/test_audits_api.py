"""
Tests para el API de Auditorías
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from app.core.config import settings
from app.models import Audit, AuditPageSpeedJob, AuditPdfJob, Competitor, Report
from app.services.cache_service import cache
from app.services.audit_service import AuditService
from app.services.pagespeed_job_service import PageSpeedJobService
from app.services.pdf_job_service import PDFJobService
from app.schemas import AuditStatus
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError


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

    assert config_response.status_code == 200
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

    assert config_response.status_code == 200
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

    assert config_response.status_code == 200
    detail_response = client.get(f"/api/v1/audits/{audit_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["intake_profile"] == {
        "add_articles": True,
        "article_count": 5,
        "improve_ecommerce_fixes": True,
    }


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


def test_artifact_status_endpoints_use_cached_snapshot_without_touching_db(
    client: TestClient, db_session, monkeypatch
):
    audit = Audit(
        id=73,
        url="https://example-artifact-cache-hit.com",
        domain="example-artifact-cache-hit.com",
        status=AuditStatus.COMPLETED,
        user_id="test-user",
        user_email="test@example.com",
        pagespeed_data={"desktop": {"score": 0.91}},
    )
    pagespeed_job = AuditPageSpeedJob(
        id=11,
        audit_id=73,
        status="running",
        warnings=["PageSpeed still refreshing."],
    )
    pdf_job = AuditPdfJob(
        id=19,
        audit_id=73,
        status="waiting",
        waiting_on="pagespeed",
        dependency_job_id=11,
    )
    pdf_report = Report(
        id=101,
        audit_id=73,
        report_type="PDF",
        file_path="supabase://audits/73/report.pdf",
    )
    snapshot = AuditService.build_artifact_payload(
        audit,
        pagespeed_job=pagespeed_job,
        pdf_job=pdf_job,
        pdf_report=pdf_report,
    )

    monkeypatch.setattr(cache, "enabled", True, raising=False)
    monkeypatch.setattr(cache, "get", lambda key: snapshot, raising=False)

    def _fail_query(*args, **kwargs):
        raise AssertionError("db.query should not run on artifact snapshot cache hit")

    monkeypatch.setattr(db_session, "query", _fail_query)

    pdf_response = client.get("/api/v1/audits/73/pdf-status")
    pagespeed_response = client.get("/api/v1/audits/73/pagespeed-status")
    artifacts_response = client.get("/api/v1/audits/73/artifacts-status")

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
    snapshot = {
        "audit_id": 88,
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

    monkeypatch.setattr(cache, "enabled", True, raising=False)
    monkeypatch.setattr(cache, "get", lambda key: snapshot, raising=False)

    def _fail_query(*args, **kwargs):
        raise AssertionError("db.query should not run when cached snapshot denies access")

    monkeypatch.setattr(db_session, "query", _fail_query)

    response = client.get("/api/v1/audits/88/artifacts-status")
    assert response.status_code == 403


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


def test_run_pagespeed_returns_202_and_exposes_status(
    client: TestClient, db_session
):
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

    with patch("app.workers.tasks.run_pagespeed_generation_job_task.delay") as mock_delay:
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
            "provider_message": "Lighthouse returned error: NO_FCP",
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
    assert "NO_FCP" in job.warnings[0]

    diagnostics_response = client.get(f"/api/v1/audits/{audit.id}/diagnostics")
    assert diagnostics_response.status_code == 200
    diagnostics = diagnostics_response.json()["diagnostics"]
    assert diagnostics
    assert diagnostics[0]["source"] == "pagespeed"
    assert diagnostics[0]["severity"] == "warning"
    assert diagnostics[0]["code"] == "pagespeed_warning_1"
    assert "NO_FCP" in diagnostics[0]["message"]
