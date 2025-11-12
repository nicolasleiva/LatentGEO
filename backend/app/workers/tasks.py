"""
Celery Tasks for background processing.
"""
import asyncio
import os
import sys
from contextlib import contextmanager
from sqlalchemy.orm import Session

from backend.app.core.database import SessionLocal
from backend.app.core.logger import get_logger
from backend.app.models import AuditStatus
from backend.app.services.audit_service import AuditService, ReportService
from backend.app.services.pdf_service import PDFService
from backend.app.services.audit_local_service import AuditLocalService
from backend.app.services.pipeline_service import PipelineService
from backend.app.core.config import settings
from backend.app.workers.celery_app import celery_app

# Importar la fábrica de LLM desde el endpoint de auditorías
# Esto puede ser refactorizado a un módulo de utilidades común en el futuro
from backend.app.core.llm import get_llm_function

logger = get_logger(__name__)


@contextmanager
def get_db_session():
    """Provide a transactional scope around a series of operations."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@celery_app.task(name="run_audit_task")
def run_audit_task(audit_id: int):
    """
    Celery task to run the complete audit pipeline in the background.
    """
    logger.info(f"Celery task 'run_audit_task' started for audit_id: {audit_id}")

    with get_db_session() as db:
        # 1. Marcar la auditoría como RUNNING
        AuditService.update_audit_progress(
            db=db, audit_id=audit_id, progress=5, status=AuditStatus.RUNNING
        )

        audit = AuditService.get_audit(db, audit_id)
        if not audit:
            logger.error(f"Audit with ID {audit_id} not found.")
            return

    # 2. Ejecutar el pipeline
    try:
        llm_function = get_llm_function()

        async def audit_local_service_func(url: str):
            result = await AuditLocalService.run_local_audit(url)
            return result, None

        # El pipeline es asíncrono, por lo que se ejecuta con asyncio.run
        result = asyncio.run(
            PipelineService.run_complete_audit(
                url=str(audit.url),
                target_audit={},
                crawler_service=None,
                audit_local_service=audit_local_service_func,
                llm_function=llm_function,
                google_api_key=settings.GOOGLE_API_KEY,
                google_cx_id=settings.CSE_ID,
            )
        )

        with get_db_session() as db:
            # 3. Guardar resultados y marcar como COMPLETED
            report_markdown = result.get("report_markdown", "")
            fix_plan = result.get("fix_plan", [])
            target_audit = result.get("target_audit", {})
            external_intelligence = result.get("external_intelligence", {})
            search_results = result.get("search_results", {})
            competitor_audits = result.get("competitor_audits", [])

            AuditService.set_audit_results(
                db=db,
                audit_id=audit_id,
                target_audit=target_audit,
                external_intelligence=external_intelligence,
                search_results=search_results,
                competitor_audits=competitor_audits,
                report_markdown=report_markdown,
                fix_plan=fix_plan,
            )

            AuditService.update_audit_progress(
                db=db, audit_id=audit_id, progress=100, status=AuditStatus.COMPLETED
            )
            logger.info(f"Audit {audit_id} completed successfully.")

            # 4. Disparar la tarea de generación de PDF
            if report_markdown:
                logger.info(f"Dispatching PDF generation task for audit {audit_id}.")
                generate_pdf_task.delay(audit_id, report_markdown)

    except Exception as e:
        logger.error(f"Error running pipeline for audit {audit_id}: {e}", exc_info=True)
        with get_db_session() as db:
            # 5. Marcar como FAILED en caso de error
            AuditService.update_audit_progress(
                db=db,
                audit_id=audit_id,
                progress=0,
                status=AuditStatus.FAILED,
                error_message=str(e),
            )
        logger.error(f"Audit {audit_id} marked as FAILED.")


@celery_app.task(name="generate_pdf_task")
def generate_pdf_task(audit_id: int, report_markdown: str):
    """
    Celery task to generate a PDF report from markdown content.
    """
    logger.info(f"Starting PDF generation for audit_id: {audit_id}")

    with get_db_session() as db:
        audit = AuditService.get_audit(db, audit_id)
        if not audit:
            logger.error(f"Audit {audit_id} not found for PDF generation.")
            return

        try:
            # 1. Usar el nuevo PDFService para generar el archivo
            pdf_file_path = PDFService.create_from_audit(
                audit=audit, markdown_content=report_markdown
            )

            # 2. Registrar el reporte en la base de datos
            ReportService.create_report(
                db=db, audit_id=audit_id, report_type="PDF", file_path=pdf_file_path
            )
            logger.info(f"PDF report for audit {audit_id} registered in the database.")
        except Exception as e:
            logger.error(f"Failed to generate PDF for audit {audit_id}: {e}", exc_info=True)
