"""
Celery Tasks for background processing.
"""

from contextlib import contextmanager
from datetime import datetime, timezone

from app.core.config import settings
from app.core.database import SessionLocal, ensure_database_revision

# Importar la fábrica de LLM desde el endpoint de auditorías
# Esto puede ser refactorizado a un módulo de utilidades común en el futuro
from app.core.llm_kimi import get_llm_function
from app.core.logger import get_logger
from app.models import Audit, AuditStatus, GeoArticleBatch
from app.services.audit_local_service import AuditLocalService
from app.services.audit_service import AuditService, ReportService
from app.services.pagespeed_job_service import PageSpeedJobService
from app.services.pdf_job_service import PDFJobService
from app.services.pdf_service import PDFService
from app.services.pipeline_service import PipelineService
from app.workers.async_runtime import run_worker_coroutine
from app.workers.celery_app import celery_app
from sqlalchemy.orm import Session

logger = get_logger(__name__)


@contextmanager
def get_db_session():
    """Provide a transactional scope around a series of operations."""
    ensure_database_revision()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@celery_app.task(name="run_pdf_generation_job_task")
def run_pdf_generation_job_task(job_id: int):
    """
    Canonical PDF generation task.
    """
    logger.info("Starting canonical PDF generation job job_id=%s", job_id)
    with get_db_session() as db:
        job = run_worker_coroutine(PDFJobService.execute_job(db, job_id))
        logger.info(
            "Finished canonical PDF generation job job_id=%s status=%s",
            job_id,
            getattr(job, "status", "unknown"),
        )
        return {
            "job_id": job_id,
            "status": getattr(job, "status", "unknown"),
            "report_id": getattr(job, "report_id", None),
        }


@celery_app.task(name="run_pagespeed_generation_job_task")
def run_pagespeed_generation_job_task(job_id: int):
    """
    Canonical PageSpeed generation task.
    """
    logger.info("Starting canonical PageSpeed generation job job_id=%s", job_id)
    with get_db_session() as db:
        job = run_worker_coroutine(PageSpeedJobService.execute_job(db, job_id))
        logger.info(
            "Finished canonical PageSpeed generation job job_id=%s status=%s",
            job_id,
            getattr(job, "status", "unknown"),
        )
        return {
            "job_id": job_id,
            "status": getattr(job, "status", "unknown"),
        }


