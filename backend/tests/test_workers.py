"""
Tests para los Celery Workers
"""

from unittest.mock import ANY, AsyncMock, patch

import pytest
from app.models import Audit, AuditStatus
from app.workers.tasks import generate_pdf_task, run_audit_task
from sqlalchemy.orm import Session

# --- Test para run_audit_task ---


@patch("app.workers.tasks.AuditLocalService.run_local_audit", new_callable=AsyncMock)
@patch("app.services.pipeline_service.run_initial_audit", new_callable=AsyncMock)
def test_run_audit_task_success(
    mock_run_initial, mock_local_audit, db_session: Session
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


@patch("app.workers.tasks.ReportService.create_report")
@patch("app.workers.tasks.PDFService.create_from_audit")
def test_generate_pdf_task(
    mock_create_from_audit, mock_create_report, db_session: Session
):
    """
    Verifica que la tarea 'generate_pdf_task' genera un PDF y lo registra.
    """
    # 1. Setup
    audit = Audit(
        url="https://pdf-test.com", status=AuditStatus.COMPLETED, domain="pdf-test.com"
    )
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)

    markdown_content = "# Test PDF Report"
    mock_create_from_audit.return_value = "reports/audit_1/report.pdf"

    # 2. Ejecutar la tarea
    with patch("app.workers.tasks.get_db_session") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = db_session
        generate_pdf_task.run(audit.id, markdown_content)

    # Verificar que se registró en la base de datos
    mock_create_report.assert_called_once_with(
        db=db_session,
        audit_id=audit.id,
        report_type="PDF",
        file_path=ANY,  # El path exacto puede variar
    )
