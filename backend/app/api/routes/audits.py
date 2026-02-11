from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Response,
    status,
    BackgroundTasks,
    Request,
)
from sqlalchemy.orm import Session
from typing import List
import asyncio
import os
from datetime import datetime
from pydantic import BaseModel

from app.core.database import get_db
from app.core.config import settings
from app.models import Audit, AuditStatus, Competitor
from app.schemas import (
    AuditCreate,
    AuditResponse,
    AuditSummary,
    AuditConfigRequest,
    ChatMessage,
)
from app.services.audit_service import AuditService
from app.services.pipeline_service import PipelineService
from app.services.audit_local_service import AuditLocalService
from app.core.logger import get_logger

from app.core.llm_client import call_kimi_api

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
    PageSpeed is NOT run here - it's executed on-demand when user requests it.
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

        # PageSpeed NOT collected here - runs on-demand only.
        logger.info("PageSpeed skipped - will run on-demand when user requests it")

        # Ejecutar pipeline
        llm_function = get_llm_function()

        # Ejecutar auditoría local directamente
        # run_local_audit returns a tuple (result, error), we only need the result for the pipeline.
        target_audit_result, _ = await AuditLocalService.run_local_audit(str(audit.url))
        if not target_audit_result:
            raise Exception("Local audit failed to produce results.")

        # Enriquecer con mercado/idioma/dominio si no vienen en el resumen
        if isinstance(target_audit_result, dict):
            target_audit_result["language"] = "en"
            if audit.market and not target_audit_result.get("market"):
                target_audit_result["market"] = audit.market
            if audit.domain and not target_audit_result.get("domain"):
                target_audit_result["domain"] = audit.domain

        from app.services.pipeline_service import run_initial_audit

        result = await run_initial_audit(
            url=str(audit.url),
            target_audit=target_audit_result,
            audit_id=audit_id,
            llm_function=llm_function,
            google_api_key=settings.GOOGLE_API_KEY,
            google_cx_id=settings.CSE_ID,
            crawler_service=CrawlerService.crawl_site,
            audit_local_service=AuditLocalService.run_local_audit,
            generate_report=False,
            enable_llm_external_intel=False,
        )

        # Guardar resultados
        report_markdown = result.get("report_markdown", "")
        fix_plan = result.get("fix_plan", [])
        target_audit = result.get("target_audit", {})
        external_intelligence = result.get("external_intelligence", {})
        search_results = result.get("search_results", {})
        competitor_audits = result.get("competitor_audits", [])

        await AuditService.set_audit_results(
            db=db,
            audit_id=audit_id,
            target_audit=target_audit,
            external_intelligence=external_intelligence,
            search_results=search_results,
            competitor_audits=competitor_audits,
            report_markdown=report_markdown,
            fix_plan=fix_plan,
            pagespeed_data=None,  # Not collected during initial audit
        )

        AuditService.update_audit_progress(
            db=db, audit_id=audit_id, progress=100, status=AuditStatus.COMPLETED
        )
        logger.info(f"Audit {audit_id} completed successfully (sync mode)")
        logger.info(
            f"Dashboard ready! PDF can be generated manually from the dashboard."
        )

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


async def _create_audit_internal(
    audit_create: AuditCreate,
    response: Response,
    background_tasks: BackgroundTasks,
    db: Session,
):
    """
    Función interna para crear auditoría.
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

    response.headers["Location"] = f"/api/audits/{audit.id}"
    return audit


@router.post(
    "",
    response_model=AuditResponse,
    status_code=status.HTTP_202_ACCEPTED,
    include_in_schema=False,
)
@router.post("/", response_model=AuditResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_audit(
    audit_create: AuditCreate,
    response: Response,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Crea auditoría. Si tiene competitors/market, inicia pipeline.
    Si no, solo crea registro (espera configuración de chat).

    NOTE: PageSpeed is NOT collected here. It runs when user:
    - Clicks "Analyze PageSpeed" button
    - Generates the full PDF report
    This keeps audit creation fast and responsive.

    Acepta tanto /api/audits como /api/audits/ para evitar redirecciones 307.
    """
    return await _create_audit_internal(audit_create, response, background_tasks, db)


@router.get("", response_model=List[AuditSummary], include_in_schema=False)
@router.get("/", response_model=List[AuditSummary])
def list_audits(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    user_email: str = None,  # Optional filter by user email
) -> List[Audit]:
    """
    Lista auditorías con paginación.
    Si se proporciona user_email, filtra solo las auditorías de ese usuario.
    """
    audits = AuditService.get_audits(db, skip=skip, limit=limit, user_email=user_email)
    return audits