@celery_app.task(
    name="run_audit_task",
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 5, "countdown": 60},
    soft_time_limit=3600,  # 60 minutes for 50 pages
    time_limit=4000,
)
def run_audit_task(self, audit_id: int):
    """
    Tarea de Celery para ejecutar el pipeline completo.
    Mejorada con reintentos inteligentes para evitar condiciones de carrera.
    """
    logger.info(
        f"Celery task '{self.name}' [ID: {self.request.id}] started for audit_id: {audit_id}"
    )

    # No usamos time.sleep(2). Usamos lógica de reintento.

    try:
        with get_db_session() as db:
            audit = AuditService.get_audit(db, audit_id)
            if not audit:
                # Si la transacción del API aún no terminó, la auditoría no existirá aquí.
                # Reintentamos en 2 segundos sin contar como error grave.
                logger.warning(f"Audit {audit_id} not found yet, retrying in 2s...")
                raise self.retry(
                    exc=ValueError(f"Audit {audit_id} not found"),
                    countdown=2,
                    max_retries=5,
                )

            # 1. Marcar la auditoría como RUNNING
            AuditService.update_audit_progress(
                db=db, audit_id=audit_id, progress=5, status=AuditStatus.RUNNING
            )

            # Guardamos la URL y el contexto para usarla fuera del bloque de sesión
            audit_url = str(audit.url)
            audit_market = audit.market
            audit_domain = audit.domain
            audit_competitors = (
                audit.competitors if isinstance(audit.competitors, list) else []
            )

        # 2. Ejecutar el pipeline (fuera de la transacción de DB para no bloquearla)
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
                    logger.error(
                        f"AuditLocalService.run_local_audit returned non-dict for {url}: {type(summary)}"
                    )
                    return {
                        "status": 500,
                        "url": url,
                        "error": "Invalid audit result type",
                    }

                return summary
            except Exception as audit_error:
                logger.error(
                    f"Error in audit_local_service_func for {url}: {audit_error}",
                    exc_info=True,
                )
                return {"status": 500, "url": url, "error": str(audit_error)}

        # Importar crawler (PageSpeed y GEO tools se ejecutan solo al generar PDF)
        from app.services.crawler_service import CrawlerService

        # NOTE: PageSpeed and GEO Tools (Keywords, Rankings, Backlinks, Visibility)
        # are NOT run automatically here. They are executed when the user requests
        # the full PDF report via generate_full_report_task.
        # This keeps the main audit pipeline fast (2-5 minutes) and the dashboard available quickly.
        # CRITICAL FIX: Run local audit on target URL FIRST to get actual site data
        # Without this, the LLM cannot detect the correct category and search queries
        logger.info(f"Running local audit on target URL: {audit_url}")
        target_audit_result = run_worker_coroutine(audit_local_service_func(audit_url))

        if not target_audit_result or target_audit_result.get("status") == 500:
            logger.error(f"Failed to run local audit on target URL: {audit_url}")
            target_audit_result = {
                "url": audit_url,
                "status": 500,
                "error": "Failed to crawl target site",
            }
        else:
            logger.info(
                f"Local audit completed for {audit_url}: status={target_audit_result.get('status')}"
            )

        # Enriquecer con mercado/idioma/domino desde la auditoría si no viene en el resumen
        if isinstance(target_audit_result, dict):
            target_audit_result["language"] = "en"
            if audit_market and not target_audit_result.get("market"):
                target_audit_result["market"] = audit_market
            if audit_domain and not target_audit_result.get("domain"):
                target_audit_result["domain"] = audit_domain
            if audit_competitors and not target_audit_result.get("competitors"):
                target_audit_result["competitors"] = audit_competitors

        def update_progress(value: float):
            try:
                with get_db_session() as db:
                    audit = AuditService.get_audit(db, audit_id)
                    if not audit:
                        return
                    current = audit.progress or 0
                    if value <= current:
                        return
                    AuditService.update_audit_progress(
                        db=db,
                        audit_id=audit_id,
                        progress=value,
                        status=AuditStatus.RUNNING,
                    )
            except Exception as progress_err:
                logger.warning(
                    f"Could not update progress for audit {audit_id}: {progress_err}"
                )

        # Ejecutar pipeline principal de auditoría INICIAL (sin GEO tools, sin reporte pesado)
        # Este nuevo flujo es exclusivamente para errores (fix plan) y competidores.
        from app.services.pipeline_service import run_initial_audit

        result = run_worker_coroutine(
            run_initial_audit(
                url=audit_url,
                target_audit=target_audit_result,
                audit_id=audit_id,
                llm_function=llm_function,
                google_api_key=None,
                google_cx_id=None,
                crawler_service=CrawlerService.crawl_site,
                audit_local_service=audit_local_service_func,
                progress_callback=update_progress,
                generate_report=False,
                enable_llm_external_intel=True,
                external_intel_mode="full",
                external_intel_timeout_seconds=(
                    settings.AGENT1_LLM_TIMEOUT_SECONDS
                    if settings.AGENT1_LLM_TIMEOUT_SECONDS
                    and settings.AGENT1_LLM_TIMEOUT_SECONDS > 0
                    else None
                ),
            )
        )

        # GEO Tools (Keywords, Backlinks, Rankings) will be generated on-demand when PDF is requested
        # This avoids generating data that may not be used and keeps the audit pipeline fast

        # Guardar páginas auditadas individuales
        with get_db_session() as db:
            _save_individual_pages(db, audit_id, result)

        with get_db_session() as db:
            # 3. Guardar resultados y marcar como COMPLETED
            report_markdown = result.get("report_markdown", "")

            # Ensure target_audit is a dictionary.
            raw_target_audit = result.get("target_audit", {})
            if not isinstance(raw_target_audit, dict):
                logger.warning(
                    f"PipelineService returned non-dict target_audit for audit {audit_id}: {type(raw_target_audit)}"
                )
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

                # Generar y guardar análisis ejecutivo de PageSpeed
                try:
                    # Como estamos en un contexto síncrono, usamos asyncio.run
                    ps_analysis = run_worker_coroutine(
                        PipelineService.generate_pagespeed_analysis(
                            pagespeed_data, llm_function
                        )
                    )
                    if ps_analysis:
                        _save_pagespeed_analysis(audit_id, ps_analysis)
                except Exception as e:
                    logger.error(f"Error generating PageSpeed analysis: {e}")

            # Guardar resultados y marcar como COMPLETED
            run_worker_coroutine(
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
            )

            AuditService.update_audit_progress(
                db=db, audit_id=audit_id, progress=100, status=AuditStatus.COMPLETED
            )
            logger.info(f"Audit {audit_id} completed successfully.")
            logger.info(
                "Dashboard ready! PDF can be generated manually from the dashboard."
            )

            if settings.ENABLE_PAGESPEED and settings.GOOGLE_PAGESPEED_API_KEY:
                try:
                    db.expire_all()
                    persistent_audit = (
                        db.query(Audit).filter(Audit.id == audit_id).first()
                    )
                    if persistent_audit is None:
                        raise ValueError(
                            f"Audit {audit_id} not found after completion for automatic PageSpeed queue"
                        )
                    queued_pagespeed_job = PageSpeedJobService.queue_if_needed(
                        db,
                        audit=persistent_audit,
                        requested_by_user_id=getattr(
                            persistent_audit, "user_id", None
                        ),
                        strategy="both",
                        force_refresh=False,
                    )
                    if queued_pagespeed_job is not None:
                        logger.info(
                            "Queued automatic PageSpeed job for audit %s (job_id=%s)",
                            audit_id,
                            queued_pagespeed_job.id,
                        )
                except Exception as pagespeed_queue_error:
                    logger.warning(
                        "Automatic PageSpeed queue failed for audit %s: %s",
                        audit_id,
                        pagespeed_queue_error,
                    )
                    try:
                        AuditService.append_runtime_diagnostic(
                            db,
                            audit_id,
                            source="pagespeed",
                            stage="auto-queue",
                            severity="warning",
                            code="pagespeed_auto_queue_failed",
                            message="Automatic PageSpeed queue failed after audit completion.",
                            technical_detail=type(pagespeed_queue_error).__name__,
                        )
                    except Exception:
                        logger.warning(
                            "Could not persist automatic PageSpeed queue diagnostic for audit %s",
                            audit_id,
                        )

    except Exception as e:
        logger.error(f"Error running pipeline for audit {audit_id}: {e}", exc_info=True)
        try:
            with get_db_session() as db:
                # 5. Marcar como FAILED en caso de error
                audit = AuditService.get_audit(db, audit_id)
                last_progress = getattr(audit, "progress", 0) if audit else 0

                AuditService.update_audit_progress(
                    db=db,
                    audit_id=audit_id,
                    progress=last_progress,
                    status=AuditStatus.FAILED,
                    error_message=str(e),
                )
            logger.error(f"Audit {audit_id} marked as FAILED.")
        except Exception as db_error:
            logger.critical(
                f"Failed to update audit {audit_id} status to FAILED: {db_error}",
                exc_info=True,
            )
        raise


