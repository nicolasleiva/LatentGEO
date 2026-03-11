"""
Tests para los Celery Workers
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from app.core.config import settings
from app.models import Audit, AuditStatus
from app.workers.async_runtime import _worker_async_runtime, run_worker_coroutine
from app.workers.tasks import generate_pdf_task, run_audit_task, run_pagespeed_task
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session

# --- Test para run_audit_task ---


@patch("app.workers.tasks.PageSpeedJobService.queue_if_needed")
@patch("app.workers.tasks.AuditLocalService.run_local_audit", new_callable=AsyncMock)
@patch("app.services.pipeline_service.run_initial_audit", new_callable=AsyncMock)
def test_run_audit_task_success(
    mock_run_initial,
    mock_local_audit,
    mock_queue_pagespeed,
    db_session: Session,
    monkeypatch,
):
    """
    Verifica el camino exitoso de la tarea 'run_audit_task'.
    """
    # 1. Setup: Crear una auditoría en estado PENDING
    audit = Audit(
        url="https://success.com", status=AuditStatus.PENDING, domain="success.com"
    )
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)

    # Mock del resultado del pipeline
    mock_pipeline_result = {
        "report_markdown": "# Report",
        "fix_plan": [{"issue": "test"}],
        "target_audit": {"score": 90},
        "external_intelligence": {"is_ymyl": False},
        "search_results": {},
        "competitor_audits": [],
    }
    mock_run_initial.return_value = mock_pipeline_result
    mock_local_audit.return_value = {"url": "https://success.com", "status": 200}
    monkeypatch.setattr(settings, "ENABLE_PAGESPEED", True, raising=False)
    monkeypatch.setattr(
        settings, "GOOGLE_PAGESPEED_API_KEY", "test-pagespeed-key", raising=False
    )

    def _queue_pagespeed_side_effect(*args, **kwargs):
        queued_audit = kwargs["audit"]
        assert queued_audit.id == audit.id
        assert sa_inspect(queued_audit).persistent is True
        return SimpleNamespace(id=987)

    mock_queue_pagespeed.side_effect = _queue_pagespeed_side_effect

    # 2. Ejecutar la tarea
    # Usamos patch en get_db_session para que la tarea use la sesión de test
    with patch("app.workers.tasks.get_db_session") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = db_session
        run_audit_task.run(audit.id)

    # 3. Verificación
    db_session.refresh(audit)

    # Verificar que el estado es COMPLETED y el progreso 100
    assert audit.status == AuditStatus.COMPLETED
    assert audit.progress == 100

    # Verificar que los resultados se guardaron
    assert audit.report_markdown == "# Report"
    assert audit.fix_plan[0]["issue"] == "test"
    assert audit.target_audit["score"] == 90
    mock_queue_pagespeed.assert_called_once()


@patch("app.workers.tasks.AuditLocalService.run_local_audit", new_callable=AsyncMock)
@patch("app.services.pipeline_service.run_initial_audit", new_callable=AsyncMock)
def test_run_audit_task_failure(
    mock_run_initial, mock_local_audit, db_session: Session
):
    """
    Verifica el manejo de errores en la tarea 'run_audit_task'.
    """
    # 1. Setup
    audit = Audit(url="https://fail.com", status=AuditStatus.PENDING, domain="fail.com")
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)

    # Mock de un error en el pipeline
    mock_run_initial.side_effect = Exception("Pipeline exploded")
    mock_local_audit.return_value = {"url": "https://fail.com", "status": 200}

    # 2. Ejecutar la tarea
    with patch("app.workers.tasks.get_db_session") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = db_session
        with pytest.raises(Exception):
            run_audit_task.run(audit.id)

    # 3. Verificación
    db_session.refresh(audit)

    assert audit.status == AuditStatus.FAILED
    assert audit.error_message == "Pipeline exploded"


# --- Test para generate_pdf_task ---


@patch("app.workers.tasks.run_pdf_generation_job_task.run")
@patch("app.workers.tasks.PDFJobService.queue_job")
def test_generate_pdf_task(mock_queue_job, mock_run_job, db_session: Session):
    """
    Verifica que la tarea legacy delega al flujo canónico de job.
    """
    # 1. Setup
    audit = Audit(
        url="https://pdf-test.com", status=AuditStatus.COMPLETED, domain="pdf-test.com"
    )
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)

    markdown_content = "# Test PDF Report"
    mock_queue_job.return_value = type("Job", (), {"id": 321})()
    mock_run_job.return_value = {"job_id": 321, "status": "completed"}

    # 2. Ejecutar la tarea
    with patch("app.workers.tasks.get_db_session") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = db_session
        result = generate_pdf_task.run(audit.id, markdown_content)

    mock_queue_job.assert_called_once_with(
        db_session,
        audit_id=audit.id,
        requested_by_user_id=None,
        force_pagespeed_refresh=False,
        force_report_refresh=False,
        force_external_intel_refresh=False,
    )
    mock_run_job.assert_called_once_with(321)
    assert result == {"job_id": 321, "status": "completed"}


@patch("app.workers.tasks.run_pagespeed_generation_job_task.run")
@patch("app.workers.tasks.PageSpeedJobService.queue_if_needed")
def test_run_pagespeed_task_delegates_to_canonical_job(
    mock_queue_job, mock_run_job, db_session: Session
):
    audit = Audit(
        url="https://pagespeed-task-test.com",
        status=AuditStatus.COMPLETED,
        domain="pagespeed-task-test.com",
    )
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)

    mock_queue_job.return_value = type("Job", (), {"id": 654})()
    mock_run_job.return_value = {"job_id": 654, "status": "completed"}

    with patch("app.workers.tasks.get_db_session") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = db_session
        result = run_pagespeed_task.run(audit.id)

    mock_queue_job.assert_called_once()
    mock_run_job.assert_called_once_with(654)
    assert result == {"job_id": 654, "status": "completed"}


def test_worker_async_runtime_reuses_same_loop_for_multiple_coroutines():
    async def _loop_id():
        return id(asyncio.get_running_loop())

    first_loop_id = run_worker_coroutine(_loop_id())
    second_loop_id = run_worker_coroutine(_loop_id())

    assert first_loop_id == second_loop_id

    _worker_async_runtime.close()
