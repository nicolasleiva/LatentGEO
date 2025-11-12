"""
Tests para los Celery Workers
"""
import pytest
from unittest.mock import patch, MagicMock, ANY
from sqlalchemy.orm import Session

from backend.app.workers.tasks import run_audit_task, generate_pdf_task
from backend.app.services.audit_service import AuditService
from backend.app.models import Audit, AuditStatus

# --- Test para run_audit_task ---


@patch("backend.app.workers.tasks.generate_pdf_task.delay")
@patch("backend.app.workers.tasks.PipelineService.run_complete_audit")
def test_run_audit_task_success(
    mock_run_complete_audit, mock_generate_pdf, db_session: Session
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
    mock_run_complete_audit.return_value = mock_pipeline_result

    # 2. Ejecutar la tarea
    # Usamos patch en get_db_session para que la tarea use la sesión de test
    with patch("backend.app.workers.tasks.get_db_session") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = db_session
        run_audit_task(audit.id)

    # 3. Verificación
    db_session.refresh(audit)

    # Verificar que el estado es COMPLETED y el progreso 100
    assert audit.status == AuditStatus.COMPLETED
    assert audit.progress == 100

    # Verificar que los resultados se guardaron
    assert audit.report_markdown == "# Report"
    assert audit.fix_plan[0]["issue"] == "test"
    assert audit.target_audit["score"] == 90

    # Verificar que la tarea de PDF fue llamada
    mock_generate_pdf.assert_called_once_with(audit.id, "# Report")


@patch("backend.app.workers.tasks.PipelineService.run_complete_audit")
def test_run_audit_task_failure(mock_run_complete_audit, db_session: Session):
    """
    Verifica el manejo de errores en la tarea 'run_audit_task'.
    """
    # 1. Setup
    audit = Audit(url="https://fail.com", status=AuditStatus.PENDING, domain="fail.com")
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)

    # Mock de un error en el pipeline
    mock_run_complete_audit.side_effect = Exception("Pipeline exploded")

    # 2. Ejecutar la tarea
    with patch("backend.app.workers.tasks.get_db_session") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = db_session
        run_audit_task(audit.id)

    # 3. Verificación
    db_session.refresh(audit)

    assert audit.status == AuditStatus.FAILED
    assert audit.error_message == "Pipeline exploded"


# --- Test para generate_pdf_task ---


@patch("backend.app.workers.tasks.ReportService.create_report")
@patch("backend.app.workers.tasks.PDFReport")
def test_generate_pdf_task(MockPDFReport, mock_create_report, db_session: Session):
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

    # Mock de la clase PDFReport
    mock_pdf_instance = MagicMock()
    MockPDFReport.return_value = mock_pdf_instance

    # 2. Ejecutar la tarea
    with patch("backend.app.workers.tasks.get_db_session") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = db_session
        generate_pdf_task(audit.id, markdown_content)

    # 3. Verificación
    # Verificar que se crearon la portada y el contenido
    mock_pdf_instance.create_cover_page.assert_called_once()
    mock_pdf_instance.write_markdown_text.assert_called_once_with(markdown_content)

    # Verificar que se guardó el PDF
    mock_pdf_instance.output.assert_called_once()

    # Verificar que se registró en la base de datos
    mock_create_report.assert_called_once_with(
        db=db_session,
        audit_id=audit.id,
        report_type="PDF",
        file_path=ANY,  # El path exacto puede variar
    )