@celery_app.task(
    name="run_geo_analysis_task",
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 60},
    soft_time_limit=900,
    time_limit=1000,
)
def run_geo_analysis_task(self, audit_id: int):
    """
    Tarea separada para ejecutar herramientas GEO (Rank, Backlinks, Visibility)
    y actualizar el reporte existente.
    """
    logger.info(f"Starting GEO Analysis task for audit {audit_id}")

    try:
        with get_db_session() as db:
            audit = AuditService.get_audit(db, audit_id)
            if not audit:
                raise ValueError(f"Audit {audit_id} not found")

            audit_url = str(audit.url)

            # Import services
            from urllib.parse import urlparse

            from app.services.backlink_service import BacklinkService
            from app.services.llm_visibility_service import LLMVisibilityService
            from app.services.rank_tracker_service import RankTrackerService

            domain = urlparse(audit_url).netloc.replace("www.", "")
            brand_name = domain.split(".")[0]

            # Get category from existing intelligence if available
            category = None
            if audit.external_intelligence and isinstance(
                audit.external_intelligence, dict
            ):
                category = audit.external_intelligence.get("category")

            # 1. Prepare Keywords
            keywords = [brand_name]
            if category:
                keywords.append(category)

            # 2. Define Async Wrapper
            async def run_geo_tools():
                rank_service = RankTrackerService(db)
                backlink_service = BacklinkService(db)
                visibility_service = LLMVisibilityService(db)

                logger.info(f"Running Rank Tracking for {domain}")
                rankings = await rank_service.track_rankings(audit_id, domain, keywords)

                logger.info(f"Running Backlink Analysis for {domain}")
                backlinks = await backlink_service.analyze_backlinks(audit_id, domain)

                logger.info(f"Running LLM Visibility for {domain}")

                # Use instance method check_visibility to ensure results are saved to DB
                visibility = await visibility_service.check_visibility(
                    audit_id, brand_name, keywords
                )

                return rankings, backlinks, visibility

            # 3. Execute Tools
            rankings, backlinks, visibility = run_worker_coroutine(run_geo_tools())

            # 4. Append/Update Report
            current_report = audit.report_markdown or ""

            # Check if GEO section already exists to avoid duplication (simple check)
            if "# 10. Análisis GEO Automático" not in current_report:
                geo_section = "\n\n# 10. Análisis GEO Automático (Anexos)\n\n"

                # Rank Tracking
                geo_section += "## 10.1 Rank Tracking Inicial\n"
                if rankings:
                    geo_section += (
                        "| Keyword | Posición | Top Competidor |\n|---|---|---|\n"
                    )
                    for r in rankings:
                        top_competitor = (
                            r.top_results[0]["domain"] if r.top_results else "N/A"
                        )
                        pos = f"#{r.position}" if r.position > 0 else ">10"
                        geo_section += f"| {r.keyword} | {pos} | {top_competitor} |\n"
                else:
                    geo_section += "*No se encontraron rankings.*\n"

                # Backlinks
                geo_section += "\n## 10.2 Análisis de Enlaces\n"
                geo_section += (
                    f"* **Total de Backlinks Encontrados**: {len(backlinks)}\n"
                )
                dofollow_count = len([b for b in backlinks if b.is_dofollow])
                geo_section += f"* **Enlaces DoFollow**: {dofollow_count}\n"
                geo_section += (
                    f"* **Enlaces NoFollow**: {len(backlinks) - dofollow_count}\n"
                )

                # LLM Visibility
                geo_section += "\n## 10.3 Visibilidad en IA (LLMs)\n"
                if visibility and len(visibility) > 0:
                    visible_count = sum(
                        1 for v in visibility if v.get("is_visible", False)
                    )
                    total_queries = len(visibility)
                    visibility_rate = (
                        (visible_count / total_queries * 100)
                        if total_queries > 0
                        else 0
                    )

                    geo_section += f"* **Consultas Analizadas**: {total_queries}\n"
                    geo_section += f"* **Visibilidad**: {visible_count}/{total_queries} ({visibility_rate:.1f}%)\n"
                    geo_section += (
                        f"* **LLM**: {visibility[0].get('llm_name', 'KIMI')}\n"
                    )

                    visible_queries = [
                        v for v in visibility if v.get("is_visible", False)
                    ]
                    if visible_queries:
                        geo_section += "\n**Queries donde la marca es visible:**\n"
                        for v in visible_queries[:3]:
                            query = v.get("query", "N/A")
                            citation = (
                                v.get("citation_text", "")[:100] + "..."
                                if len(v.get("citation_text", "")) > 100
                                else v.get("citation_text", "")
                            )
                            geo_section += f"- *{query}*: {citation}\n"
                else:
                    geo_section += "*Análisis de visibilidad no disponible.*\n"

                # Update Audit
                audit.report_markdown = current_report + geo_section
                db.commit()
                logger.info("GEO Tools results appended to report.")

                # Regenerate PDF
                logger.info(f"Regenerating PDF for audit {audit_id}")
                pdf_file_path = PDFService.create_from_audit(
                    audit=audit, markdown_content=audit.report_markdown
                )
                pdf_file_size = getattr(audit, "_generated_pdf_size_bytes", None)
                ReportService.create_report(
                    db=db,
                    audit_id=audit_id,
                    report_type="PDF",
                    file_path=pdf_file_path,
                    file_size=pdf_file_size,
                )
            else:
                logger.info("GEO section already present in report.")

    except Exception as e:
        logger.error(
            f"Error running GEO Analysis task for audit {audit_id}: {e}", exc_info=True
        )
        raise


