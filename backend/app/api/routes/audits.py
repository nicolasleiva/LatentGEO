from time import perf_counter
from typing import List
from urllib.parse import urlparse

from app.core.access_control import ensure_artifact_snapshot_access, ensure_audit_access
from app.core.auth import AuthUser, get_current_user
from app.core.config import settings
from app.core.database import SessionLocal, get_db
from app.core.logger import get_logger
from app.models import Audit, AuditedPage, AuditPageSpeedJob, AuditStatus, Competitor
from app.schemas import (
    AuditArtifactsStatusResponse,
    AuditConfigRequest,
    AuditCreate,
    AuditOverview,
    AuditPageSpeedStatusResponse,
    AuditPDFStatusResponse,
    AuditResponse,
    AuditSummary,
    ChatMessage,
    PDFDownloadUrlResponse,
)
from app.services import pdf_job_service as pdf_job_service_module
from app.services.audit_local_service import AuditLocalService
from app.services.audit_service import AuditService
from app.services.competitor_filters import (
    infer_vertical_hint,
    is_valid_competitor_domain,
    normalize_domain,
)
from app.services.pagespeed_job_service import (
    DEFAULT_PAGESPEED_RETRY_AFTER_SECONDS,
    PageSpeedJobService,
)
from app.services.pdf_job_service import DEFAULT_PDF_RETRY_AFTER_SECONDS, PDFJobService
from app.services.pipeline_service import PipelineService

# Importar la tarea de Celery
from app.workers.tasks import run_audit_task
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.orm import Session

logger = get_logger(__name__)

# Backward-compatible aliases used by legacy lock tests and tooling.
_pdf_generation_in_progress = pdf_job_service_module._pdf_generation_in_progress
_pdf_generation_tokens = pdf_job_service_module._pdf_generation_tokens
_acquire_pdf_generation_lock = pdf_job_service_module.acquire_pdf_generation_lock
_pdf_lock_key = pdf_job_service_module.pdf_lock_key
_release_pdf_generation_lock = pdf_job_service_module.release_pdf_generation_lock

router = APIRouter(
    prefix="/audits",
    tags=["audits"],
    responses={404: {"description": "No encontrado"}},
)

_AUDIT_ACCESS_FIELDS = (
    Audit.id,
    Audit.user_id,
    Audit.user_email,
)
_AUDIT_CACHE_VALIDATION_FIELDS = _AUDIT_ACCESS_FIELDS + (Audit.created_at,)
_AUDIT_STATUS_FIELDS = _AUDIT_ACCESS_FIELDS + (
    Audit.url,
    Audit.domain,
    Audit.status,
    Audit.progress,
    Audit.geo_score,
    Audit.total_pages,
)
_AUDIT_OVERVIEW_FIELDS = _AUDIT_ACCESS_FIELDS + (
    Audit.url,
    Audit.domain,
    Audit.status,
    Audit.progress,
    Audit.created_at,
    Audit.started_at,
    Audit.completed_at,
    Audit.geo_score,
    Audit.total_pages,
    Audit.critical_issues,
    Audit.high_issues,
    Audit.medium_issues,
    Audit.source,
    Audit.language,
    Audit.category,
    Audit.market,
    Audit._intake_profile_raw,
    Audit._runtime_diagnostics_raw,
    Audit.odoo_connection_id,
    Audit.error_message,
)
_AUDIT_RESPONSE_FIELDS = _AUDIT_ACCESS_FIELDS + (
    Audit.url,
    Audit.domain,
    Audit.status,
    Audit.progress,
    Audit.created_at,
    Audit.started_at,
    Audit.completed_at,
    Audit.error_message,
    Audit.target_audit,
    Audit.external_intelligence,
    Audit.competitor_audits,
    Audit.fix_plan,
    Audit.report_markdown,
    Audit.total_pages,
    Audit.critical_issues,
    Audit.high_issues,
    Audit.medium_issues,
    Audit.pagespeed_data,
    Audit.language,
    Audit.category,
    Audit.competitors,
    Audit.market,
    Audit._intake_profile_raw,
    Audit._runtime_diagnostics_raw,
    Audit.odoo_connection_id,
    Audit.geo_score,
)
_AUDIT_PDF_FIELDS = _AUDIT_ACCESS_FIELDS + (
    Audit.url,
    Audit.domain,
    Audit.status,
    Audit.created_at,
    Audit.pagespeed_data,
)
_AUDIT_CHAT_CONFIG_FIELDS = _AUDIT_ACCESS_FIELDS + (
    Audit.status,
    Audit.language,
    Audit.competitors,
    Audit.market,
    Audit.progress,
)
_AUDITED_PAGE_COMPACT_FIELDS = (
    AuditedPage.id,
    AuditedPage.url,
    AuditedPage.path,
    AuditedPage.overall_score,
    AuditedPage.h1_score,
    AuditedPage.structure_score,
    AuditedPage.content_score,
    AuditedPage.eeat_score,
    AuditedPage.schema_score,
    AuditedPage.critical_issues,
    AuditedPage.high_issues,
    AuditedPage.medium_issues,
    AuditedPage.low_issues,
)
_AUDITED_PAGE_DETAIL_FIELDS = _AUDITED_PAGE_COMPACT_FIELDS + (AuditedPage.audit_data,)