@router.get("/{audit_id}/status", response_model=AuditSummary)
@router.get("/{audit_id}/progress", response_model=AuditSummary)
def get_audit_status(audit_id: int, db: Session = Depends(get_db)):
    """
    Get lightweight audit status for polling.
    Only returns id, url, status, progress, geo_score, and total_pages.
    """
    audit = AuditService.get_audit(db, audit_id)
    if not audit:
        raise HTTPException(status_code=404, detail="Auditoría no encontrada")
    return audit


@router.get("/{audit_id}", response_model=AuditResponse)
def get_audit(audit_id: int, db: Session = Depends(get_db)):
    """
    Get audit details WITHOUT triggering PageSpeed or GEO tools.

    This endpoint loads quickly and returns basic audit information and fix plan.
    Frontend should display "Generate PDF" for full analysis.
    """
    audit = AuditService.get_audit(db, audit_id)
    if not audit:
        raise HTTPException(status_code=404, detail="Auditoría no encontrada")

    # Load audited pages (fast operation)
    pages = AuditService.get_audited_pages(db, audit_id)
    audit.pages = pages

    # Recalcular GEO score si hay datos suficientes (evita valores falsos)
    if isinstance(audit.target_audit, dict):
        try:
            from app.services.audit_service import CompetitorService
            recalculated = CompetitorService._calculate_geo_score(audit.target_audit)
            if recalculated is not None:
                if (audit.geo_score is None or audit.geo_score <= 0) and recalculated >= 0:
                    audit.geo_score = recalculated
                    db.commit()
                elif recalculated > 0 and audit.geo_score != recalculated:
                    # Actualiza si la nueva métrica es más precisa
                    audit.geo_score = recalculated
                    db.commit()
        except Exception as e:
            logger.warning(f"No se pudo recalcular GEO score para audit {audit_id}: {e}")

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

    if not audit.report_markdown:
        raise HTTPException(
            status_code=404,
            detail="Report not generated. Generate PDF first.",
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

    if not audit.fix_plan:
        return {
            "fix_plan": [],
            "message": "Fix plan is generated when you create the PDF report.",
        }

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
            "audit_data": p.audit_data,
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
        "audit_data": page.audit_data,
    }


@router.get("/{audit_id}/competitors", response_model=list)
def get_competitors(audit_id: int, limit: int = 10, db: Session = Depends(get_db)):
    """
    Obtiene datos de competidores de una auditoría con GEO scores calculados.
    Limitado a 10 por defecto para evitar memory issues.
    """
    from app.services.audit_service import CompetitorService

    audit = AuditService.get_audit(db, audit_id)
    if not audit:
        raise HTTPException(status_code=404, detail="Auditoría no encontrada")

    if audit.status != AuditStatus.COMPLETED:
        # Avoid 400s during long-running audits; return empty list until completed.
        return []

    # Obtener competidores de la base de datos (con límite)
    competitors_db = (
        db.query(Competitor).filter(Competitor.audit_id == audit_id).limit(limit).all()
    )

    # Si hay competidores en la BD, usarlos
    if competitors_db:
        result = []
        for comp in competitors_db:
            audit_data = comp.audit_data or {}
            geo_score = CompetitorService._calculate_geo_score(audit_data) if audit_data else (comp.geo_score or 0)
            if geo_score == 0 and comp.geo_score:
                geo_score = comp.geo_score
            formatted = CompetitorService._format_competitor_data(
                audit_data, geo_score, comp.url
            )
            result.append(formatted)
        return result

    # Fallback: usar competitor_audits del JSON (con límite)
    competitors = (audit.competitor_audits or [])[:limit]
    result = []
    for comp in competitors:
        if isinstance(comp, dict):
            geo_score = CompetitorService._calculate_geo_score(comp)
            if geo_score == 0:
                geo_score = comp.get("geo_score", 0) or 0
            formatted = CompetitorService._format_competitor_data(comp, geo_score)
            result.append(formatted)

    return result