def _save_pagespeed_data(audit_id: int, pagespeed_data: dict):
    """Guardar datos de PageSpeed en JSON"""
    if not settings.AUDIT_LOCAL_ARTIFACTS_ENABLED:
        logger.info(
            f"Skipping local pagespeed artifact for audit {audit_id} (Supabase-only mode)."
        )
        return
    try:
        import json
        from pathlib import Path

        reports_dir = Path(settings.REPORTS_DIR or "reports") / f"audit_{audit_id}"
        reports_dir.mkdir(parents=True, exist_ok=True)

        pagespeed_path = reports_dir / "pagespeed.json"
        with open(pagespeed_path, "w", encoding="utf-8") as f:
            json.dump(pagespeed_data, f, ensure_ascii=False, indent=2)

        logger.info(f"PageSpeed data saved to {pagespeed_path}")
    except Exception as e:
        logger.error(f"Error saving PageSpeed data for audit {audit_id}: {e}")


def _save_pagespeed_analysis(audit_id: int, analysis_md: str):
    if not settings.AUDIT_LOCAL_ARTIFACTS_ENABLED:
        logger.info(
            f"Skipping local pagespeed analysis artifact for audit {audit_id} (Supabase-only mode)."
        )
        return
    """Guardar análisis de PageSpeed en Markdown"""
    try:
        from pathlib import Path

        reports_dir = Path(settings.REPORTS_DIR or "reports") / f"audit_{audit_id}"
        reports_dir.mkdir(parents=True, exist_ok=True)

        analysis_path = reports_dir / "pagespeed_analysis.md"
        with open(analysis_path, "w", encoding="utf-8") as f:
            f.write(analysis_md)

        logger.info(f"PageSpeed analysis saved to {analysis_path}")
    except Exception as e:
        logger.error(f"Error saving PageSpeed analysis for audit {audit_id}: {e}")