def _get_owned_audit(db: Session, audit_id: int, current_user: AuthUser) -> Audit:
    audit = AuditService.get_audit(db, audit_id)
    return ensure_audit_access(audit, current_user)


def _get_owned_projected_audit(
    db: Session,
    audit_id: int,
    current_user: AuthUser,
    *fields,
) -> Audit:
    audit = AuditService.get_audit_projection(db, audit_id, *fields)
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
    audit = _get_owned_projected_audit(
        db,
        audit_id,
        current_user,
        *_AUDIT_CACHE_VALIDATION_FIELDS,
    )
    cached_payload = AuditService.get_cached_artifact_payload(audit_id)
    if cached_payload is not None and AuditService.artifact_payload_matches_audit(
        cached_payload, audit
    ):
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


def _default_artifact_status_payload(
    audit_id: int,
    payload: dict | None = None,
) -> dict[str, object]:
    base_payload: dict[str, object] = {
        "audit_id": audit_id,
        "pagespeed_status": "idle",
        "pagespeed_available": False,
        "pagespeed_warnings": [],
        "pagespeed_retry_after_seconds": 0,
        "pdf_status": "idle",
        "pdf_available": False,
        "pdf_warnings": [],
        "pdf_retry_after_seconds": 0,
    }
    if isinstance(payload, dict):
        base_payload.update(payload)
    return base_payload


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


def _summarize_external_intelligence(
    payload: dict[str, object] | None,
) -> dict[str, str] | None:
    return AuditService._summarize_external_intelligence(payload)


def _runtime_technical_detail(exc: Exception) -> str | None:
    return PDFJobService.runtime_technical_detail(exc)


def _build_audit_shell_response(
    db: Session,
    audit: Audit,
) -> AuditOverview:
    payload = AuditService.rebuild_overview_payload(db, audit.id, audit=audit)
    if payload is None:
        raise HTTPException(status_code=404, detail="Auditoría no encontrada")
    public_payload = AuditService.public_overview_payload(payload) or {}
    return AuditOverview(**public_payload)


def _get_owned_overview_payload(
    db: Session,
    audit_id: int,
    current_user: AuthUser,
) -> AuditOverview:
    audit_stub = _get_owned_projected_audit(
        db,
        audit_id,
        current_user,
        *_AUDIT_CACHE_VALIDATION_FIELDS,
    )
    cached_payload = AuditService.get_cached_overview_payload(audit_id)
    if cached_payload is not None and AuditService.overview_payload_matches_audit(
        cached_payload, audit_stub
    ):
        ensure_artifact_snapshot_access(cached_payload, current_user)
        public_payload = AuditService.public_overview_payload(cached_payload) or {}
        return AuditOverview(**public_payload)

    audit = _get_owned_projected_audit(
        db,
        audit_id,
        current_user,
        *_AUDIT_OVERVIEW_FIELDS,
    )
    return _build_audit_shell_response(db, audit)


def _log_generate_pdf_timing(
    *,
    audit_id: int,
    path: str,
    started_at: float,
    precheck_ms: int,
    job_lookup_ms: int,
    dependency_ms: int,
    queue_ms: int,
) -> None:
    logger.info(
        "generate_pdf_timing audit_id=%s path=%s precheck_ms=%s job_lookup_ms=%s dependency_ms=%s queue_ms=%s total_ms=%s",
        audit_id,
        path,
        precheck_ms,
        job_lookup_ms,
        dependency_ms,
        queue_ms,
        int((perf_counter() - started_at) * 1000),
    )