@router.post("/{audit_id}/run-pagespeed")
@router.post("/{audit_id}/pagespeed")
async def run_pagespeed_analysis(
    audit_id: int, strategy: str = "both", db: Session = Depends(get_db)
):
    """
    Manually trigger PageSpeed analysis and return COMPLETE data.

    This endpoint is called when user clicks "Run PageSpeed" button.
    Returns the full PageSpeed Insights output with all metrics, opportunities,
    diagnostics, accessibility, SEO, and best practices audits.

    Args:
        audit_id: Audit ID
        strategy: "mobile", "desktop", or "both" (default)

    Returns:
        Complete PageSpeed data structure with all fields
    """
    from app.services.pagespeed_service import PageSpeedService
    import asyncio

    audit = AuditService.get_audit(db, audit_id)
    if not audit:
        raise HTTPException(status_code=404, detail="Auditoría no encontrada")

    try:
        logger.info(
            f"Manual PageSpeed analysis triggered for audit {audit_id}, strategy: {strategy}"
        )
        logger.info(f"Audit URL: {audit.url}")
        logger.info(f"API Key present: {bool(settings.GOOGLE_PAGESPEED_API_KEY)}")

        if strategy == "both":
            # Run both strategies
            logger.info("Running mobile analysis...")
            mobile = await PageSpeedService.analyze_url(
                url=str(audit.url),
                api_key=settings.GOOGLE_PAGESPEED_API_KEY,
                strategy="mobile",
            )
            logger.info(
                f"Mobile analysis completed. Keys: {list(mobile.keys()) if mobile else 'None'}"
            )

            # Reduced sleep if API key is present
            sleep_time = 0.5 if settings.GOOGLE_PAGESPEED_API_KEY else 3
            await asyncio.sleep(sleep_time)

            logger.info("Running desktop analysis...")
            desktop = await PageSpeedService.analyze_url(
                url=str(audit.url),
                api_key=settings.GOOGLE_PAGESPEED_API_KEY,
                strategy="desktop",
            )
            logger.info(
                f"Desktop analysis completed. Keys: {list(desktop.keys()) if desktop else 'None'}"
            )
            pagespeed_data = {"mobile": mobile, "desktop": desktop}
        else:
            # Run single strategy
            logger.info(f"Running {strategy} analysis...")
            result = await PageSpeedService.analyze_url(
                url=str(audit.url),
                api_key=settings.GOOGLE_PAGESPEED_API_KEY,
                strategy=strategy,
            )
            logger.info(
                f"{strategy.capitalize()} analysis completed. Keys: {list(result.keys()) if result else 'None'}"
            )
            pagespeed_data = {strategy: result}

        # Store complete data in database
        logger.info(f"Storing PageSpeed data in database...")
        AuditService.set_pagespeed_data(db, audit_id, pagespeed_data)

        logger.info(f"PageSpeed analysis completed for audit {audit_id}")

        # Return COMPLETE data to frontend
        return {
            "success": True,
            "data": pagespeed_data,  # Full structure with all fields
            "message": "PageSpeed analysis completed",
            "strategies_analyzed": list(pagespeed_data.keys()),
        }
    except Exception as e:
        logger.error(
            f"PageSpeed analysis failed for audit {audit_id}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=500, detail=f"Error analyzing PageSpeed: {str(e)}"
        )


@router.post("/{audit_id}/generate-pdf")
async def generate_audit_pdf(
    audit_id: int,
    force_pagespeed_refresh: bool = False,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
):
    """
    Generate PDF report with automatic PageSpeed analysis.

    This endpoint automatically triggers PageSpeed analysis if:
    - No PageSpeed data exists
    - Cached PageSpeed data is stale (>24 hours old)
    - force_pagespeed_refresh is True

    The PDF includes complete context from ALL features:
    - PageSpeed (mobile + desktop)
    - Keywords
    - Backlinks
    - Rank tracking
    - LLM visibility
    - AI content suggestions
    """
    from app.services.pdf_service import PDFService
    from app.models import Report

    audit = AuditService.get_audit(db, audit_id)
    if not audit:
        raise HTTPException(status_code=404, detail="Auditoría no encontrada")

    if audit.status != AuditStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"La auditoría debe estar completada. Estado actual: {audit.status.value}",
        )

    try:
        logger.info(
            f"=== Starting PDF generation with auto-PageSpeed for audit {audit_id} ==="
        )

        # Generate PDF with complete context (includes auto-PageSpeed trigger)
        pdf_path = await PDFService.generate_pdf_with_complete_context(
            db=db, audit_id=audit_id, force_pagespeed_refresh=force_pagespeed_refresh
        )

        if not pdf_path or not os.path.exists(pdf_path):
            raise Exception(f"PDF generation failed - file not created at {pdf_path}")

        # Get file size
        file_size = os.path.getsize(pdf_path)

        # Save PDF path to Report table
        existing_report = (
            db.query(Report)
            .filter(Report.audit_id == audit_id, Report.report_type == "PDF")
            .first()
        )

        if existing_report:
            # Update existing report
            existing_report.file_path = pdf_path
            existing_report.file_size = file_size
            existing_report.created_at = datetime.now()
            logger.info(f"Updated existing PDF report entry")
        else:
            # Create new report entry
            pdf_report = Report(
                audit_id=audit_id,
                report_type="PDF",
                file_path=pdf_path,
                file_size=file_size,
            )
            db.add(pdf_report)
            logger.info(f"Created new PDF report entry")

        db.commit()

        # Refresh audit to get updated pagespeed_data
        db.refresh(audit)

        logger.info(f"=== PDF generation completed successfully ===")
        logger.info(f"PDF saved at: {pdf_path}")
        logger.info(f"PDF size: {file_size} bytes")

        return {
            "success": True,
            "pdf_path": pdf_path,
            "message": "PDF generated successfully with PageSpeed data",
            "pagespeed_included": bool(audit.pagespeed_data),
            "file_size": file_size,
        }

    except Exception as e:
        logger.error(f"=== Error generating PDF for audit {audit_id} ===")
        logger.error(f"Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error generating PDF: {str(e)}")