def _save_individual_pages(db: Session, audit_id: int, pipeline_result: dict):
    """Guardar páginas auditadas individuales como en ag2_pipeline.py"""
    try:
        target_audit = pipeline_result.get("target_audit", {})
        if not isinstance(target_audit, dict):
            return

        # Obtener páginas auditadas del resultado agregado
        audited_page_paths = target_audit.get("audited_page_paths", [])
        audited_pages_count = target_audit.get("audited_pages_count", 0)

        # NUEVO: Verificar si hay datos individuales de páginas
        individual_page_audits = target_audit.get("_individual_page_audits", [])

        if individual_page_audits:
            # Usar datos individuales reales de cada página
            logger.info(
                f"Encontrados {len(individual_page_audits)} reportes individuales de páginas"
            )

            for page_audit in individual_page_audits:
                page_index = page_audit.get("index", 0)
                page_url = page_audit.get("url")
                page_data = page_audit.get("data", {})

                if page_url and page_data:
                    try:
                        AuditService.save_page_audit(
                            db=db,
                            audit_id=audit_id,
                            page_url=page_url,
                            audit_data=page_data,
                            page_index=page_index,
                        )
                    except Exception as e:
                        logger.error(f"Error guardando página {page_url}: {e}")

            logger.info(
                f"Guardadas {len(individual_page_audits)} páginas auditadas para audit {audit_id}"
            )
            return

        # FALLBACK: Si no hay datos individuales, usar el método anterior
        if not audited_page_paths or audited_pages_count == 0:
            # Si no hay páginas múltiples, guardar solo la principal
            page_url = target_audit.get("url")
            if page_url and target_audit.get("status") == 200:
                AuditService.save_page_audit(
                    db=db,
                    audit_id=audit_id,
                    page_url=page_url,
                    audit_data=target_audit,
                    page_index=0,
                )
                logger.info(f"Guardada 1 página auditada para audit {audit_id}")
            else:
                logger.info(f"Guardadas 0 páginas auditadas para audit {audit_id}")
            return

        # Guardar cada página auditada (método anterior - datos agregados)
        audit = AuditService.get_audit(db, audit_id)
        if not audit:
            return

        base_url = str(audit.url).rstrip("/")

        for i, page_path in enumerate(audited_page_paths):
            # Reconstruir URL completa
            if page_path.startswith("http"):
                page_url = page_path
            elif page_path.startswith("/"):
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
                "schema": target_audit.get("schema", {}),
            }

            # Guardar página auditada
            AuditService.save_page_audit(
                db=db,
                audit_id=audit_id,
                page_url=page_url,
                audit_data=page_audit_data,
                page_index=i,
            )

        logger.info(
            f"Guardadas {len(audited_page_paths)} páginas auditadas para audit {audit_id}"
        )
    except Exception as e:
        logger.error(
            f"Error guardando páginas individuales para audit {audit_id}: {e}",
            exc_info=True,
        )