def _publish_artifact_snapshot(
    audit: Audit,
    *,
    pagespeed_job: AuditPageSpeedJob | None = None,
    pdf_job=None,
    pdf_report=None,
) -> None:
    AuditService.publish_artifact_event(
        audit.id,
        AuditService.build_artifact_payload(
            audit,
            pagespeed_job=pagespeed_job,
            pdf_job=pdf_job,
            pdf_report=pdf_report,
        ),
    )


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
    if pagespeed_job is not None and pagespeed_job.status == "completed":
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
            try:
                pdf_report = await PDFService.ensure_supabase_pdf_report(
                    db=db,
                    audit=audit,
                    report=pdf_report,
                    allow_full_regeneration=False,
                )
            except HTTPException:
                raise
            except (OperationalError, DBAPIError):
                raise
            except Exception as exc:
                logger.error(
                    "storage_provider=supabase audit_id=%s action=repair_legacy_pdf_failed error=%s",
                    audit_id,
                    exc,
                )
                raise HTTPException(
                    status_code=502,
                    detail="No se pudo reparar el PDF almacenado para su descarga. Generá el PDF nuevamente.",
                ) from exc

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


def _dispatch_pdf_job_after_response(audit_id: int, job_id: int) -> None:
    db = SessionLocal()
    try:
        audit = AuditService.get_audit_projection(db, audit_id, *_AUDIT_PDF_FIELDS)
        if audit is None:
            logger.warning(
                "pdf_dispatch_skipped_missing_audit audit_id=%s job_id=%s",
                audit_id,
                job_id,
            )
            return
        job = PDFJobService.get_job(db, audit_id)
        if job is None or job.id != job_id or job.status != "queued":
            return
        PDFJobService.enqueue_job_task(db, audit, job)
    except Exception as exc:
        logger.error(
            "pdf_dispatch_after_response_failed audit_id=%s job_id=%s error=%s",
            audit_id,
            job_id,
            exc,
        )
        db.rollback()
        audit = AuditService.get_audit_projection(db, audit_id, *_AUDIT_PDF_FIELDS)
        job = PDFJobService.get_job(db, audit_id)
        if audit is None or job is None or job.id != job_id:
            return
        PDFJobService.mark_dispatch_failed(
            db,
            audit,
            job,
            exc=exc,
            message="PDF generation could not be dispatched after the request was accepted.",
        )
    finally:
        db.close()


def _dispatch_pagespeed_job_after_response(
    audit_id: int,
    job_id: int,
) -> None:
    db = SessionLocal()
    try:
        audit = AuditService.get_audit_projection(db, audit_id, *_AUDIT_PDF_FIELDS)
        if audit is None:
            logger.warning(
                "pagespeed_dispatch_skipped_missing_audit audit_id=%s job_id=%s",
                audit_id,
                job_id,
            )
            return
        job = PageSpeedJobService.get_job(db, audit_id)
        if job is None or job.id != job_id or job.status != "queued":
            return
        PageSpeedJobService.enqueue_job_task(db, audit, job)
    except Exception as exc:
        logger.error(
            "pagespeed_dispatch_after_response_failed audit_id=%s job_id=%s error=%s",
            audit_id,
            job_id,
            exc,
        )
        db.rollback()
        audit = AuditService.get_audit_projection(db, audit_id, *_AUDIT_PDF_FIELDS)
        job = PageSpeedJobService.get_job(db, audit_id)
        if audit is None or job is None or job.id != job_id:
            return
        PageSpeedJobService.mark_dispatch_failed(
            db,
            audit,
            job,
            exc=exc,
            message="PageSpeed analysis could not be dispatched after the request was accepted.",
        )
    finally:
        db.close()


