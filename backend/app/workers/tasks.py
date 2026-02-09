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
    retry_kwargs={"max_retries": 5, "countdown": 60},
    soft_time_limit=3600,  # 60 minutes for 50 pages
    time_limit=4000,
)
def run_audit_task(self, audit_id: int):
    """
    Tarea de Celery para ejecutar el pipeline completo.
    Mejorada con reintentos inteligentes para evitar condiciones de carrera.
    """
    logger.info(f"Celery task '{self.name}' [ID: {self.request.id}] started for audit_id: {audit_id}")

    # No usamos time.sleep(2). Usamos lógica de reintento.
    
    try:
        with get_db_session() as db:
            audit = AuditService.get_audit(db, audit_id)
            if not audit:
                # Si la transacción del API aún no terminó, la auditoría no existirá aquí.
                # Reintentamos en 2 segundos sin contar como error grave.
                logger.warning(f"Audit {audit_id} not found yet, retrying in 2s...")
                raise self.retry(exc=ValueError(f"Audit {audit_id} not found"), countdown=2, max_retries=5)

            # 1. Marcar la auditoría como RUNNING
            AuditService.update_audit_progress(
                db=db, audit_id=audit_id, progress=5, status=AuditStatus.RUNNING
            )
            
            # Guardamos la URL y el contexto para usarla fuera del bloque de sesión
            audit_url = str(audit.url)
            audit_market = audit.market
            audit_language = audit.language
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
                    logger.error(f"AuditLocalService.run_local_audit returned non-dict for {url}: {type(summary)}")
                    return {"status": 500, "url": url, "error": "Invalid audit result type"}

                return summary
            except Exception as audit_error:
                logger.error(f"Error in audit_local_service_func for {url}: {audit_error}", exc_info=True)
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
        target_audit_result = asyncio.run(audit_local_service_func(audit_url))
        
        if not target_audit_result or target_audit_result.get("status") == 500:
            logger.error(f"Failed to run local audit on target URL: {audit_url}")
            target_audit_result = {"url": audit_url, "status": 500, "error": "Failed to crawl target site"}
        else:
            logger.info(f"Local audit completed for {audit_url}: status={target_audit_result.get('status')}")
        
        # Enriquecer con mercado/idioma/domino desde la auditoría si no viene en el resumen
        if isinstance(target_audit_result, dict):
            if audit_market and not target_audit_result.get("market"):
                target_audit_result["market"] = audit_market
            if audit_language and not target_audit_result.get("language"):
                target_audit_result["language"] = audit_language
            if audit_domain and not target_audit_result.get("domain"):
                target_audit_result["domain"] = audit_domain
            if audit_competitors and not target_audit_result.get("competitors"):
                target_audit_result["competitors"] = audit_competitors

        # Ejecutar pipeline principal de auditoría INICIAL (sin GEO tools, sin reporte pesado)
        # Este nuevo flujo es exclusivamente para errores (fix plan) y competidores.
        from app.services.pipeline_service import run_initial_audit
        result = asyncio.run(run_initial_audit(
            url=audit_url,
            target_audit=target_audit_result,
            audit_id=audit_id,
            llm_function=llm_function,
            google_api_key=settings.GOOGLE_API_KEY,
            google_cx_id=settings.CSE_ID,
            crawler_service=CrawlerService.crawl_site,
            audit_local_service=audit_local_service_func
        ))
        


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
                    ps_analysis = asyncio.run(PipelineService.generate_pagespeed_analysis(
                        pagespeed_data, llm_function
                    ))
                    if ps_analysis:
                        _save_pagespeed_analysis(audit_id, ps_analysis)
                except Exception as e:
                    logger.error(f"Error generating PageSpeed analysis: {e}")

            # Guardar resultados y marcar como COMPLETED
            asyncio.run(AuditService.set_audit_results(
                db=db,
                audit_id=audit_id,
                target_audit=target_audit,
                external_intelligence=external_intelligence,
                search_results=search_results,
                competitor_audits=competitor_audits,
                report_markdown=report_markdown,
                fix_plan=fix_plan,
                pagespeed_data=pagespeed_data,
            ))

            AuditService.update_audit_progress(
                db=db, audit_id=audit_id, progress=100, status=AuditStatus.COMPLETED
            )
            logger.info(f"Audit {audit_id} completed successfully.")
            logger.info(f"Dashboard ready! PDF can be generated manually from the dashboard.")

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
            logger.critical(f"Failed to update audit {audit_id} status to FAILED: {db_error}", exc_info=True)
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
            from app.services.rank_tracker_service import RankTrackerService
            from app.services.backlink_service import BacklinkService
            from app.services.llm_visibility_service import LLMVisibilityService
            from urllib.parse import urlparse
            
            domain = urlparse(audit_url).netloc.replace("www.", "")
            brand_name = domain.split('.')[0]
            
            # Get category from existing intelligence if available
            category = None
            if audit.external_intelligence and isinstance(audit.external_intelligence, dict):
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
                visibility = await visibility_service.check_visibility(audit_id, brand_name, keywords)
                
                return rankings, backlinks, visibility

            # 3. Execute Tools
            rankings, backlinks, visibility = asyncio.run(run_geo_tools())
            
            # 4. Append/Update Report
            current_report = audit.report_markdown or ""
            
            # Check if GEO section already exists to avoid duplication (simple check)
            if "# 10. Análisis GEO Automático" not in current_report:
                geo_section = "\n\n# 10. Análisis GEO Automático (Anexos)\n\n"
                
                # Rank Tracking
                geo_section += "## 10.1 Rank Tracking Inicial\n"
                if rankings:
                    geo_section += "| Keyword | Posición | Top Competidor |\n|---|---|---|\n"
                    for r in rankings:
                        top_competitor = r.top_results[0]['domain'] if r.top_results else "N/A"
                        pos = f"#{r.position}" if r.position > 0 else ">10"
                        geo_section += f"| {r.keyword} | {pos} | {top_competitor} |\n"
                else:
                    geo_section += "*No se encontraron rankings.*\n"
                
                # Backlinks
                geo_section += "\n## 10.2 Análisis de Enlaces\n"
                geo_section += f"* **Total de Backlinks Encontrados**: {len(backlinks)}\n"
                dofollow_count = len([b for b in backlinks if b.is_dofollow])
                geo_section += f"* **Enlaces DoFollow**: {dofollow_count}\n"
                geo_section += f"* **Enlaces NoFollow**: {len(backlinks) - dofollow_count}\n"
                
                # LLM Visibility
                geo_section += "\n## 10.3 Visibilidad en IA (LLMs)\n"
                if visibility and len(visibility) > 0:
                    visible_count = sum(1 for v in visibility if v.get('is_visible', False))
                    total_queries = len(visibility)
                    visibility_rate = (visible_count / total_queries * 100) if total_queries > 0 else 0
                    
                    geo_section += f"* **Consultas Analizadas**: {total_queries}\n"
                    geo_section += f"* **Visibilidad**: {visible_count}/{total_queries} ({visibility_rate:.1f}%)\n"
                    geo_section += f"* **LLM**: {visibility[0].get('llm_name', 'KIMI')}\n"
                    
                    visible_queries = [v for v in visibility if v.get('is_visible', False)]
                    if visible_queries:
                        geo_section += "\n**Queries donde la marca es visible:**\n"
                        for v in visible_queries[:3]:
                            query = v.get('query', 'N/A')
                            citation = v.get('citation_text', '')[:100] + "..." if len(v.get('citation_text', '')) > 100 else v.get('citation_text', '')
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
                ReportService.create_report(
                    db=db, audit_id=audit_id, report_type="PDF", file_path=pdf_file_path
                )
            else:
                logger.info("GEO section already present in report.")

    except Exception as e:
        logger.error(f"Error running GEO Analysis task for audit {audit_id}: {e}", exc_info=True)
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