@celery_app.task(name="generate_pdf_task")
def generate_pdf_task(audit_id: int, report_markdown: str):
    """
    Deprecated legacy wrapper kept for compatibility.
    Delegates to the canonical PDF job flow.
    """
    logger.warning(
        "generate_pdf_task is deprecated; delegating to canonical PDF job flow for audit_id=%s",
        audit_id,
    )

    with get_db_session() as db:
        audit = AuditService.get_audit(db, audit_id)
        if not audit:
            logger.error(f"Audit {audit_id} not found for PDF generation.")
            raise ValueError(f"Audit {audit_id} not found for PDF generation")
        if report_markdown and not audit.report_markdown:
            audit.report_markdown = report_markdown
            db.add(audit)
            db.commit()

        job = PDFJobService.queue_job(
            db,
            audit_id=audit_id,
            requested_by_user_id=getattr(audit, "user_id", None),
            force_pagespeed_refresh=False,
            force_report_refresh=not bool(report_markdown),
            force_external_intel_refresh=False,
        )

    return run_pdf_generation_job_task.run(job.id)


@celery_app.task(
    name="run_pagespeed_task",
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 60},
    soft_time_limit=300,
    time_limit=360,
)
def run_pagespeed_task(self, audit_id: int):
    """Deprecated legacy wrapper kept for compatibility."""
    logger.warning(
        "run_pagespeed_task is deprecated; delegating to canonical PageSpeed job flow for audit_id=%s",
        audit_id,
    )
    with get_db_session() as db:
        audit = AuditService.get_audit(db, audit_id)
        if not audit:
            raise ValueError(f"Audit {audit_id} not found")

        job = PageSpeedJobService.queue_if_needed(
            db,
            audit=audit,
            requested_by_user_id=getattr(audit, "user_id", None),
            strategy="both",
            force_refresh=True,
        )
        if job is None:
            return {"audit_id": audit_id, "status": "skipped"}

    return run_pagespeed_generation_job_task.run(job.id)