def _dispatch_audit_after_chat_config(audit_id: int) -> None:
    db = SessionLocal()
    try:
        audit = AuditService.get_audit_projection(
            db,
            audit_id,
            *_AUDIT_CHAT_CONFIG_FIELDS,
        )
        if audit is None:
            logger.warning("chat_config_dispatch_missing_audit audit_id=%s", audit_id)
            return
        task = run_audit_task.delay(audit.id)
        AuditService.set_audit_task_id(db, audit.id, task.id)
        logger.info("Audit %s pipeline started after chat config", audit.id)
    except Exception as exc:
        logger.error(
            "chat_config_dispatch_failed audit_id=%s error=%s",
            audit_id,
            exc,
        )
        db.rollback()
        audit = AuditService.get_audit(db, audit_id)
        if audit is None:
            return
        audit.status = AuditStatus.FAILED
        audit.error_message = "Background worker unavailable. Try again shortly."
        audit.task_id = None
        db.add(audit)
        db.commit()
        db.refresh(audit)
        AuditService.publish_progress_event(
            audit_id=audit.id,
            payload=AuditService.build_progress_payload(audit),
        )
        AuditService.append_runtime_diagnostic(
            db,
            audit.id,
            source="pipeline",
            stage="chat-config-dispatch",
            severity="error",
            code="worker_unavailable",
            message="Audit configuration was saved, but the pipeline could not be dispatched.",
            technical_detail=type(exc).__name__,
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
    audit = _get_owned_projected_audit(
        db,
        audit_id,
        current_user,
        *_AUDIT_STATUS_FIELDS,
    )
    return audit


@router.get("/{audit_id}/summary", response_model=AuditOverview)
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
    return _get_owned_overview_payload(db, audit_id, current_user)


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


@router.get("/{audit_id}", response_model=AuditOverview)
def get_audit(
    audit_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """
    Get the slim audit shell payload without loading heavy report blobs.
    """
    return _get_owned_overview_payload(db, audit_id, current_user)


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


@router.get("/{audit_id}/issues", response_model=dict)
@router.get("/{audit_id}/fix_plan", response_model=dict)
def get_audit_issues(
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
    _get_owned_projected_audit(
        db,
        audit_id,
        current_user,
        *_AUDIT_ACCESS_FIELDS,
    )

    pages = AuditService.get_audited_pages_projection(
        db,
        audit_id,
        *_AUDITED_PAGE_COMPACT_FIELDS,
    )
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
    _get_owned_projected_audit(
        db,
        audit_id,
        current_user,
        *_AUDIT_ACCESS_FIELDS,
    )

    page = AuditService.get_audited_page_projection(
        db,
        audit_id,
        page_id,
        *_AUDITED_PAGE_DETAIL_FIELDS,
    )

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

    def _build_competitor_response(
        competitor_payload: dict[str, object],
        *,
        fallback_url: str | None = None,
        default_geo_score: float = 0.0,
        benchmark_available: bool | None = None,
    ) -> dict[str, object]:
        normalized_comp = CompetitorService.normalize_competitor_audit_payload(
            competitor_payload
        )
        score_meta = normalized_comp.get("benchmark")
        return CompetitorService._format_competitor_data(
            normalized_comp,
            normalized_comp.get("geo_score", default_geo_score) or default_geo_score,
            fallback_url or normalized_comp.get("url"),
            score_meta=score_meta if isinstance(score_meta, dict) else None,
            benchmark_available=benchmark_available,
        )

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
            formatted = _build_competitor_response(
                audit_data,
                fallback_url=comp.url,
                default_geo_score=comp.geo_score or 0,
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
            formatted = _build_competitor_response(
                comp,
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
    except Exception:
        logger.warning(
            "Could not derive competitors from search_results for audit %s",
            audit_id,
            exc_info=True,
        )

    return result


@router.post("/{audit_id}/run-pagespeed")
@router.post("/{audit_id}/pagespeed")
async def run_pagespeed_analysis(
    audit_id: int,
    background_tasks: BackgroundTasks,
    strategy: str = "both",
    force_refresh: bool = False,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """
    Queue or reuse the canonical PageSpeed job for an audit.
    """
    audit = _get_owned_projected_audit(
        db,
        audit_id,
        current_user,
        *_AUDIT_PDF_FIELDS,
    )
    if audit.status != AuditStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"La auditoría debe estar completada. Estado actual: {audit.status.value}",
        )

    normalized_strategy = (
        strategy.strip().lower() if isinstance(strategy, str) else "both"
    )
    if normalized_strategy not in {"mobile", "desktop", "both"}:
        normalized_strategy = "both"

    try:
        existing_job = PageSpeedJobService.get_job_reconciled(db, audit.id)
        if PageSpeedJobService.has_active_job(existing_job):
            response = PageSpeedJobService.build_status_response(
                audit=audit,
                job=existing_job,
                retry_after_seconds=DEFAULT_PAGESPEED_RETRY_AFTER_SECONDS,
                message="PageSpeed analysis is already in progress for this audit.",
            )
            return JSONResponse(
                status_code=202,
                content=response.model_dump(mode="json"),
                background=background_tasks,
            )

        if not force_refresh and PageSpeedJobService.has_usable_pagespeed_data(
            audit,
            require_complete=(normalized_strategy == "both"),
        ):
            response = PageSpeedJobService.build_status_response(
                audit=audit,
                job=(
                    existing_job
                    if existing_job and existing_job.status == "completed"
                    else None
                ),
                message="Existing PageSpeed data is already available.",
            )
            return JSONResponse(
                status_code=200,
                content=response.model_dump(mode="json"),
                background=background_tasks,
            )

        job = PageSpeedJobService.queue_job(
            db,
            audit=audit,
            requested_by_user_id=current_user.user_id,
            strategy=normalized_strategy,
            force_refresh=force_refresh,
        )
        background_tasks.add_task(
            _dispatch_pagespeed_job_after_response,
            audit.id,
            job.id,
        )

        response = PageSpeedJobService.build_status_response(
            audit=audit,
            job=job,
            retry_after_seconds=DEFAULT_PAGESPEED_RETRY_AFTER_SECONDS,
            message="PageSpeed analysis queued successfully.",
        )
        return JSONResponse(
            status_code=202,
            content=response.model_dump(mode="json"),
            background=background_tasks,
        )
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

    payload = _default_artifact_status_payload(
        audit_id,
        AuditService.public_artifact_payload(artifact_payload),
    )
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
    payload["pagespeed_message"] = payload.get("pagespeed_message") or degraded_message
    return AuditArtifactsStatusResponse.model_validate(payload)


@router.post(
    "/{audit_id}/generate-pdf",
    response_model=AuditPDFStatusResponse,
)
async def generate_audit_pdf(
    audit_id: int,
    background_tasks: BackgroundTasks,
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
    request_started_at = perf_counter()
    precheck_ms = 0
    job_lookup_ms = 0
    dependency_ms = 0
    queue_ms = 0
    try:
        audit = _get_owned_projected_audit(
            db,
            audit_id,
            current_user,
            *_AUDIT_PDF_FIELDS,
        )
        if audit.status != AuditStatus.COMPLETED:
            raise HTTPException(
                status_code=400,
                detail=f"La auditoría debe estar completada. Estado actual: {audit.status.value}",
            )
        precheck_ms = int((perf_counter() - request_started_at) * 1000)
    except HTTPException:
        raise
    except (OperationalError, DBAPIError) as db_err:
        logger.error(
            f"generate_pdf_precheck_failed audit_id={audit_id} error_code=db_unavailable error={db_err}"
        )
        raise _db_unavailable_http_exception("generate_pdf_precheck") from db_err

    try:
        lookup_started_at = perf_counter()
        existing_report = PDFJobService.get_latest_pdf_report(db, audit.id)
        existing_job = PDFJobService.get_job_reconciled(db, audit.id)
        current_pagespeed_job = PageSpeedJobService.get_job_reconciled(db, audit.id)
        needs_pagespeed = _pdf_requires_pagespeed_refresh(
            audit,
            force_pagespeed_refresh=force_pagespeed_refresh,
            pagespeed_job=current_pagespeed_job,
        )
        job_lookup_ms = int((perf_counter() - lookup_started_at) * 1000)

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
            _log_generate_pdf_timing(
                audit_id=audit.id,
                path="existing_report",
                started_at=request_started_at,
                precheck_ms=precheck_ms,
                job_lookup_ms=job_lookup_ms,
                dependency_ms=dependency_ms,
                queue_ms=queue_ms,
            )
            return JSONResponse(
                status_code=200,
                content=response.model_dump(mode="json"),
                background=background_tasks,
            )

        if PDFJobService.has_active_job(existing_job):
            response = PDFJobService.build_status_response(
                audit_id=audit.id,
                job=existing_job,
                report=None,
                retry_after_seconds=DEFAULT_PDF_RETRY_AFTER_SECONDS,
                message="PDF generation is already in progress for this audit.",
            )
            _log_generate_pdf_timing(
                audit_id=audit.id,
                path="active_job",
                started_at=request_started_at,
                precheck_ms=precheck_ms,
                job_lookup_ms=job_lookup_ms,
                dependency_ms=dependency_ms,
                queue_ms=queue_ms,
            )
            return JSONResponse(
                status_code=202,
                content=response.model_dump(mode="json"),
                background=background_tasks,
            )

        if needs_pagespeed:
            dependency_started_at = perf_counter()
            if not PageSpeedJobService.has_active_job(current_pagespeed_job):
                current_pagespeed_job = PageSpeedJobService.queue_job(
                    db,
                    audit=audit,
                    requested_by_user_id=current_user.user_id,
                    strategy="both",
                    force_refresh=force_pagespeed_refresh,
                    publish_event=False,
                )
                background_tasks.add_task(
                    _dispatch_pagespeed_job_after_response,
                    audit.id,
                    current_pagespeed_job.id,
                )
            dependency_ms = int((perf_counter() - dependency_started_at) * 1000)
            if current_pagespeed_job and PageSpeedJobService.has_active_job(
                current_pagespeed_job
            ):
                queue_started_at = perf_counter()
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
                queue_ms = int((perf_counter() - queue_started_at) * 1000)
                _publish_artifact_snapshot(
                    audit,
                    pagespeed_job=current_pagespeed_job,
                    pdf_job=job,
                    pdf_report=existing_report,
                )
                response = PDFJobService.build_status_response(
                    audit_id=audit.id,
                    job=job,
                    report=None,
                    retry_after_seconds=DEFAULT_PDF_RETRY_AFTER_SECONDS,
                    message=(
                        "PDF generation is waiting for the active PageSpeed refresh to finish."
                    ),
                )
                _log_generate_pdf_timing(
                    audit_id=audit.id,
                    path="waiting_on_pagespeed",
                    started_at=request_started_at,
                    precheck_ms=precheck_ms,
                    job_lookup_ms=job_lookup_ms,
                    dependency_ms=dependency_ms,
                    queue_ms=queue_ms,
                )
                return JSONResponse(
                    status_code=202,
                    content=response.model_dump(mode="json"),
                    background=background_tasks,
                )

        queue_started_at = perf_counter()
        job = PDFJobService.queue_job(
            db,
            audit_id=audit.id,
            requested_by_user_id=current_user.user_id,
            force_pagespeed_refresh=force_pagespeed_refresh,
            force_report_refresh=force_report_refresh,
            force_external_intel_refresh=force_external_intel_refresh,
        )
        queue_ms = int((perf_counter() - queue_started_at) * 1000)
        _publish_artifact_snapshot(
            audit,
            pagespeed_job=current_pagespeed_job,
            pdf_job=job,
            pdf_report=existing_report,
        )
        background_tasks.add_task(
            _dispatch_pdf_job_after_response,
            audit.id,
            job.id,
        )

        response = PDFJobService.build_status_response(
            audit_id=audit.id,
            job=job,
            report=None,
            retry_after_seconds=DEFAULT_PDF_RETRY_AFTER_SECONDS,
            message="PDF generation queued successfully.",
        )
        _log_generate_pdf_timing(
            audit_id=audit.id,
            path="queued",
            started_at=request_started_at,
            precheck_ms=precheck_ms,
            job_lookup_ms=job_lookup_ms,
            dependency_ms=dependency_ms,
            queue_ms=queue_ms,
        )
        return JSONResponse(
            status_code=202,
            content=response.model_dump(mode="json"),
            background=background_tasks,
        )
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


@router.post(
    "/chat/config",
    response_model=ChatMessage,
    status_code=status.HTTP_202_ACCEPTED,
)
async def configure_audit_chat(
    config: AuditConfigRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """
    Configura auditoría y lanza pipeline.
    """
    audit = _get_owned_projected_audit(
        db,
        config.audit_id,
        current_user,
        *_AUDIT_CHAT_CONFIG_FIELDS,
    )

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
        background_tasks.add_task(
            _dispatch_audit_after_chat_config,
            audit.id,
        )

        return ChatMessage(
            role="assistant", content="Configuration saved. Audit queued."
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
