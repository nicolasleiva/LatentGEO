from typing import List
from urllib.parse import urlparse

from app.core.access_control import ensure_artifact_snapshot_access, ensure_audit_access
from app.core.auth import AuthUser, get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.logger import get_logger
from app.models import Audit, AuditPageSpeedJob, AuditStatus, Competitor
from app.schemas import (
    AuditConfigRequest,
    AuditArtifactsStatusResponse,
    AuditCreate,
    AuditOverview,
    AuditPageSpeedStatusResponse,
    AuditPDFStatusResponse,
    AuditResponse,
    AuditSummary,
    ChatMessage,
    PDFDownloadUrlResponse,
)
from app.services.audit_local_service import AuditLocalService
from app.services.audit_service import AuditService
from app.services.pagespeed_job_service import (
    DEFAULT_PAGESPEED_RETRY_AFTER_SECONDS,
    PageSpeedJobService,
)
from app.services.competitor_filters import (
    infer_vertical_hint,
    is_valid_competitor_domain,
    normalize_domain,
)
from app.services.pdf_job_service import (
    DEFAULT_PDF_RETRY_AFTER_SECONDS,
    PDFJobService,
    _pdf_generation_in_progress,
    _pdf_generation_tokens,
    acquire_pdf_generation_lock as _acquire_pdf_generation_lock,
    pdf_lock_key as _pdf_lock_key,
    release_pdf_generation_lock as _release_pdf_generation_lock,
)
from app.services.pipeline_service import PipelineService

# Importar la tarea de Celery
from app.workers.tasks import run_audit_task
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.orm import Session

logger = get_logger(__name__)

router = APIRouter(
    prefix="/audits",
    tags=["audits"],
    responses={404: {"description": "No encontrado"}},
)


def _get_owned_audit(db: Session, audit_id: int, current_user: AuthUser) -> Audit:
    audit = AuditService.get_audit(db, audit_id)
    return ensure_audit_access(audit, current_user)


def _artifact_status_retry_after(source: str, active_retry_after_seconds: int) -> int:
    if source == "redis":
        return active_retry_after_seconds
    degraded_retry = max(
        active_retry_after_seconds,
        int(getattr(settings, "ARTIFACT_STATUS_DEGRADED_RETRY_AFTER_SECONDS", 10)),
    )
    return degraded_retry if active_retry_after_seconds > 0 else 0


def _get_owned_artifact_payload(
    db: Session,
    audit_id: int,
    current_user: AuthUser,
) -> tuple[dict, str]:
    cached_payload = AuditService.get_cached_artifact_payload(audit_id)
    if cached_payload is not None:
        ensure_artifact_snapshot_access(cached_payload, current_user)
        return cached_payload, "redis"

    rebuilt_payload = AuditService.rebuild_artifact_payload(db, audit_id)
    if rebuilt_payload is None:
        raise HTTPException(status_code=404, detail="Auditoría no encontrada")

    ensure_artifact_snapshot_access(rebuilt_payload, current_user)
    return rebuilt_payload, "db"


def _db_unavailable_http_exception(action: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "error_code": "db_unavailable",
            "action": action,
            "message": "Database is temporarily unavailable. Retry in a few seconds.",
        },
    )


def _persist_runtime_diagnostic_safely(
    db: Session,
    audit_id: int,
    *,
    source: str,
    stage: str,
    severity: str,
    code: str,
    message: str,
    technical_detail: str | None = None,
) -> None:
    PDFJobService.persist_runtime_diagnostic_safely(
        db,
        audit_id,
        source=source,
        stage=stage,
        severity=severity,
        code=code,
        message=message,
        technical_detail=technical_detail,
    )


def _persist_generation_warnings(
    db: Session, audit_id: int, warnings: list[str]
) -> None:
    PDFJobService.persist_generation_warnings(db, audit_id, warnings)


def _runtime_technical_detail(exc: Exception) -> str | None:
    return PDFJobService.runtime_technical_detail(exc)


def _pdf_requires_pagespeed_refresh(
    audit: Audit,
    *,
    force_pagespeed_refresh: bool,
    pagespeed_job: AuditPageSpeedJob | None,
) -> bool:
    if not settings.ENABLE_PAGESPEED or not settings.GOOGLE_PAGESPEED_API_KEY:
        return False
    if force_pagespeed_refresh:
        return True
    if pagespeed_job is not None and PageSpeedJobService.has_active_job(pagespeed_job):
        return True
    if pagespeed_job is not None and pagespeed_job.status in {"completed", "failed"}:
        return False
    return not PageSpeedJobService.has_usable_pagespeed_data(
        audit,
        require_complete=True,
    )


