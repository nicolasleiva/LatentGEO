from fastapi import APIRouter, Depends, HTTPException, Response, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
import asyncio

from app.core.database import get_db
from app.core.config import settings
from app.models import Audit, AuditStatus
from app.schemas import AuditCreate, AuditResponse, AuditSummary, AuditConfigRequest, ChatMessage
from app.services.audit_service import AuditService
from app.services.pipeline_service import PipelineService
from app.services.audit_local_service import AuditLocalService
from app.core.logger import get_logger

from app.core.llm_client import call_gemini_api

# Importar la tarea de Celery
from app.workers.tasks import run_audit_task

logger = get_logger(__name__)

router = APIRouter(
    tags=["audits"],
    responses={404: {"description": "No encontrado"}},
)


async def run_audit_sync(audit_id: int):
    """
    Función auxiliar para ejecutar auditoría de forma síncrona como fallback.
    """
    from app.core.llm_kimi import get_llm_function
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
        logger.info(f"Dashboard ready! PDF can be generated manually from the dashboard.")
        
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
    Crea auditoría. Si tiene competitors/market, inicia pipeline.
    Si no, solo crea registro (espera configuración de chat).
    """
    audit = AuditService.create_audit(db, audit_create)

    # Solo iniciar pipeline si tiene configuración completa
    if audit_create.competitors or audit_create.market:
        try:
            task = run_audit_task.delay(audit.id)
            AuditService.set_audit_task_id(db, audit.id, task.id)
            logger.info(f"Audit {audit.id} queued with config")
        except Exception as e:
            logger.warning(f"Celery unavailable: {e}")
            background_tasks.add_task(run_audit_sync, audit.id)
    else:
        logger.info(f"Audit {audit.id} created, waiting for chat config")

    response.headers["Location"] = f"/audits/{audit.id}"
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
    
    # Cargar páginas auditadas
    pages = AuditService.get_audited_pages(db, audit_id)
    audit.pages = pages
    
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


@router.get("/{audit_id}/pages", response_model=list)
def get_audit_pages(audit_id: int, db: Session = Depends(get_db)):
    """
    Obtiene todas las páginas auditadas de una auditoría.
    """
    audit = AuditService.get_audit(db, audit_id)
    if not audit:
        raise HTTPException(status_code=404, detail="Auditoría no encontrada")
    
    pages = AuditService.get_audited_pages(db, audit_id)
    return [
        {
            "id": p.id,
            "url": p.url,
            "path": p.path,
            "overall_score": p.overall_score,
            "h1_score": p.h1_score,
            "structure_score": p.structure_score,
            "content_score": p.content_score,
            "eeat_score": p.eeat_score,
            "schema_score": p.schema_score,
            "critical_issues": p.critical_issues,
            "high_issues": p.high_issues,
            "medium_issues": p.medium_issues,
            "low_issues": p.low_issues,
            "audit_data": p.audit_data
        }
        for p in pages
    ]


@router.get("/{audit_id}/pages/{page_id}", response_model=dict)
def get_page_details(audit_id: int, page_id: int, db: Session = Depends(get_db)):
    """
    Obtiene detalles de una página específica.
    """
    audit = AuditService.get_audit(db, audit_id)
    if not audit:
        raise HTTPException(status_code=404, detail="Auditoría no encontrada")
    
    pages = AuditService.get_audited_pages(db, audit_id)
    page = next((p for p in pages if p.id == page_id), None)
    
    if not page:
        raise HTTPException(status_code=404, detail="Página no encontrada")
    
    return {
        "id": page.id,
        "url": page.url,
        "path": page.path,
        "overall_score": page.overall_score,
        "h1_score": page.h1_score,
        "structure_score": page.structure_score,
        "content_score": page.content_score,
        "eeat_score": page.eeat_score,
        "schema_score": page.schema_score,
        "critical_issues": page.critical_issues,
        "high_issues": page.high_issues,
        "medium_issues": page.medium_issues,
        "low_issues": page.low_issues,
        "audit_data": page.audit_data
    }


@router.get("/{audit_id}/competitors", response_model=list)
def get_competitors(audit_id: int, db: Session = Depends(get_db)):
    """
    Obtiene datos de competidores de una auditoría con GEO scores calculados.
    """
    from app.services.audit_service import CompetitorService
    
    audit = AuditService.get_audit(db, audit_id)
    if not audit:
        raise HTTPException(status_code=404, detail="Auditoría no encontrada")
    
    if audit.status != AuditStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail="La auditoría aún no está completada. Los datos de competidores estarán disponibles al finalizar."
        )
    
    # Obtener competidores de la base de datos
    competitors_db = CompetitorService.get_competitors(db, audit_id)
    
    # Si hay competidores en la BD, usarlos
    if competitors_db:
        result = []
        for comp in competitors_db:
            audit_data = comp.audit_data or {}
            geo_score = comp.geo_score or 0
            if geo_score == 0:
                geo_score = CompetitorService._calculate_geo_score(audit_data)
            formatted = CompetitorService._format_competitor_data(audit_data, geo_score, comp.url)
            result.append(formatted)
        return result
    
    # Fallback: usar competitor_audits del JSON y calcular scores
    competitors = audit.competitor_audits or []
    result = []
    for comp in competitors:
        if isinstance(comp, dict):
            geo_score = comp.get("geo_score", 0)
            # Si no tiene score, calcularlo
            if geo_score == 0 or geo_score is None:
                geo_score = CompetitorService._calculate_geo_score(comp)
            formatted = CompetitorService._format_competitor_data(comp, geo_score)
            result.append(formatted)
    
    return result


@router.get("/{audit_id}/download-pdf")
def download_audit_pdf(audit_id: int, db: Session = Depends(get_db)):
    """
    Descarga el PDF de una auditoría completada.
    """
    from fastapi.responses import FileResponse
    import os
    
    audit = AuditService.get_audit(db, audit_id)
    if not audit:
        raise HTTPException(status_code=404, detail="Auditoría no encontrada")
    
    if audit.status != AuditStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"El PDF aún no está listo. Estado actual: {audit.status.value}",
        )
    
    if not audit.report_pdf_path or not os.path.exists(audit.report_pdf_path):
        raise HTTPException(
            status_code=404,
            detail="El archivo PDF no se encuentra disponible",
        )
    
    return FileResponse(
        path=audit.report_pdf_path,
        media_type="application/pdf",
        filename=f"audit_{audit_id}_report.pdf"
    )


@router.post("/chat/config", response_model=ChatMessage)
async def configure_audit_chat(
    config: AuditConfigRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Configura auditoría y lanza pipeline.
    """
    audit = AuditService.get_audit(db, config.audit_id)
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")
    
    if config.language:
        audit.language = config.language
    if config.competitors:
        audit.competitors = config.competitors
    if config.market:
        audit.market = config.market
    
    db.commit()
    db.refresh(audit)
    
    # Iniciar pipeline ahora que tenemos configuración
    try:
        task = run_audit_task.delay(audit.id)
        AuditService.set_audit_task_id(db, audit.id, task.id)
        logger.info(f"Audit {audit.id} pipeline started after chat config")
    except Exception as e:
        logger.warning(f"Celery unavailable: {e}")
        background_tasks.add_task(run_audit_sync, audit.id)
    
    return ChatMessage(
        role="assistant",
        content="Configuration saved. Starting audit..."
    )