def _save_pagespeed_analysis(audit_id: int, analysis_md: str):
    """Guardar análisis de PageSpeed en Markdown"""
    try:
        from pathlib import Path
        
        reports_dir = Path(settings.REPORTS_DIR or "reports") / f"audit_{audit_id}"
        reports_dir.mkdir(parents=True, exist_ok=True)
        
        analysis_path = reports_dir / "pagespeed_analysis.md"
        with open(analysis_path, 'w', encoding='utf-8') as f:
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
            logger.info(f"Encontrados {len(individual_page_audits)} reportes individuales de páginas")
            
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
                            page_index=page_index
                        )
                    except Exception as e:
                        logger.error(f"Error guardando página {page_url}: {e}")
            
            logger.info(f"Guardadas {len(individual_page_audits)} páginas auditadas para audit {audit_id}")
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
                    page_index=0
                )
                logger.info(f"Guardada 1 página auditada para audit {audit_id}")
            else:
                logger.info(f"Guardadas 0 páginas auditadas para audit {audit_id}")
            return
        
        # Guardar cada página auditada (método anterior - datos agregados)
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


@celery_app.task(
    name="run_pagespeed_task",
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 60},
    soft_time_limit=300,
    time_limit=360,
)
def run_pagespeed_task(self, audit_id: int):
    """Tarea manual para PageSpeed"""
    logger.info(f"Starting PageSpeed task for audit {audit_id}")
    try:
        with get_db_session() as db:
            audit = AuditService.get_audit(db, audit_id)
            if not audit:
                raise ValueError(f"Audit {audit_id} not found")
            
            from app.services.pagespeed_service import PageSpeedService
            from app.services.pipeline_service import PipelineService
            from app.core.llm_kimi import get_llm_function
            
            # Run PageSpeed
            pagespeed_data = asyncio.run(PageSpeedService.analyze_both_strategies(
                url=str(audit.url),
                api_key=settings.GOOGLE_PAGESPEED_API_KEY
            ))
            
            if isinstance(pagespeed_data, Exception):
                raise pagespeed_data
                
            # Save Data
            _save_pagespeed_data(audit_id, pagespeed_data)
            
            # Generate Analysis
            llm_function = get_llm_function()
            ps_analysis = asyncio.run(PipelineService.generate_pagespeed_analysis(
                pagespeed_data, llm_function
            ))
            if ps_analysis:
                _save_pagespeed_analysis(audit_id, ps_analysis)
            
            # Update Audit in DB
            audit.pagespeed_data = pagespeed_data
            db.commit()
            logger.info(f"PageSpeed completed for audit {audit_id}")
            
    except Exception as e:
        logger.error(f"Error in PageSpeed task: {e}")
        raise


