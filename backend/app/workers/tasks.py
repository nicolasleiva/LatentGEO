"""
Celery Tasks for background processing.
"""
import asyncio
import os
import sys
from contextlib import contextmanager
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.logger import get_logger
from app.models import AuditStatus
from app.services.audit_service import AuditService, ReportService
from app.services.pdf_service import PDFService
from app.services.audit_local_service import AuditLocalService
from app.services.pipeline_service import PipelineService
from app.core.config import settings
from app.workers.celery_app import celery_app

# Importar la fábrica de LLM desde el endpoint de auditorías
# Esto puede ser refactorizado a un módulo de utilidades común en el futuro
from app.core.llm_kimi import get_llm_function

logger = get_logger(__name__)


@contextmanager
def get_db_session():
    """Provide a transactional scope around a series of operations."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@celery_app.task(
    name="run_audit_task",
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 60},
    soft_time_limit=300,  # 5 minutos
    time_limit=360,  # 6 minutos
)
def run_audit_task(self, audit_id: int):
    """
    Celery task to run the complete audit pipeline in the background.
    - Es idempotente en la práctica: si se reintenta, el pipeline se ejecuta de nuevo,
      sobrescribiendo los resultados, lo cual es aceptable.
    - Gestiona su propia sesión de BD.
    """
    logger.info(f"Celery task '{self.name}' [ID: {self.request.id}] started for audit_id: {audit_id}")

    # Delay para asegurar que la transacción del backend se complete y el archivo SQLite se sincronice
    import time
    time.sleep(2)

    with get_db_session() as db:
        # 1. Marcar la auditoría como RUNNING (antes estaba PENDING)
        AuditService.update_audit_progress(
            db=db, audit_id=audit_id, progress=5, status=AuditStatus.RUNNING
        )

        audit = AuditService.get_audit(db, audit_id)
        if not audit:
            logger.error(f"Audit with ID {audit_id} not found.")
            raise ValueError(f"Audit {audit_id} not found")

    # 2. Ejecutar el pipeline
    try:
        llm_function = get_llm_function()

        async def audit_local_service_func(url: str):
            """
            Wrapper alrededor de AuditLocalService.run_local_audit que normaliza el retorno.
            Acepta que run_local_audit devuelva (summary, meta) o solo summary, y retorna siempre summary (dict).
            """
            try:
                result = await AuditLocalService.run_local_audit(url)

                # Si la función retorna (summary, meta) -> extraer summary
                if isinstance(result, (tuple, list)) and len(result) > 0:
                    summary = result[0]
                else:
                    summary = result

                # Si por alguna razón summary no es dict, retornar un dict vacío con status 500
                if not isinstance(summary, dict):
                    logger.error(f"AuditLocalService.run_local_audit returned non-dict for {url}: {type(summary)}")
                    return {"status": 500, "url": url, "error": "Invalid audit result type"}

                return summary
            except Exception as audit_error:
                logger.error(f"Error in audit_local_service_func for {url}: {audit_error}", exc_info=True)
                return {"status": 500, "url": url, "error": str(audit_error)}

        # Importar crawler y PageSpeed
        from app.services.crawler_service import CrawlerService
        from app.services.pagespeed_service import PageSpeedService
        
        # Ejecutar PageSpeed en paralelo con el pipeline
        async def run_with_pagespeed():
            # Ejecutar pipeline principal
            pipeline_task = PipelineService.run_complete_audit(
                url=str(audit.url),
                target_audit={},
                crawler_service=CrawlerService.crawl_site,
                audit_local_service=audit_local_service_func,
                llm_function=llm_function,
                google_api_key=settings.GOOGLE_API_KEY,
                google_cx_id=settings.CSE_ID,
            )
            
            # Ejecutar PageSpeed
            pagespeed_task = PageSpeedService.analyze_both_strategies(
                url=str(audit.url),
                api_key=settings.GOOGLE_PAGESPEED_API_KEY
            )
            
            # Esperar ambos
            pipeline_result, pagespeed_result = await asyncio.gather(
                pipeline_task, pagespeed_task, return_exceptions=True
            )
            
            # Manejar errores
            if isinstance(pipeline_result, Exception):
                logger.error(f"Pipeline error: {pipeline_result}")
                raise pipeline_result
            
            if isinstance(pagespeed_result, Exception):
                logger.warning(f"PageSpeed error: {pagespeed_result}")
                pagespeed_result = {"error": str(pagespeed_result)}
            
            # Agregar PageSpeed al resultado
            pipeline_result["pagespeed"] = pagespeed_result
            return pipeline_result
        
        result = asyncio.run(run_with_pagespeed())

        # Guardar páginas auditadas individuales como en ag2_pipeline.py
        _save_individual_pages(db, audit_id, result)

        with get_db_session() as db:
            # 3. Guardar resultados y marcar como COMPLETED
            report_markdown = result.get("report_markdown", "")
            
            # Ensure target_audit is a dictionary. The PipelineService might return it as a tuple
            # if it internally calls AuditLocalService.run_local_audit without the wrapper,
            # or if it otherwise mismanages the target_audit structure.
            raw_target_audit = result.get("target_audit", {})
            if not isinstance(raw_target_audit, dict):
                logger.warning(
                    f"PipelineService returned non-dict target_audit for audit {audit_id}: {type(raw_target_audit)}"
                )
                # If it's a tuple (summary, meta), try to extract summary; otherwise, default to an empty dict.
                target_audit = (
                    raw_target_audit[0] 
                    if isinstance(raw_target_audit, (tuple, list)) 
                    and len(raw_target_audit) > 0 
                    and isinstance(raw_target_audit[0], dict) 
                    else {}
                )
            else:
                target_audit = raw_target_audit

            fix_plan = result.get("fix_plan", [])
            external_intelligence = result.get("external_intelligence", {})
            search_results = result.get("search_results", {})
            competitor_audits = result.get("competitor_audits", [])
            pagespeed_data = result.get("pagespeed", {})
            
            # Guardar PageSpeed en JSON y BD
            if pagespeed_data:
                _save_pagespeed_data(audit_id, pagespeed_data)
                logger.info(f"PageSpeed data: {list(pagespeed_data.keys())}")

            AuditService.set_audit_results(
                db=db,
                audit_id=audit_id,
                target_audit=target_audit,
                external_intelligence=external_intelligence,
                search_results=search_results,
                competitor_audits=competitor_audits,
                report_markdown=report_markdown,
                fix_plan=fix_plan,
                pagespeed_data=pagespeed_data,
            )

            AuditService.update_audit_progress(
                db=db, audit_id=audit_id, progress=100, status=AuditStatus.COMPLETED
            )
            logger.info(f"Audit {audit_id} completed successfully.")

            # 4. Generar PDF inmediatamente (síncrono)
            if report_markdown:
                logger.info(f"Generating PDF for audit {audit_id}")
                try:
                    pdf_file_path = PDFService.create_from_audit(
                        audit=audit, markdown_content=report_markdown
                    )
                    ReportService.create_report(
                        db=db, audit_id=audit_id, report_type="PDF", file_path=pdf_file_path
                    )
                    logger.info(f"PDF generated: {pdf_file_path}")
                except Exception as pdf_error:
                    logger.error(f"PDF generation failed for audit {audit_id}: {pdf_error}", exc_info=True)

    except Exception as e:
        logger.error(f"Error running pipeline for audit {audit_id}: {e}", exc_info=True)
        try:
            with get_db_session() as db:
                # 5. Marcar como FAILED en caso de error
                # Intentamos recuperar el audit de la DB para leer su progreso actual
                audit = AuditService.get_audit(db, audit_id)
                last_progress = getattr(audit, "progress", 0) if audit else 0

                AuditService.update_audit_progress(
                    db=db,
                    audit_id=audit_id,
                    progress=last_progress,  # Mantener el último progreso conocido
                    status=AuditStatus.FAILED,
                    error_message=str(e),
                )
            logger.error(f"Audit {audit_id} marked as FAILED.")
        except Exception as db_error:
            logger.critical(f"Failed to update audit {audit_id} status to FAILED: {db_error}", exc_info=True)
        raise


def _save_pagespeed_data(audit_id: int, pagespeed_data: dict):
    """Guardar datos de PageSpeed en JSON"""
    try:
        import json
        from pathlib import Path
        
        reports_dir = Path(settings.REPORTS_DIR or "reports") / f"audit_{audit_id}"
        reports_dir.mkdir(parents=True, exist_ok=True)
        
        pagespeed_path = reports_dir / "pagespeed.json"
        with open(pagespeed_path, 'w', encoding='utf-8') as f:
            json.dump(pagespeed_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"PageSpeed data saved to {pagespeed_path}")
    except Exception as e:
        logger.error(f"Error saving PageSpeed data for audit {audit_id}: {e}")


def _save_individual_pages(db: Session, audit_id: int, pipeline_result: dict):
    """Guardar páginas auditadas individuales como en ag2_pipeline.py"""
    try:
        target_audit = pipeline_result.get("target_audit", {})
        if not isinstance(target_audit, dict):
            return
        
        # Obtener páginas auditadas del resultado agregado
        audited_page_paths = target_audit.get("audited_page_paths", [])
        audited_pages_count = target_audit.get("audited_pages_count", 0)
        
        if not audited_page_paths or audited_pages_count == 0:
            # Si no hay páginas múltiples, guardar solo la principal
            page_url = target_audit.get("url")
            if page_url and target_audit.get("status") == 200:
                AuditService.save_page_audit(
                    db=db,
                    audit_id=audit_id,
                    page_url=page_url,
                    audit_data=target_audit,
                    page_index=0
                )
                logger.info(f"Guardada 1 página auditada para audit {audit_id}")
            else:
                logger.info(f"Guardadas 0 páginas auditadas para audit {audit_id}")
            return
        
        # Guardar cada página auditada
        audit = AuditService.get_audit(db, audit_id)
        if not audit:
            return
            
        base_url = str(audit.url).rstrip('/')
        
        for i, page_path in enumerate(audited_page_paths):
            # Reconstruir URL completa
            if page_path.startswith('http'):
                page_url = page_path
            elif page_path.startswith('/'):
                page_url = f"{base_url}{page_path}"
            else:
                page_url = f"{base_url}/{page_path}"
            
            # Crear datos de auditoría para la página
            page_audit_data = {
                "url": page_url,
                "path": page_path,
                "status": 200,
                "generated_at": target_audit.get("generated_at"),
                "structure": target_audit.get("structure", {}),
                "content": target_audit.get("content", {}),
                "eeat": target_audit.get("eeat", {}),
                "schema": target_audit.get("schema", {})
            }
            
            # Guardar página auditada
            AuditService.save_page_audit(
                db=db,
                audit_id=audit_id,
                page_url=page_url,
                audit_data=page_audit_data,
                page_index=i
            )
        
        logger.info(f"Guardadas {len(audited_page_paths)} páginas auditadas para audit {audit_id}")
    except Exception as e:
        logger.error(f"Error guardando páginas individuales para audit {audit_id}: {e}", exc_info=True)


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
            raise ValueError(f"Audit {audit_id} not found for PDF generation")

        try:
            pdf_file_path = PDFService.create_from_audit(
                audit=audit, markdown_content=report_markdown
            )
            ReportService.create_report(
                db=db, audit_id=audit_id, report_type="PDF", file_path=pdf_file_path
            )
            logger.info(f"PDF report for audit {audit_id} registered in the database.")
        except Exception as e:
            logger.error(f"Failed to generate PDF for audit {audit_id}: {e}", exc_info=True)
            try:
                AuditService.update_audit_progress(
                    db=db, audit_id=audit_id, 
                    progress=100, status=AuditStatus.COMPLETED,
                    error_message=f"PDF generation failed: {str(e)}"
                )
            except Exception as update_error:
                logger.error(f"Failed to update audit status after PDF error: {update_error}", exc_info=True)
            raise