@router.get("/{audit_id}/download-pdf")
def download_audit_pdf(audit_id: int, db: Session = Depends(get_db)):
    """
    Descarga el PDF de una auditoría completada.
    Si el PDF no existe, sugiere generarlo primero.
    """
    from fastapi.responses import FileResponse
    from app.models import Report

    audit = AuditService.get_audit(db, audit_id)
    if not audit:
        raise HTTPException(status_code=404, detail="Auditoría no encontrada")

    if audit.status != AuditStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"El PDF aún no está listo. Estado actual: {audit.status.value}",
        )

    # Get PDF path from Report table
    pdf_report = (
        db.query(Report)
        .filter(Report.audit_id == audit_id, Report.report_type == "PDF")
        .order_by(Report.created_at.desc())
        .first()
    )

    if not pdf_report or not pdf_report.file_path:
        raise HTTPException(
            status_code=404,
            detail="El archivo PDF no existe. Por favor, genera el PDF primero usando POST /api/audits/{audit_id}/generate-pdf",
        )

    pdf_path = pdf_report.file_path

    # Handle both relative and absolute paths
    if not os.path.isabs(pdf_path):
        # If relative, make it absolute from current working directory
        pdf_path = os.path.abspath(pdf_path)

    logger.info(f"Attempting to download PDF from: {pdf_path}")
    logger.info(f"File exists: {os.path.exists(pdf_path)}")

    if not os.path.exists(pdf_path):
        # Try alternative path - maybe it's in /app directory
        alt_path = os.path.join("/app", pdf_report.file_path)
        logger.info(f"Trying alternative path: {alt_path}")
        if os.path.exists(alt_path):
            pdf_path = alt_path
            logger.info(f"Found PDF at alternative path")
        else:
            raise HTTPException(
                status_code=404,
                detail=f"El archivo PDF no existe en {pdf_path} ni en {alt_path}. Por favor, genera el PDF primero.",
            )

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=f"audit_{audit_id}_report.pdf",
    )


@router.post("/chat/config", response_model=ChatMessage)
async def configure_audit_chat(
    config: AuditConfigRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Configura auditoría y lanza pipeline.
    """
    audit = AuditService.get_audit(db, config.audit_id)
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")

    # Prevenir doble ejecución si ya está en curso
    if audit.status in [AuditStatus.RUNNING, AuditStatus.COMPLETED]:
        logger.warning(
            f"Audit {audit.id} already {audit.status}. Skipping duplicate trigger."
        )
        return ChatMessage(
            role="assistant", content="This audit is already in progress or completed."
        )

    audit.language = "en"
    if config.competitors:
        audit.competitors = config.competitors
    if config.market:
        audit.market = config.market

    try:
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
            role="assistant", content="Configuration saved. Starting audit..."
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error saving audit configuration: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error saving configuration: {str(e)}"
        )


# DEPRECATED: Old GitHub integration endpoint
# This functionality is now handled by /api/github/ endpoints
# See: backend/app/api/routes/github.py

# class GitHubFixRequest(BaseModel):
#     repo_full_name: str
#     base_branch: str = "main"

# @router.post("/{audit_id}/github/create-fix", status_code=status.HTTP_201_CREATED)
# async def create_github_fix(...):
#     # This endpoint has been superseded by the new GitHub integration
#     # Use /api/github/create-auto-fix-pr/{connection_id}/{repo_id} instead