async def _resolve_signed_pdf_download_url(
    audit_id: int,
    db: Session,
    current_user: AuthUser,
) -> tuple[str, str]:
    from app.models import Report
    from app.services.pdf_service import PDFService
    from app.services.supabase_service import SupabaseService

    try:
        audit = _get_owned_audit(db, audit_id, current_user)

        if audit.status != AuditStatus.COMPLETED:
            raise HTTPException(
                status_code=400,
                detail=f"El PDF aún no está listo. Estado actual: {audit.status.value}",
            )

        pdf_report = (
            db.query(Report)
            .filter(Report.audit_id == audit_id, Report.report_type == "PDF")
            .order_by(Report.created_at.desc())
            .first()
        )

        if not pdf_report or not pdf_report.file_path:
            raise HTTPException(
                status_code=404,
                detail="El archivo PDF no existe. Por favor, genera el PDF primero usando POST /api/v1/audits/{audit_id}/generate-pdf",
            )

        if not str(pdf_report.file_path).startswith("supabase://"):
            pdf_report = await PDFService.ensure_supabase_pdf_report(
                db=db,
                audit=audit,
                report=pdf_report,
            )

        pdf_path = str(pdf_report.file_path)
    except HTTPException:
        raise
    except (OperationalError, DBAPIError) as db_err:
        logger.error(
            f"download_pdf_db_failed audit_id={audit_id} error_code=db_unavailable error={db_err}"
        )
        raise _db_unavailable_http_exception("download_pdf_lookup") from db_err

    storage_path = pdf_path.replace("supabase://", "", 1)
    try:
        signed_url = SupabaseService.get_signed_url(
            bucket=settings.SUPABASE_STORAGE_BUCKET,
            path=storage_path,
        )
    except Exception as exc:
        logger.error(
            f"storage_provider=supabase audit_id={audit_id} action=download_pdf_failed error_code=supabase_signed_url_failed error={exc}"
        )
        raise HTTPException(
            status_code=500,
            detail="No se pudo generar el enlace de descarga de Supabase.",
        ) from exc

    return signed_url, storage_path


async def run_audit_sync(audit_id: int):
    """
    Función auxiliar para ejecutar auditoría de forma síncrona como fallback.
    PageSpeed is NOT run here - it's executed on-demand when user requests it.
    """
    from app.core.database import SessionLocal
    from app.core.llm_kimi import get_llm_function

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
            target_audit_result["language"] = audit.language or "en"
            if audit.market and not target_audit_result.get("market"):
                target_audit_result["market"] = audit.market
            if audit.domain and not target_audit_result.get("domain"):
                target_audit_result["domain"] = audit.domain

        from app.services.crawler_service import CrawlerService
        from app.services.pipeline_service import run_initial_audit

        result = await run_initial_audit(
            url=str(audit.url),
            target_audit=target_audit_result,
            audit_id=audit_id,
            llm_function=llm_function,
            google_api_key=None,
            google_cx_id=None,
            crawler_service=CrawlerService.crawl_site,
            audit_local_service=AuditLocalService.run_local_audit,
            generate_report=False,
            enable_llm_external_intel=True,
            external_intel_mode="full",
            external_intel_timeout_seconds=30.0,
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
            "Dashboard ready! PDF can be generated manually from the dashboard."
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
    # Run sync database operation in threadpool
    from starlette.concurrency import run_in_threadpool

    try:
        audit = await run_in_threadpool(AuditService.create_audit, db, audit_create)
    except (OperationalError, DBAPIError) as db_err:
        logger.error(
            "create_audit_db_failed " f"error_code=db_unavailable error={db_err}"
        )
        raise _db_unavailable_http_exception("create_audit") from db_err

    # Solo iniciar pipeline si tiene configuración completa
    if audit_create.competitors or audit_create.market:
        try:
            task = run_audit_task.delay(audit.id)
            AuditService.set_audit_task_id(db, audit.id, task.id)
            logger.info(f"Audit {audit.id} queued with config")
        except Exception as e:
            logger.warning(f"Celery unavailable: {e}")
            if settings.DEBUG:
                background_tasks.add_task(run_audit_sync, audit.id)
            else:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Background worker unavailable. Try again shortly.",
                )
    else:
        logger.info(f"Audit {audit.id} created, waiting for chat config")

    response.headers["Location"] = f"/api/v1/audits/{audit.id}"
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
    current_user: AuthUser = Depends(get_current_user),
):
    """
    Crea auditoría. Si tiene competitors/market, inicia pipeline.
    Si no, solo crea registro (espera configuración de chat).

    NOTE: PageSpeed is NOT collected here. It runs when user:
    - Clicks "Analyze PageSpeed" button
    - Generates the full PDF report
    This keeps audit creation fast and responsive.

    Acepta tanto /api/v1/audits como /api/v1/audits/ para evitar redirecciones 307.
    """
    # Do not trust ownership from request body.
    audit_create.user_id = current_user.user_id
    audit_create.user_email = current_user.email
    return await _create_audit_internal(audit_create, response, background_tasks, db)


