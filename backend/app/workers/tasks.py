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
    soft_time_limit=900,  # 15 minutes
    time_limit=1000,  # 16+ minutes
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
            
            # Guardamos la URL para usarla fuera del bloque de sesión
            audit_url = str(audit.url)

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

        # Importar crawler y PageSpeed
        from app.services.crawler_service import CrawlerService
        from app.services.pagespeed_service import PageSpeedService
        
        # Ejecutar pipeline principal (SIN PageSpeed automático)
        result = asyncio.run(PipelineService.run_complete_audit(
            url=audit_url,
            target_audit={},
            crawler_service=CrawlerService.crawl_site,
            audit_local_service=audit_local_service_func,
            llm_function=llm_function,
            google_api_key=settings.GOOGLE_API_KEY,
            google_cx_id=settings.CSE_ID,
        ))
        
        # Inicializar pagespeed vacío para consistencia
        result["pagespeed"] = {}


        # --- AUTO-RUN GEO TOOLS (Rank, Backlinks, Visibility) ---
        # DISABLED FOR MANUAL EXECUTION
        # try:
        #     with get_db_session() as db:
        #         logger.info(f"Auto-running GEO Tools for audit {audit_id}...")
        #         ...
        # except Exception as tool_error:
        #     logger.error(f"Error running auto GEO tools: {tool_error}", exc_info=True)
        
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
    Orchestrator task:
    1. Checks if GEO tools run. If not, runs them.
    2. Checks if PageSpeed run. If not, runs it.
    3. Generates final PDF.
    """
    logger.info(f"Starting Full Report Generation for audit {audit_id}")
    
    try:
        # 1. Run GEO Analysis (if missing)
        with get_db_session() as db:
            audit = AuditService.get_audit(db, audit_id)
            if "# 10. Análisis GEO Automático" not in (audit.report_markdown or ""):
                logger.info("GEO Analysis missing, running now...")
                
                # Import services
                from app.services.rank_tracker_service import RankTrackerService
                from app.services.backlink_service import BacklinkService
                from app.services.llm_visibility_service import LLMVisibilityService
                from urllib.parse import urlparse
                
                audit_url = str(audit.url)
                domain = urlparse(audit_url).netloc.replace("www.", "")
                brand_name = domain.split('.')[0]
                
                category = None
                if audit.external_intelligence and isinstance(audit.external_intelligence, dict):
                    category = audit.external_intelligence.get("category")
                
                keywords = [brand_name]
                if category:
                    keywords.append(category)
                
                async def run_geo_tools():
                    rank_service = RankTrackerService(db)
                    backlink_service = BacklinkService(db)
                    visibility_service = LLMVisibilityService(db)
                    
                    rankings = await rank_service.track_rankings(audit_id, domain, keywords)
                    backlinks = await backlink_service.analyze_backlinks(audit_id, domain)
                    visibility = await visibility_service.check_visibility(audit_id, brand_name, keywords)
                    return rankings, backlinks, visibility

                rankings, backlinks, visibility = asyncio.run(run_geo_tools())
                
                # Append to report
                current_report = audit.report_markdown or ""
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
                
                audit.report_markdown = current_report + geo_section
                db.commit()
                logger.info("GEO Analysis auto-completed for full report.")

        # 2. Run PageSpeed (if missing)
        with get_db_session() as db:
            audit = AuditService.get_audit(db, audit_id)
            if not audit.pagespeed_data:
                logger.info("PageSpeed data missing, running analysis...")
                # Run PageSpeed logic directly
                from app.services.pagespeed_service import PageSpeedService
                from app.services.pipeline_service import PipelineService
                from app.core.llm_kimi import get_llm_function
                
                pagespeed_data = asyncio.run(PageSpeedService.analyze_both_strategies(
                    url=str(audit.url),
                    api_key=settings.GOOGLE_PAGESPEED_API_KEY
                ))
                
                if not isinstance(pagespeed_data, Exception):
                    _save_pagespeed_data(audit_id, pagespeed_data)
                    llm_function = get_llm_function()
                    ps_analysis = asyncio.run(PipelineService.generate_pagespeed_analysis(
                        pagespeed_data, llm_function
                    ))
                    if ps_analysis:
                        _save_pagespeed_analysis(audit_id, ps_analysis)
                    
                    audit.pagespeed_data = pagespeed_data
                    db.commit()
                    logger.info("PageSpeed auto-completed for full report.")

        # 3. Generate PDF
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
