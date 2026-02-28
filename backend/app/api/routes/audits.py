import asyncio
import uuid
from datetime import datetime
from typing import List
from urllib.parse import urlparse

from app.core.access_control import ensure_audit_access
from app.core.auth import AuthUser, get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.logger import get_logger
from app.models import Audit, AuditStatus, Competitor
from app.schemas import (
    AuditConfigRequest,
    AuditCreate,
    AuditResponse,
    AuditSummary,
    ChatMessage,
)
from app.services.audit_local_service import AuditLocalService
from app.services.audit_service import AuditService
from app.services.competitor_filters import (
    infer_vertical_hint,
    is_valid_competitor_domain,
    normalize_domain,
)
from app.services.cache_service import cache
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

_pdf_generation_in_progress: set[int] = set()
_pdf_generation_tokens: dict[int, str] = {}


def _pdf_lock_key(audit_id: int) -> str:
    return f"pdf_generation_lock:{audit_id}"


def _acquire_pdf_generation_lock(audit_id: int) -> tuple[bool, str | None, str | None]:
    """
    Acquire PDF lock using Redis (distributed).
    In production this is fail-closed when Redis is unavailable.
    Returns (acquired, token, mode["redis"|"local"|"unavailable"]).
    """
    token = str(uuid.uuid4())
    ttl_seconds = max(30, int(settings.PDF_LOCK_TTL_SECONDS or 900))

    if cache.enabled and cache.redis_client:
        try:
            acquired = bool(
                cache.redis_client.set(
                    _pdf_lock_key(audit_id),
                    token,
                    nx=True,
                    ex=ttl_seconds,
                )
            )
            if acquired:
                return True, token, "redis"
            return False, None, "redis"
        except Exception as exc:
            if not settings.DEBUG:
                logger.error(
                    f"Redis PDF lock unavailable for audit {audit_id}; refusing generation in production: {exc}"
                )
                return False, None, "unavailable"
            logger.warning(
                f"Redis PDF lock unavailable for audit {audit_id}; falling back to local lock in debug: {exc}"
            )
    else:
        if not settings.DEBUG:
            logger.error(
                f"Redis PDF lock disabled for audit {audit_id}; refusing generation in production"
            )
            return False, None, "unavailable"
        logger.warning(
            f"Redis PDF lock disabled for audit {audit_id}; using local in-memory lock in debug"
        )

    if audit_id in _pdf_generation_in_progress:
        return False, None, "local"

    _pdf_generation_in_progress.add(audit_id)
    _pdf_generation_tokens[audit_id] = token
    return True, token, "local"


def _release_pdf_generation_lock(
    audit_id: int, token: str | None, mode: str | None
) -> None:
    """Release Redis/local PDF lock safely."""
    if not token or not mode:
        return

    if mode == "redis":
        if cache.enabled and cache.redis_client:
            try:
                lock_key = _pdf_lock_key(audit_id)
                current_token = cache.redis_client.get(lock_key)
                if current_token == token:
                    cache.redis_client.delete(lock_key)
            except Exception as exc:
                logger.warning(
                    f"Failed to release Redis PDF lock for audit {audit_id}: {exc}"
                )
        return

    current_token = _pdf_generation_tokens.get(audit_id)
    if current_token and current_token != token:
        logger.warning(
            f"PDF local lock token mismatch for audit {audit_id}; forcing release"
        )
    _pdf_generation_tokens.pop(audit_id, None)
    _pdf_generation_in_progress.discard(audit_id)


def _get_owned_audit(db: Session, audit_id: int, current_user: AuthUser) -> Audit:
    audit = AuditService.get_audit(db, audit_id)
    return ensure_audit_access(audit, current_user)


