from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.config import settings
from app.models import Audit, AuditStatus
from app.schemas import AuditCreate, AuditResponse, AuditSummary
from app.services.audit_service import AuditService
from app.services.pipeline_service import PipelineService
from app.services.audit_local_service import AuditLocalService

from app.core.llm_client import call_gemini_api

router = APIRouter(
    prefix="/audits",
    tags=["audits"],
    responses={404: {"description": "No encontrado"}},
)


async def run_audit_background(audit_id: int, url: str, db: Session):
    """
    Función que se ejecuta en segundo plano para no bloquear la respuesta de la API.
    """
    print(f"Iniciando auditoría en segundo plano para el audit_id: {audit_id}")
    AuditService.update_audit_status(db, audit_id, AuditStatus.processing)

    try:
        # Aquí es donde se llama al pipeline completo.
        # La función `call_gemini_api` es un placeholder, debes reemplazarla
        # por tu implementación real de llamada al LLM.
        result = await PipelineService.run_complete_audit(
            url=url,
            audit_local_service=AuditLocalService.run_local_audit,
            llm_function=call_gemini_api, # <--- REEMPLAZA ESTO
            google_api_key=settings.GOOGLE_API_KEY,
            google_cx_id=settings.CSE_ID,
        )

        # Guardar los resultados en la base de datos
        AuditService.set_audit_results(
            db=db,
            audit_id=audit_id,
            target_audit=result.get("target_audit"),
            external_intelligence=result.get("external_intelligence"),
            search_results=result.get("search_results"),
            competitor_audits=result.get("competitor_audits"),
            report_markdown=result.get("report_markdown"),
            fix_plan=result.get("fix_plan"),
        )

        # Marcar la auditoría como completada
        AuditService.update_audit_status(db, audit_id, AuditStatus.completed)
        print(f"Auditoría completada para el audit_id: {audit_id}")

    except Exception as e:
        print(f"Error durante la auditoría en segundo plano para {audit_id}: {e}")
        AuditService.update_audit_status(
            db, audit_id, AuditStatus.failed, error_message=str(e)
        )


@router.post("", response_model=AuditResponse, status_code=201)
async def create_audit(
    audit_create: AuditCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Crea una nueva auditoría y la inicia en segundo plano.
    Esta es la implementación de la Fase 3.
    """
    # 1. Crear el registro inicial en la base de datos
    audit = AuditService.create_audit(db, audit_create)

    # 2. Añadir la tarea de auditoría completa al background
    background_tasks.add_task(
        run_audit_background, audit_id=audit.id, url=str(audit.url), db=db
    )

    # 3. Devolver una respuesta inmediata al cliente
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

    if audit.status != AuditStatus.completed:
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

    if audit.status != AuditStatus.completed:
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