@router.get("", response_model=List[AuditSummary], include_in_schema=False)
@router.get("/", response_model=List[AuditSummary])
def list_audits(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: AuthUser = Depends(get_current_user),
) -> List[Audit]:
    """
    Lista auditorías con paginación.
    Si se proporciona user_email, filtra solo las auditorías de ese usuario.
    """
    audits = AuditService.get_audits(
        db,
        skip=skip,
        limit=limit,
        user_email=current_user.email,
        user_id=current_user.user_id,
    )
    return audits


@router.get("/{audit_id}/status", response_model=AuditSummary)
@router.get("/{audit_id}/progress", response_model=AuditSummary)
def get_audit_status(
    audit_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """
    Get lightweight audit status for polling.
    Only returns id, url, status, progress, geo_score, and total_pages.
    """
    audit = _get_owned_audit(db, audit_id, current_user)
    return audit


@router.get("/{audit_id}/overview", response_model=AuditOverview)
def get_audit_overview(
    audit_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """
    Get a production-friendly overview payload for the audit detail shell.
    Excludes heavy JSON blobs such as target_audit, report_markdown, and fix_plan.
    """
    from app.services.audit_service import CompetitorService

    audit = _get_owned_audit(db, audit_id, current_user)

    fix_plan = audit.fix_plan if isinstance(audit.fix_plan, list) else []
    external_intelligence = (
        audit.external_intelligence
        if isinstance(audit.external_intelligence, dict)
        else None
    )
    pagespeed_job = PageSpeedJobService.get_job(db, audit_id)
    pdf_job = PDFJobService.get_job(db, audit_id)
    latest_pdf_report = PDFJobService.get_latest_pdf_report(db, audit_id)
    competitor_count = (
        db.query(Competitor).filter(Competitor.audit_id == audit_id).count()
    )
    if competitor_count <= 0:
        competitor_count = len(
            [
                comp
                for comp in (audit.competitor_audits or [])
                if CompetitorService.is_benchmark_available_competitor(comp)
            ]
        )
    return AuditOverview(
        id=audit.id,
        url=audit.url,
        domain=audit.domain,
        status=(
            audit.status.value if hasattr(audit.status, "value") else str(audit.status)
        ),
        progress=int(round(audit.progress or 0)),
        created_at=audit.created_at,
        started_at=audit.started_at,
        completed_at=audit.completed_at,
        geo_score=audit.geo_score,
        total_pages=audit.total_pages,
        critical_issues=audit.critical_issues,
        high_issues=audit.high_issues,
        medium_issues=audit.medium_issues,
        source=audit.source,
        language=audit.language,
        category=audit.category,
        market=audit.market,
        intake_profile=audit.intake_profile,
        diagnostics_summary=AuditService.summarize_runtime_diagnostics(
            audit.runtime_diagnostics, limit=4
        ),
        odoo_connection_id=getattr(audit, "odoo_connection_id", None),
        error_message=audit.error_message,
        competitor_count=competitor_count,
        fix_plan_count=len(fix_plan),
        report_ready=bool(audit.report_markdown),
        pagespeed_available=bool(audit.pagespeed_data),
        pagespeed_status=(pagespeed_job.status if pagespeed_job else None),
        pagespeed_warnings=PageSpeedJobService.normalize_warnings(
            getattr(pagespeed_job, "warnings", [])
        ),
        pdf_available=bool(latest_pdf_report and latest_pdf_report.file_path),
        pdf_status=(pdf_job.status if pdf_job else None),
        pdf_warnings=PDFJobService.normalize_warnings(getattr(pdf_job, "warnings", [])),
        external_intelligence=external_intelligence,
    )


@router.get("/{audit_id}/diagnostics", response_model=dict)
def get_audit_diagnostics(
    audit_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    audit = _get_owned_audit(db, audit_id, current_user)
    diagnostics = AuditService.summarize_runtime_diagnostics(
        audit.runtime_diagnostics,
        limit=AuditService.MAX_RUNTIME_DIAGNOSTICS,
    )
    return {
        "audit_id": audit.id,
        "diagnostics": diagnostics,
    }


@router.get("/{audit_id}", response_model=AuditResponse)
def get_audit(
    audit_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """
    Get audit details WITHOUT triggering PageSpeed or GEO tools.

    This endpoint loads quickly and returns basic audit information and fix plan.
    Frontend should display "Generate PDF" for full analysis.
    """
    audit = _get_owned_audit(db, audit_id, current_user)
    return audit


@router.get("/{audit_id}/report", response_model=dict)
def get_audit_report(
    audit_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """
    Devuelve el reporte en Markdown de una auditoría completada.
    """
    audit = _get_owned_audit(db, audit_id, current_user)

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
def get_audit_fix_plan(
    audit_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """
    Devuelve el plan de correcciones (fix plan) en JSON.
    """
    audit = _get_owned_audit(db, audit_id, current_user)

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
def delete_audit(
    audit_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """
    Elimina una auditoría de la base de datos.
    """
    _get_owned_audit(db, audit_id, current_user)
    success = AuditService.delete_audit(db, audit_id)
    if not success:
        raise HTTPException(status_code=404, detail="Auditoría no encontrada")
    return


@router.get("/status/{status}", response_model=List[AuditSummary])
def get_audits_by_status(
    status: AuditStatus,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
) -> List[Audit]:
    """
    Filtra auditorías por su estado (pending, processing, completed, failed).
    """
    audits = AuditService.get_audits_by_status(
        db,
        status,
        user_email=current_user.email,
        user_id=current_user.user_id,
    )
    return audits


@router.get("/stats/summary", response_model=dict)
def get_audits_summary(
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """
    Obtiene estadísticas generales sobre las auditorías.
    """
    stats = AuditService.get_stats_summary(
        db,
        user_email=current_user.email,
        user_id=current_user.user_id,
    )
    return stats


@router.get("/{audit_id}/pages", response_model=list)
def get_audit_pages(
    audit_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """
    Obtiene todas las páginas auditadas de una auditoría.
    """
    _get_owned_audit(db, audit_id, current_user)

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
def get_page_details(
    audit_id: int,
    page_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """
    Obtiene detalles de una página específica.
    """
    _get_owned_audit(db, audit_id, current_user)

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
def get_competitors(
    audit_id: int,
    limit: int = 5,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """
    Obtiene datos de competidores de una auditoría con GEO scores calculados.
    Limitado a 10 por defecto para evitar memory issues.
    """
    from app.services.audit_service import CompetitorService

    audit = _get_owned_audit(db, audit_id, current_user)

    if audit.status != AuditStatus.COMPLETED:
        # Avoid 400s during long-running audits; return empty list until completed.
        return []

    safe_limit = max(1, min(int(limit), 10))
    target_audit = audit.target_audit if isinstance(audit.target_audit, dict) else {}
    external_intelligence = (
        audit.external_intelligence
        if isinstance(audit.external_intelligence, dict)
        else {}
    )
    vertical_hint = infer_vertical_hint(
        external_intelligence.get("category"),
        external_intelligence.get("subcategory"),
        target_audit.get("category"),
        target_audit.get("subcategory"),
        audit.category,
    )

    def _is_valid_domain(url_or_domain: str) -> bool:
        domain = normalize_domain(url_or_domain)
        return bool(domain) and is_valid_competitor_domain(domain, vertical_hint)

    # Obtener competidores de la base de datos (con límite)
    competitors_db = (
        db.query(Competitor)
        .filter(Competitor.audit_id == audit_id)
        .limit(safe_limit)
        .all()
    )

    # Si hay competidores en la BD, usarlos
    if competitors_db:
        result = []
        for comp in competitors_db:
            if not _is_valid_domain(comp.url or comp.domain or ""):
                continue
            audit_data = comp.audit_data or {}
            if not CompetitorService.is_benchmark_available_competitor(audit_data):
                continue
            normalized_comp = CompetitorService.normalize_competitor_audit_payload(
                audit_data
            )
            geo_score = normalized_comp.get("geo_score", comp.geo_score or 0)
            formatted = CompetitorService._format_competitor_data(
                normalized_comp,
                geo_score,
                comp.url,
                score_meta=(
                    normalized_comp.get("benchmark")
                    if isinstance(normalized_comp.get("benchmark"), dict)
                    else None
                ),
                benchmark_available=True,
            )
            result.append(formatted)
            if len(result) >= safe_limit:
                break
        if result:
            return result

    # Fallback: usar competitor_audits del JSON (con límite)
    competitors = (audit.competitor_audits or [])[:safe_limit]
    result = []
    for comp in competitors:
        if isinstance(comp, dict):
            if not _is_valid_domain(comp.get("url") or comp.get("domain") or ""):
                continue
            if not CompetitorService.is_benchmark_available_competitor(comp):
                continue
            normalized_comp = CompetitorService.normalize_competitor_audit_payload(comp)
            geo_score = normalized_comp.get("geo_score", 0) or 0
            formatted = CompetitorService._format_competitor_data(
                normalized_comp,
                geo_score,
                score_meta=(
                    normalized_comp.get("benchmark")
                    if isinstance(normalized_comp.get("benchmark"), dict)
                    else None
                ),
                benchmark_available=True,
            )
            result.append(formatted)
            if len(result) >= safe_limit:
                break

    if result:
        return result

    # Último fallback: derivar competidores desde search_results existentes.
    # Útil para auditorías históricas que quedaron sin competitor_audits por filtros previos.
    try:
        search_results = (
            audit.search_results if isinstance(audit.search_results, dict) else {}
        )

        target_domain = (audit.domain or "").replace("www.", "").strip().lower()
        if not target_domain:
            target_domain = (
                urlparse(str(audit.url or "")).netloc.replace("www.", "").lower()
            )

        core_profile = PipelineService._build_core_business_profile(
            target_audit, max_terms=6
        )
        inferred_urls = PipelineService._extract_competitor_urls_from_search(
            search_results=search_results,
            target_domain=target_domain,
            target_audit=target_audit,
            external_intelligence=external_intelligence,
            core_profile=core_profile,
            limit=safe_limit,
        )

        for comp_url in inferred_urls:
            if not _is_valid_domain(comp_url):
                continue
            inferred_domain = urlparse(comp_url).netloc.replace("www.", "")
            formatted = CompetitorService._format_competitor_data(
                {"url": comp_url, "domain": inferred_domain, "status": "inferred"},
                0.0,
                comp_url,
            )
            formatted["source"] = "derived_from_search_results"
            result.append(formatted)
            if len(result) >= safe_limit:
                break
    except Exception as e:
        logger.warning(
            f"Could not derive competitors from search_results for audit {audit_id}: {e}"
        )

    return result


@router.post("/{audit_id}/run-pagespeed")
@router.post("/{audit_id}/pagespeed")
async def run_pagespeed_analysis(
    audit_id: int,
    strategy: str = "both",
    force_refresh: bool = False,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """
    Queue or reuse the canonical PageSpeed job for an audit.
    """
    audit = _get_owned_audit(db, audit_id, current_user)
    if audit.status != AuditStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"La auditoría debe estar completada. Estado actual: {audit.status.value}",
        )

    try:
        existing_job = PageSpeedJobService.get_job(db, audit.id)
        if PageSpeedJobService.has_active_job(existing_job):
            response = PageSpeedJobService.build_status_response(
                audit=audit,
                job=existing_job,
                retry_after_seconds=DEFAULT_PAGESPEED_RETRY_AFTER_SECONDS,
                message="PageSpeed analysis is already in progress for this audit.",
            )
            return JSONResponse(status_code=202, content=response.model_dump(mode="json"))

        if (
            not force_refresh
            and PageSpeedJobService.has_usable_pagespeed_data(
                audit,
                require_complete=(strategy == "both"),
            )
        ):
            response = PageSpeedJobService.build_status_response(
                audit=audit,
                job=existing_job if existing_job and existing_job.status == "completed" else None,
                message="Existing PageSpeed data is already available.",
            )
            return JSONResponse(status_code=200, content=response.model_dump(mode="json"))

        job = PageSpeedJobService.queue_job(
            db,
            audit=audit,
            requested_by_user_id=current_user.user_id,
            strategy=strategy,
            force_refresh=force_refresh,
        )
        try:
            job = PageSpeedJobService.enqueue_job_task(db, audit, job)
        except Exception as exc:
            logger.error(
                "pagespeed_queue_failed audit_id=%s job_id=%s error=%s",
                audit.id,
                job.id,
                exc,
            )
            error_code, error_message = PageSpeedJobService.classify_error(exc)
            PageSpeedJobService.mark_job_failed(
                db,
                audit,
                job,
                error_code="worker_unavailable",
                error_message=error_message or error_code,
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error_code": "worker_unavailable",
                    "message": "Background worker unavailable. Try again shortly.",
                },
            ) from exc

        response = PageSpeedJobService.build_status_response(
            audit=audit,
            job=job,
            retry_after_seconds=DEFAULT_PAGESPEED_RETRY_AFTER_SECONDS,
            message="PageSpeed analysis queued successfully.",
        )
        return JSONResponse(status_code=202, content=response.model_dump(mode="json"))
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"PageSpeed analysis failed for audit {audit_id}", exc_info=True)
        _persist_runtime_diagnostic_safely(
            db,
            audit_id,
            source="pagespeed",
            stage="run-pagespeed",
            severity="error",
            code="pagespeed_failed",
            message=(
                "PageSpeed analysis failed before performance data could be refreshed."
            ),
            technical_detail=_runtime_technical_detail(exc),
        )
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{audit_id}/pdf-status", response_model=AuditPDFStatusResponse)
async def get_audit_pdf_status(
    audit_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    try:
        artifact_payload, source = _get_owned_artifact_payload(
            db, audit_id, current_user
        )
    except (OperationalError, DBAPIError) as db_err:
        logger.error(
            "pdf_status_db_failed audit_id=%s error_code=db_unavailable error=%s",
            audit_id,
            db_err,
        )
        raise _db_unavailable_http_exception("pdf_status_lookup") from db_err

    payload = dict(artifact_payload)
    payload["pdf_retry_after_seconds"] = _artifact_status_retry_after(
        source,
        int(payload.get("pdf_retry_after_seconds") or 0),
    )
    message = (
        None
        if source == "redis"
        else "Artifact status served from database fallback while Redis snapshot is unavailable."
    )
    return PDFJobService.build_status_response_from_artifact_payload(
        payload,
        message=message,
    )


@router.get("/{audit_id}/artifacts-status", response_model=AuditArtifactsStatusResponse)
async def get_audit_artifacts_status(
    audit_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    try:
        artifact_payload, source = _get_owned_artifact_payload(
            db, audit_id, current_user
        )
    except (OperationalError, DBAPIError) as db_err:
        logger.error(
            "artifacts_status_db_failed audit_id=%s error_code=db_unavailable error=%s",
            audit_id,
            db_err,
        )
        raise _db_unavailable_http_exception("artifacts_status_lookup") from db_err

    payload = AuditService.public_artifact_payload(artifact_payload) or {
        "audit_id": audit_id
    }
    degraded_message = (
        "Artifact status served from database fallback while Redis snapshot is unavailable."
        if source != "redis"
        else None
    )
    payload["pdf_retry_after_seconds"] = _artifact_status_retry_after(
        source,
        int(payload.get("pdf_retry_after_seconds") or 0),
    )
    payload["pagespeed_retry_after_seconds"] = _artifact_status_retry_after(
        source,
        int(payload.get("pagespeed_retry_after_seconds") or 0),
    )
    payload["pdf_message"] = payload.get("pdf_message") or degraded_message
    payload["pagespeed_message"] = (
        payload.get("pagespeed_message") or degraded_message
    )
    return AuditArtifactsStatusResponse.model_validate(payload)


@router.post(
    "/{audit_id}/generate-pdf",
    response_model=AuditPDFStatusResponse,
)
async def generate_audit_pdf(
    audit_id: int,
    force_pagespeed_refresh: bool = False,
    force_report_refresh: bool = False,
    force_external_intel_refresh: bool = False,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """
    Generate PDF report with automatic PageSpeed analysis.

    This endpoint automatically triggers PageSpeed analysis if:
    - No PageSpeed data exists
    - Cached PageSpeed data is stale (>24 hours old)
    - force_pagespeed_refresh is True
    - force_report_refresh is True (forces report markdown regeneration)
    - force_external_intel_refresh is True (forces Agent 1 external intelligence refresh)

    The PDF includes complete context from ALL features:
    - PageSpeed (mobile + desktop)
    - Keywords
    - Backlinks
    - Rank tracking
    - LLM visibility
    - AI content suggestions
    """
    try:
        audit = _get_owned_audit(db, audit_id, current_user)
        if audit.status != AuditStatus.COMPLETED:
            raise HTTPException(
                status_code=400,
                detail=f"La auditoría debe estar completada. Estado actual: {audit.status.value}",
            )
    except HTTPException:
        raise
    except (OperationalError, DBAPIError) as db_err:
        logger.error(
            f"generate_pdf_precheck_failed audit_id={audit_id} error_code=db_unavailable error={db_err}"
        )
        raise _db_unavailable_http_exception("generate_pdf_precheck") from db_err

    try:
        existing_report = PDFJobService.get_latest_pdf_report(db, audit.id)
        existing_job = PDFJobService.get_job(db, audit.id)
        existing_pagespeed_job = PageSpeedJobService.get_job(db, audit.id)
        needs_pagespeed = _pdf_requires_pagespeed_refresh(
            audit,
            force_pagespeed_refresh=force_pagespeed_refresh,
            pagespeed_job=existing_pagespeed_job,
        )

        if (
            existing_report
            and existing_report.file_path
            and not force_pagespeed_refresh
            and not force_report_refresh
            and not force_external_intel_refresh
            and not PDFJobService.has_active_job(existing_job)
            and not needs_pagespeed
        ):
            response = PDFJobService.build_status_response(
                audit_id=audit.id,
                job=None,
                report=existing_report,
                message="Existing PDF is already available.",
            )
            return JSONResponse(status_code=200, content=response.model_dump(mode="json"))

        if PDFJobService.has_active_job(existing_job):
            response = PDFJobService.build_status_response(
                audit_id=audit.id,
                job=existing_job,
                report=None,
                retry_after_seconds=DEFAULT_PDF_RETRY_AFTER_SECONDS,
                message="PDF generation is already in progress for this audit.",
            )
            return JSONResponse(status_code=202, content=response.model_dump(mode="json"))

        if needs_pagespeed:
            queued_pagespeed_job = PageSpeedJobService.queue_if_needed(
                db,
                audit=audit,
                requested_by_user_id=current_user.user_id,
                strategy="both",
                force_refresh=force_pagespeed_refresh,
            )
            current_pagespeed_job = PageSpeedJobService.get_job(db, audit.id)
            if (
                current_pagespeed_job
                and PageSpeedJobService.has_active_job(current_pagespeed_job)
            ):
                job = PDFJobService.queue_job(
                    db,
                    audit_id=audit.id,
                    requested_by_user_id=current_user.user_id,
                    force_pagespeed_refresh=force_pagespeed_refresh,
                    force_report_refresh=force_report_refresh,
                    force_external_intel_refresh=force_external_intel_refresh,
                )
                job = PDFJobService.mark_job_waiting(
                    db,
                    job,
                    waiting_on="pagespeed",
                    dependency_job_id=current_pagespeed_job.id,
                )
                PDFJobService.publish_status_event(db, audit, job=job)
                response = PDFJobService.build_status_response(
                    audit_id=audit.id,
                    job=job,
                    report=None,
                    retry_after_seconds=DEFAULT_PDF_RETRY_AFTER_SECONDS,
                    message=(
                        "PDF generation is waiting for the active PageSpeed refresh to finish."
                    ),
                )
                return JSONResponse(
                    status_code=202,
                    content=response.model_dump(mode="json"),
                )

            if queued_pagespeed_job is None and existing_pagespeed_job is not None:
                db.refresh(audit)

        job = PDFJobService.queue_job(
            db,
            audit_id=audit.id,
            requested_by_user_id=current_user.user_id,
            force_pagespeed_refresh=force_pagespeed_refresh,
            force_report_refresh=force_report_refresh,
            force_external_intel_refresh=force_external_intel_refresh,
        )

        try:
            job = PDFJobService.enqueue_job_task(db, audit, job)
        except Exception as exc:
            logger.error(
                "generate_pdf_queue_failed audit_id=%s job_id=%s error=%s",
                audit.id,
                job.id,
                exc,
            )
            error_code, error_message = PDFJobService.classify_error(exc)
            PDFJobService.mark_job_failed(
                db,
                job,
                error_code="worker_unavailable",
                error_message=error_message,
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error_code": "worker_unavailable",
                    "message": "Background worker unavailable. Try again shortly.",
                },
            ) from exc

        response = PDFJobService.build_status_response(
            audit_id=audit.id,
            job=job,
            report=None,
            retry_after_seconds=DEFAULT_PDF_RETRY_AFTER_SECONDS,
            message="PDF generation queued successfully.",
        )
        return JSONResponse(status_code=202, content=response.model_dump(mode="json"))
    except HTTPException:
        raise
    except (OperationalError, DBAPIError) as db_err:
        logger.error(
            "generate_pdf_db_failed audit_id=%s error_code=db_unavailable error=%s",
            audit_id,
            db_err,
        )
        raise _db_unavailable_http_exception("generate_pdf_persist") from db_err
    except Exception as exc:
        logger.exception("Error queueing PDF generation for audit %s", audit_id)
        _persist_runtime_diagnostic_safely(
            db,
            audit_id,
            source="pdf",
            stage="generate-pdf",
            severity="error",
            code="pdf_queue_failed",
            message="PDF generation could not be queued.",
            technical_detail=_runtime_technical_detail(exc),
        )
        if isinstance(exc, HTTPException):
            raise exc
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{audit_id}/pagespeed-status", response_model=AuditPageSpeedStatusResponse)
async def get_audit_pagespeed_status(
    audit_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    try:
        artifact_payload, source = _get_owned_artifact_payload(
            db, audit_id, current_user
        )
    except (OperationalError, DBAPIError) as db_err:
        logger.error(
            "pagespeed_status_db_failed audit_id=%s error_code=db_unavailable error=%s",
            audit_id,
            db_err,
        )
        raise _db_unavailable_http_exception("pagespeed_status_lookup") from db_err

    payload = dict(artifact_payload)
    payload["pagespeed_retry_after_seconds"] = _artifact_status_retry_after(
        source,
        int(payload.get("pagespeed_retry_after_seconds") or 0),
    )
    message = (
        None
        if source == "redis"
        else "Artifact status served from database fallback while Redis snapshot is unavailable."
    )
    return PageSpeedJobService.build_status_response_from_artifact_payload(
        payload,
        message=message,
    )


@router.get("/{audit_id}/download-pdf")
async def download_audit_pdf(
    audit_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """
    Descarga el PDF de una auditoría completada.
    Si el PDF no existe, sugiere generarlo primero.
    """
    signed_url, storage_path = await _resolve_signed_pdf_download_url(
        audit_id=audit_id,
        db=db,
        current_user=current_user,
    )
    logger.info(
        f"storage_provider=supabase audit_id={audit_id} action=download_pdf_redirect storage_path={storage_path}"
    )
    return RedirectResponse(url=signed_url, status_code=302)


@router.get("/{audit_id}/download-pdf-url", response_model=PDFDownloadUrlResponse)
async def get_audit_pdf_download_url(
    audit_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    signed_url, storage_path = await _resolve_signed_pdf_download_url(
        audit_id=audit_id,
        db=db,
        current_user=current_user,
    )
    logger.info(
        f"storage_provider=supabase audit_id={audit_id} action=download_pdf_url_ok storage_path={storage_path}"
    )
    return PDFDownloadUrlResponse(
        download_url=signed_url,
        expires_in_seconds=3600,
        storage_provider="supabase",
    )


@router.post("/chat/config", response_model=ChatMessage)
async def configure_audit_chat(
    config: AuditConfigRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """
    Configura auditoría y lanza pipeline.
    """
    audit = _get_owned_audit(db, config.audit_id, current_user)

    # Prevenir doble ejecución si ya está en curso
    if audit.status in [AuditStatus.RUNNING, AuditStatus.COMPLETED]:
        logger.warning(
            f"Audit {audit.id} already {audit.status}. Skipping duplicate trigger."
        )
        return ChatMessage(
            role="assistant", content="This audit is already in progress or completed."
        )

    if config.language:
        audit.language = config.language
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
            if settings.DEBUG:
                background_tasks.add_task(run_audit_sync, audit.id)
            else:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Background worker unavailable. Try again shortly.",
                )

        return ChatMessage(
            role="assistant", content="Configuration saved. Starting audit..."
        )
    except Exception:
        db.rollback()
        logger.exception("Error saving audit configuration")
        raise HTTPException(status_code=500, detail="Internal server error")


# DEPRECATED: Old GitHub integration endpoint
# This functionality is now handled by /api/v1/github/ endpoints
# See: backend/app/api/routes/github.py

# class GitHubFixRequest(BaseModel):
#     repo_full_name: str
#     base_branch: str = "main"

# @router.post("/{audit_id}/github/create-fix", status_code=status.HTTP_201_CREATED)
# async def create_github_fix(...):
#     # This endpoint has been superseded by the new GitHub integration
#     # Use /api/v1/github/create-auto-fix-pr/{connection_id}/{repo_id} instead
