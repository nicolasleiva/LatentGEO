from fastapi import APIRouter, Depends, HTTPException, Response, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
import asyncio

from app.core.database import get_db
from app.core.config import settings
from app.models import Audit, AuditStatus
from app.schemas import AuditCreate, AuditResponse, AuditSummary
from app.services.audit_service import AuditService
from app.services.pipeline_service import PipelineService
from app.services.audit_local_service import AuditLocalService
from app.core.logger import get_logger

from app.core.llm_client import call_gemini_api

# Importar la tarea de Celery
from app.workers.tasks import run_audit_task

logger = get_logger(__name__)

router = APIRouter(
    prefix="/audits",
    tags=["audits"],
    responses={404: {"description": "No encontrado"}},
)


async def run_audit_sync(audit_id: int):
    """
    Función auxiliar para ejecutar auditoría de forma síncrona como fallback.
    """
    from app.core.llm import get_llm_function
    from app.core.database import SessionLocal
    
    logger.info(f"Running audit {audit_id} synchronously (Redis unavailable)")
    
    db = SessionLocal()
    try:
        # Marcar como processing
        AuditService.update_audit_progress(
            db=db, audit_id=audit_id, progress=5, status=AuditStatus.RUNNING
        )
        
        audit = AuditService.get_audit(db, audit_id)
        if not audit:
            logger.error(f"Audit {audit_id} not found")
            return
        
        # Ejecutar pipeline
        llm_function = get_llm_function()
        
        # Ejecutar auditoría local directamente
        # run_local_audit returns a tuple (result, error), we only need the result for the pipeline.
        target_audit_result, _ = await AuditLocalService.run_local_audit(str(audit.url))
        if not target_audit_result:
            raise Exception("Local audit failed to produce results.")
        
        result = await PipelineService.run_complete_audit(
            url=str(audit.url),
            target_audit=target_audit_result,
            crawler_service=None,
            audit_local_service=None,
            llm_function=llm_function,
            google_api_key=settings.GOOGLE_API_KEY,
            google_cx_id=settings.CSE_ID,
        )
        
        # Guardar resultados
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
        logger.info(f"Audit {audit_id} completed successfully (sync mode)")
        
    except Exception as e:
        logger.error(f"Error running sync audit {audit_id}: {e}", exc_info=True)
        AuditService.update_audit_progress(
            db=db,
            audit_id=audit_id,
            progress=0,
            status=AuditStatus.FAILED,
            error_message=str(e),
        )
    finally:
        db.close()


@router.post("", response_model=AuditResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_audit(
    audit_create: AuditCreate,
    response: Response,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Crea una nueva auditoría y la encola para su procesamiento en segundo plano.
    Responde inmediatamente con un 202 Accepted.
    
    Si Redis/Celery no está disponible, ejecuta la auditoría en modo síncrono.
    """
    # 1. Crear el registro inicial en la base de datos
    audit = AuditService.create_audit(db, audit_create)

    # 2. Intentar lanzar la tarea de Celery en segundo plano
    try:
        task = run_audit_task.delay(audit.id)
        AuditService.set_audit_task_id(db, audit.id, task.id)
        logger.info(f"Audit {audit.id} queued in Celery with task_id: {task.id}")
    except Exception as e:
        # Fallback: Si Redis no está disponible, ejecutar en modo síncrono
        logger.warning(f"Celery unavailable (Redis not running): {e}")
        logger.info(f"Falling back to synchronous execution for audit {audit.id}")
        background_tasks.add_task(run_audit_sync, audit.id)

    # 3. Establecer el header 'Location' para que el cliente pueda consultar el estado
    response.headers["Location"] = f"/audits/{audit.id}"

    # 4. Devolver una respuesta inmediata al cliente con los datos iniciales
    return audit


@router.get("", response_model=List[AuditSummary])
def list_audits(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100
) -> List[Audit]:
    """
    Lista todas las auditorías con paginación.
    """
    # The method is get_audits, not list_audits
    audits = AuditService.get_audits(db, skip=skip, limit=limit)
    return audits


@router.get("/{audit_id}", response_model=AuditResponse)
def get_audit(audit_id: int, db: Session = Depends(get_db)):
    """
    Obtiene los detalles completos de una auditoría, incluyendo sus resultados.
    """
    audit = AuditService.get_audit(db, audit_id)
    if not audit:
        raise HTTPException(status_code=404, detail="Auditoría no encontrada")
    return audit


@router.get("/{audit_id}/report", response_model=dict)
def get_audit_report(audit_id: int, db: Session = Depends(get_db)):
    """
    Devuelve el reporte en Markdown de una auditoría completada.
    """
    audit = AuditService.get_audit(db, audit_id)
    if not audit:
        raise HTTPException(status_code=404, detail="Auditoría no encontrada")

    if audit.status != AuditStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"El reporte aún no está listo. Estado actual: {audit.status.value}",
        )

    return {"report_markdown": audit.report_markdown}


@router.get("/{audit_id}/fix_plan", response_model=dict)
def get_audit_fix_plan(audit_id: int, db: Session = Depends(get_db)):
    """
    Devuelve el plan de correcciones (fix plan) en JSON.
    """
    audit = AuditService.get_audit(db, audit_id)
    if not audit:
        raise HTTPException(status_code=404, detail="Auditoría no encontrada")

    if audit.status != AuditStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"El plan de correcciones aún no está listo. Estado actual: {audit.status.value}",
        )

    return {"fix_plan": audit.fix_plan}


@router.delete("/{audit_id}", status_code=204)
def delete_audit(audit_id: int, db: Session = Depends(get_db)):
    """
    Elimina una auditoría de la base de datos.
    """
    success = AuditService.delete_audit(db, audit_id)
    if not success:
        raise HTTPException(status_code=404, detail="Auditoría no encontrada")
    return


@router.get("/status/{status}", response_model=List[AuditSummary])
def get_audits_by_status(
    status: AuditStatus, db: Session = Depends(get_db)
) -> List[Audit]:
    """
    Filtra auditorías por su estado (pending, processing, completed, failed).
    """
    audits = AuditService.get_audits_by_status(db, status)
    return audits


@router.get("/stats/summary", response_model=dict)
def get_audits_summary(db: Session = Depends(get_db)):
    """
    Obtiene estadísticas generales sobre las auditorías.
    """
    stats = AuditService.get_stats_summary(db)
    return stats