def _set_article_batch_task_state(
    db: Session,
    *,
    batch_id: int,
    task_id: str | None = None,
    task_state: str | None = None,
    failure_reason: str | None = None,
    mark_failed: bool = False,
) -> None:
    batch = db.query(GeoArticleBatch).filter(GeoArticleBatch.id == batch_id).first()
    if not batch:
        return

    now_iso = datetime.now(timezone.utc).isoformat()
    summary = dict(batch.summary or {})
    if task_id:
        summary["task_id"] = task_id
    if task_state:
        summary["task_state"] = task_state
    summary["last_progress_at"] = now_iso
    if failure_reason:
        summary["failure_reason"] = failure_reason[:500]
    if mark_failed:
        batch.status = "failed"
        summary["completed_at"] = now_iso

    batch.summary = summary
    db.commit()


@celery_app.task(
    name="generate_article_batch_task",
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 2, "countdown": 20},
    soft_time_limit=2400,
    time_limit=2700,
)
def generate_article_batch_task(self, batch_id: int):
    """Background processing for GEO Article Engine batches."""
    task_id = str(getattr(self.request, "id", "") or "")
    logger.info(f"Starting article batch task for batch_id={batch_id}")
    try:
        from app.services.geo_article_engine_service import GeoArticleEngineService

        with get_db_session() as db:
            _set_article_batch_task_state(
                db,
                batch_id=batch_id,
                task_id=task_id,
                task_state="STARTED",
            )

        with get_db_session() as db:
            run_worker_coroutine(GeoArticleEngineService.process_batch(db, batch_id))

        with get_db_session() as db:
            _set_article_batch_task_state(
                db,
                batch_id=batch_id,
                task_id=task_id,
                task_state="SUCCESS",
            )

        logger.info(f"Article batch {batch_id} processed successfully.")
        return {"batch_id": batch_id, "status": "completed"}
    except Exception as e:
        max_retries = int(getattr(self, "max_retries", 0) or 0)
        current_retry = int(getattr(self.request, "retries", 0) or 0)
        will_retry = current_retry < max_retries
        task_state = "RETRY" if will_retry else "FAILURE"
        failure_reason = f"{type(e).__name__}: {e}"

        try:
            with get_db_session() as db:
                _set_article_batch_task_state(
                    db,
                    batch_id=batch_id,
                    task_id=task_id,
                    task_state=task_state,
                    failure_reason=failure_reason,
                    mark_failed=not will_retry,
                )
        except Exception as status_exc:  # nosec B110
            logger.warning(
                f"Unable to persist article batch task state for batch {batch_id}: {status_exc}"
            )

        logger.error(f"Error in article batch task {batch_id}: {e}", exc_info=True)
        raise


@celery_app.task(name="generate_full_report_task")
def generate_full_report_task(audit_id: int):
    """
    Deprecated legacy wrapper kept for compatibility.
    Delegates to the canonical PDF job flow with fresh report/context regeneration.
    """
    logger.warning(
        "generate_full_report_task is deprecated; delegating to canonical PDF job flow for audit_id=%s",
        audit_id,
    )
    with get_db_session() as db:
        audit = AuditService.get_audit(db, audit_id)
        if not audit:
            raise ValueError(f"Audit {audit_id} not found")

        job = PDFJobService.queue_job(
            db,
            audit_id=audit_id,
            requested_by_user_id=getattr(audit, "user_id", None),
            force_pagespeed_refresh=True,
            force_report_refresh=True,
            force_external_intel_refresh=True,
        )

    return run_pdf_generation_job_task.run(job.id)