@celery_app.task(name="generate_full_report_task")
def generate_full_report_task(audit_id: int):
    """
    Orchestrator task for generating complete PDF report:
    1. Runs PageSpeed if missing
    2. Runs GEO Tools if missing (Keywords, Rankings, Backlinks, Visibility)
    3. REGENERATES the report markdown with LLM using ALL available data
    4. Generates the final PDF
    """
    logger.info(f"Starting Full Report Generation for audit {audit_id}")
    
    try:
        from app.services.pagespeed_service import PageSpeedService
        from app.services.pipeline_service import PipelineService
        from app.core.llm_kimi import get_llm_function
        from app.services.keyword_service import KeywordService
        from app.services.rank_tracker_service import RankTrackerService
        from app.services.backlink_service import BacklinkService
        from app.services.llm_visibility_service import LLMVisibilityService
        from urllib.parse import urlparse
        
        llm_function = get_llm_function()
        
        # Step 1: Run PageSpeed if missing
        with get_db_session() as db:
            audit = AuditService.get_audit(db, audit_id)
            if not audit:
                raise ValueError(f"Audit {audit_id} not found")
            
            audit_url = str(audit.url)
            domain = urlparse(audit_url).netloc.replace("www.", "")
            brand_name = domain.split('.')[0]
            
            if not audit.pagespeed_data:
                logger.info("PageSpeed data missing, running analysis...")
                pagespeed_data = asyncio.run(PageSpeedService.analyze_both_strategies(
                    url=audit_url,
                    api_key=settings.GOOGLE_PAGESPEED_API_KEY
                ))
                
                if pagespeed_data and not isinstance(pagespeed_data, Exception):
                    _save_pagespeed_data(audit_id, pagespeed_data)
                    ps_analysis = asyncio.run(PipelineService.generate_pagespeed_analysis(
                        pagespeed_data, llm_function
                    ))
                    if ps_analysis:
                        _save_pagespeed_analysis(audit_id, ps_analysis)
                    
                    audit.pagespeed_data = pagespeed_data
                    db.commit()
                    logger.info("PageSpeed data collected.")
        
        # Step 2: Run GEO Tools if missing
        with get_db_session() as db:
            audit = AuditService.get_audit(db, audit_id)
            audit_url = str(audit.url)
            domain = urlparse(audit_url).netloc.replace("www.", "")
            brand_name = domain.split('.')[0]
            
            category = None
            if audit.external_intelligence and isinstance(audit.external_intelligence, dict):
                category = audit.external_intelligence.get("category")
            
            keywords = [brand_name]
            if category:
                keywords.append(category)
            
            # Check if we have GEO data
            has_keywords = len(audit.keywords) > 0 if hasattr(audit, 'keywords') else False
            has_rankings = len(audit.rank_trackings) > 0 if hasattr(audit, 'rank_trackings') else False
            has_backlinks = len(audit.backlinks) > 0 if hasattr(audit, 'backlinks') else False
            has_visibility = len(audit.llm_visibilities) > 0 if hasattr(audit, 'llm_visibilities') else False
            
            if not (has_keywords and has_rankings and has_backlinks and has_visibility):
                logger.info("GEO data missing, running analysis...")
                
                async def run_geo_tools():
                    kw_service = KeywordService(db)
                    rank_service = RankTrackerService(db)
                    backlink_service = BacklinkService(db)
                    visibility_service = LLMVisibilityService(db)
                    
                    if not has_keywords:
                        await kw_service.research_keywords(audit_id, domain, [brand_name])
                    if not has_rankings:
                        await rank_service.track_rankings(audit_id, domain, keywords)
                    if not has_backlinks:
                        await backlink_service.analyze_backlinks(audit_id, domain)
                    if not has_visibility:
                        await visibility_service.check_visibility(audit_id, brand_name, keywords)

                asyncio.run(run_geo_tools())
                logger.info("GEO data collected.")
        
        # Step 3: REGENERATE report with LLM using ALL available context
        with get_db_session() as db:
            # FORCE refresh of all objects to ensure we see the GEO data from previous step
            db.expire_all()
            
            audit = AuditService.get_audit(db, audit_id)
            
            # Load complete context with ALL data
            complete_context = AuditService.get_complete_audit_context(db, audit_id)
            
            # Prepare data for report generation
            target_audit = audit.target_audit or {}
            external_intelligence = audit.external_intelligence or {}
            search_results = audit.search_results or {}
            competitor_audits = audit.competitor_audits or []
            pagespeed_data = audit.pagespeed_data or {}
            
            # Get GEO data from context (now already normalized with 'items' key)
            keywords_data = complete_context.get("keywords", {})
            backlinks_data = complete_context.get("backlinks", {})
            rank_tracking_data = complete_context.get("rank_tracking", {})
            llm_visibility_data = complete_context.get("llm_visibility", {})
            ai_content_data = complete_context.get("ai_content_suggestions", {})
            
            logger.info(f"Regenerating report with full context:")
            logger.info(f"  - Target Audit: {'OK' if target_audit else 'MISSING'}")
            logger.info(f"  - PageSpeed: {'OK' if pagespeed_data else 'MISSING'}")
            logger.info(f"  - Keywords: {len(keywords_data.get('items', []))} items")
            logger.info(f"  - Backlinks: {len(backlinks_data.get('items', []))} items")
            logger.info(f"  - Rank Tracking: {len(rank_tracking_data.get('items', []))} items")
            logger.info(f"  - LLM Visibility: {len(llm_visibility_data.get('items', []))} items")

            # Persist all data to disk for consistency and debugging before LLM call
            # This updates JSON files in the report folder and final_llm_context.json
            asyncio.run(AuditService._save_audit_files(
                audit_id=audit_id,
                target_audit=target_audit,
                external_intelligence=external_intelligence,
                search_results=search_results,
                competitor_audits=competitor_audits,
                fix_plan=fix_plan,
                pagespeed_data=pagespeed_data,
                keywords=keywords_data.get("items", []),
                backlinks=backlinks_data.get("items", []),
                rankings=rank_tracking_data.get("items", []),
                llm_visibility=llm_visibility_data.get("items", [])
            ))
            logger.info("Audit files persisted to disk successfully.")
            
            # Regenerate report markdown with LLM
            new_report_markdown, new_fix_plan = asyncio.run(
                PipelineService.generate_report(
                    target_audit=target_audit,
                    external_intelligence=external_intelligence,
                    search_results=search_results,
                    competitor_audits=competitor_audits,
                    pagespeed_data=pagespeed_data,
                    keywords_data=keywords_data,
                    backlinks_data=backlinks_data,
                    rank_tracking_data=rank_tracking_data,
                    llm_visibility_data=llm_visibility_data,
                    ai_content_suggestions=ai_content_data,
                    llm_function=llm_function
                )
            )
            
            # Update audit with new report
            if new_report_markdown and len(new_report_markdown) > 200:
                audit.report_markdown = new_report_markdown
                # Always update fix_plan if we got a response (even if empty)
                audit.fix_plan = new_fix_plan if new_fix_plan is not None else []
                db.commit()
                logger.info(f"Report regenerated with full context. Fix plan items: {len(audit.fix_plan)}")
            else:
                logger.warning("Report regeneration returned short content, keeping original.")
        
        # Step 4: Generate PDF
        with get_db_session() as db:
            audit = AuditService.get_audit(db, audit_id)
            logger.info(f"Generating Final PDF for audit {audit_id}")
            pdf_file_path = PDFService.create_from_audit(
                audit=audit, markdown_content=audit.report_markdown
            )
            ReportService.create_report(
                db=db, audit_id=audit_id, report_type="PDF", file_path=pdf_file_path
            )
            logger.info(f"Final PDF generated: {pdf_file_path}")
            
    except Exception as e:
        logger.error(f"Error generating full report: {e}", exc_info=True)
        raise
