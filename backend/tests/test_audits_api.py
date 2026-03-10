"""
Tests para el API de Auditorías
"""

from unittest.mock import MagicMock, patch

from app.models import Audit, Competitor
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
        mock_task = MagicMock()
        mock_task.id = "test-task-id"
        mock_delay.return_value = mock_task

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
        mock_task = MagicMock()
        mock_task.id = "chat-config-task-id"
        mock_delay.return_value = mock_task

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
        mock_task = MagicMock()
        mock_task.id = "chat-config-task-id-2"
        mock_delay.return_value = mock_task

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
        mock_task = MagicMock()
        mock_task.id = "chat-config-intake-task-id"
        mock_delay.return_value = mock_task

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


def test_generate_pdf_persists_runtime_warnings_in_overview_and_diagnostics(
    client: TestClient, db_session
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

    with patch(
        "app.api.routes.audits._acquire_pdf_generation_lock",
        return_value=(True, "test-lock", "local"),
    ), patch(
        "app.services.pdf_service.PDFService.generate_pdf_with_complete_context",
        side_effect=_fake_generate_pdf_with_complete_context,
    ):
        response = client.post(
            f"/api/v1/audits/{audit.id}/generate-pdf",
            headers={"X-User-ID": "pdf-diagnostics-test"},
        )

    assert response.status_code == 200
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


def test_run_pagespeed_failure_persists_runtime_diagnostic(
    client: TestClient, db_session
):
    audit = Audit(
        url="https://example-pagespeed-failure.com",
        domain="example-pagespeed-failure.com",
        status=AuditStatus.COMPLETED,
        user_id="test-user",
        user_email="test@example.com",
    )
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)

    async def _fake_analyze_url(*args, **kwargs):
        raise RuntimeError("Connector is closed.")

    with patch(
        "app.services.pagespeed_service.PageSpeedService.analyze_url",
        side_effect=_fake_analyze_url,
    ):
        response = client.post(
            f"/api/v1/audits/{audit.id}/run-pagespeed?strategy=desktop"
        )

    assert response.status_code == 500
    diagnostics_response = client.get(f"/api/v1/audits/{audit.id}/diagnostics")
    assert diagnostics_response.status_code == 200
    diagnostics = diagnostics_response.json()["diagnostics"]
    assert diagnostics
    assert diagnostics[0]["source"] == "pagespeed"
    assert diagnostics[0]["severity"] == "error"
    assert diagnostics[0]["code"] == "pagespeed_failed"
    assert diagnostics[0]["technical_detail"] == "RuntimeError"