def _db_unavailable_http_exception(action: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "error_code": "db_unavailable",
            "action": action,
            "message": "Database is temporarily unavailable. Retry in a few seconds.",
        },
    )


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

    audit = await run_in_threadpool(AuditService.create_audit, db, audit_create)

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

    # Load audited pages (fast operation)
    pages = AuditService.get_audited_pages(db, audit_id)
    audit.pages = pages

    # Recalcular GEO score si hay datos suficientes (evita valores falsos)
    if isinstance(audit.target_audit, dict):
        try:
            from app.services.audit_service import CompetitorService

            recalculated = CompetitorService._calculate_geo_score(audit.target_audit)
            if recalculated is not None:
                if (
                    audit.geo_score is None or audit.geo_score <= 0
                ) and recalculated >= 0:
                    audit.geo_score = recalculated
                    db.commit()
                elif recalculated > 0 and audit.geo_score != recalculated:
                    # Actualiza si la nueva métrica es más precisa
                    audit.geo_score = recalculated
                    db.commit()
        except Exception as e:
            logger.warning(
                f"No se pudo recalcular GEO score para audit {audit_id}: {e}"
            )

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
            geo_score = (
                CompetitorService._calculate_geo_score(audit_data)
                if audit_data
                else (comp.geo_score or 0)
            )
            if geo_score == 0 and comp.geo_score:
                geo_score = comp.geo_score
            formatted = CompetitorService._format_competitor_data(
                audit_data, geo_score, comp.url
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
            geo_score = CompetitorService._calculate_geo_score(comp)
            if geo_score == 0:
                geo_score = comp.get("geo_score", 0) or 0
            formatted = CompetitorService._format_competitor_data(comp, geo_score)
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
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
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

    audit = _get_owned_audit(db, audit_id, current_user)

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
        logger.info("Storing PageSpeed data in database...")
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
    force_pagespeed_refresh: bool = True,
    force_report_refresh: bool = False,
    force_external_intel_refresh: bool = False,
    background_tasks: BackgroundTasks = None,
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
    from app.models import Report
    from app.services.pdf_service import PDFService

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

    lock_token: str | None = None
    lock_mode: str | None = None

    acquired_lock, lock_token, lock_mode = _acquire_pdf_generation_lock(audit_id)
    if not acquired_lock:
        if lock_mode == "unavailable":
            return JSONResponse(
                status_code=503,
                content={
                    "success": False,
                    "generation_in_progress": False,
                    "message": (
                        "Distributed PDF lock backend is unavailable. "
                        "Redis is required to generate PDFs in production."
                    ),
                },
            )
        return JSONResponse(
            status_code=409,
            content={
                "success": False,
                "generation_in_progress": True,
                "retry_after_seconds": 10,
                "message": "PDF generation is already in progress for this audit.",
            },
        )

    try:
        logger.info(
            f"=== Starting PDF generation with auto-PageSpeed for audit {audit_id} ==="
        )

        # Generate PDF with complete context (includes auto-PageSpeed trigger)
        generation_result = await PDFService.generate_pdf_with_complete_context(
            db=db,
            audit_id=audit_id,
            force_pagespeed_refresh=force_pagespeed_refresh,
            force_report_refresh=force_report_refresh,
            force_external_intel_refresh=force_external_intel_refresh,
            return_details=True,
        )
        pdf_path = generation_result.get("pdf_path")
        if not pdf_path:
            raise Exception("PDF generation failed - missing path")
        is_supabase_path = str(pdf_path).startswith("supabase://")
        if not is_supabase_path:
            raise Exception(
                "PDF generation failed - expected Supabase storage path (supabase://...)."
            )

        file_size_raw = generation_result.get("file_size")
        try:
            file_size = int(file_size_raw) if file_size_raw is not None else None
        except (TypeError, ValueError):
            file_size = None

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
            logger.info("Updated existing PDF report entry")
        else:
            # Create new report entry
            pdf_report = Report(
                audit_id=audit_id,
                report_type="PDF",
                file_path=pdf_path,
                file_size=file_size,
            )
            db.add(pdf_report)
            logger.info("Created new PDF report entry")

        db.commit()

        # Refresh audit to get updated pagespeed_data
        db.refresh(audit)

        logger.info("=== PDF generation completed successfully ===")
        logger.info(f"PDF saved at: {pdf_path}")
        logger.info(f"PDF size: {file_size} bytes")

        return {
            "success": True,
            "pdf_path": pdf_path,
            "message": "PDF generated successfully with PageSpeed data",
            "pagespeed_included": bool(audit.pagespeed_data),
            "file_size": file_size,
            "report_cache_hit": bool(generation_result.get("report_cache_hit")),
            "report_regenerated": bool(generation_result.get("report_regenerated")),
            "generation_mode": generation_result.get("generation_mode", "unknown"),
            "external_intel_refreshed": bool(
                generation_result.get("external_intel_refreshed")
            ),
            "external_intel_refresh_reason": generation_result.get(
                "external_intel_refresh_reason", "not_needed"
            ),
        }

    except HTTPException:
        raise
    except (OperationalError, DBAPIError) as db_err:
        logger.error(
            f"generate_pdf_db_failed audit_id={audit_id} error_code=db_unavailable error={db_err}"
        )
        raise _db_unavailable_http_exception("generate_pdf_persist") from db_err
    except Exception as e:
        logger.error(f"=== Error generating PDF for audit {audit_id} ===")
        logger.error(f"Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error generating PDF: {str(e)}")
    finally:
        _release_pdf_generation_lock(audit_id, lock_token, lock_mode)


@router.get("/{audit_id}/download-pdf")
def download_audit_pdf(
    audit_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """
    Descarga el PDF de una auditoría completada.
    Si el PDF no existe, sugiere generarlo primero.
    """
    from app.models import Report

    try:
        audit = _get_owned_audit(db, audit_id, current_user)

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
                detail="El archivo PDF no existe. Por favor, genera el PDF primero usando POST /api/v1/audits/{audit_id}/generate-pdf",
            )

        pdf_path = pdf_report.file_path

        if not pdf_path.startswith("supabase://"):
            raise HTTPException(
                status_code=409,
                detail=(
                    "Legacy local PDF paths are disabled in Supabase-only mode. "
                    "Regenera el PDF para almacenarlo en Supabase."
                ),
            )
    except HTTPException:
        raise
    except (OperationalError, DBAPIError) as db_err:
        logger.error(
            f"download_pdf_db_failed audit_id={audit_id} error_code=db_unavailable error={db_err}"
        )
        raise _db_unavailable_http_exception("download_pdf_lookup") from db_err

    from app.services.supabase_service import SupabaseService

    storage_path = pdf_path.replace("supabase://", "", 1)
    try:
        signed_url = SupabaseService.get_signed_url(
            bucket=settings.SUPABASE_STORAGE_BUCKET,
            path=storage_path,
        )
        logger.info(
            f"storage_provider=supabase audit_id={audit_id} action=download_pdf_redirect storage_path={storage_path}"
        )
        return RedirectResponse(url=signed_url, status_code=302)
    except Exception as e:
        logger.error(
            f"storage_provider=supabase audit_id={audit_id} action=download_pdf_failed error_code=supabase_signed_url_failed error={e}"
        )
        raise HTTPException(
            status_code=500,
            detail="No se pudo generar el enlace de descarga de Supabase.",
        ) from e


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
    except Exception as e:
        db.rollback()
        logger.error(f"Error saving audit configuration: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error saving configuration: {str(e)}"
        )


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
