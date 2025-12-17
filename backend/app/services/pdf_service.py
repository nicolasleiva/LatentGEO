"""
Servicio para la generación de reportes en PDF.
"""
import os
import sys
import json
from datetime import datetime

from ..core.config import settings
from ..core.logger import get_logger
from ..models import Audit

logger = get_logger(__name__)

# Importar create_comprehensive_pdf desde el mismo directorio de servicios
try:
    from .create_pdf import create_comprehensive_pdf, FPDF_AVAILABLE
    PDF_GENERATOR_AVAILABLE = FPDF_AVAILABLE
except ImportError as e:
    logger.warning(f"No se pudo importar create_comprehensive_pdf: {e}. PDFs no estarán disponibles.")
    PDF_GENERATOR_AVAILABLE = False
    
    def create_comprehensive_pdf(report_folder_path):
        logger.error("create_comprehensive_pdf no está disponible")
        raise ImportError("create_pdf module not available")


class PDFService:
    """Encapsula la lógica para crear archivos PDF a partir de contenido."""

    @staticmethod
    def _load_complete_audit_context(db, audit_id: int) -> dict:
        """
        Load complete context from ALL audit features for LLM.
        
        This ensures the LLM has access to:
        - PageSpeed data (mobile + desktop)
        - Keywords research data
        - Backlinks analysis
        - Rank tracking data
        - LLM visibility analysis
        - AI content suggestions
        - Target audit data
        - External intelligence
        - Search results
        - Competitor audits
        
        Returns:
            Complete context dictionary for LLM
        """
        from .audit_service import AuditService
        from sqlalchemy.orm import Session
        
        logger.info(f"Loading complete audit context for audit {audit_id}")
        
        audit = AuditService.get_audit(db, audit_id)
        if not audit:
            logger.warning(f"Audit {audit_id} not found for context loading")
            return {}
        
        # Load related data from database
        keywords = []
        if hasattr(audit, 'keywords'):
            for k in audit.keywords:
                keywords.append({
                    "keyword": k.term if hasattr(k, 'term') else k.keyword if hasattr(k, 'keyword') else '',
                    "search_volume": (k.volume if hasattr(k, 'volume') else k.search_volume if hasattr(k, 'search_volume') else 0) or 0,
                    "difficulty": (k.difficulty if hasattr(k, 'difficulty') else 0) or 0,
                    "cpc": (k.cpc if hasattr(k, 'cpc') else 0) or 0,
                    "intent": k.intent if hasattr(k, 'intent') else '',
                    "current_rank": getattr(k, 'current_rank', None),
                    "opportunity_score": getattr(k, 'opportunity_score', None)
                })
        
        backlinks = {
            "total_backlinks": len(audit.backlinks) if hasattr(audit, 'backlinks') else 0,
            "referring_domains": len(set(b.source_url.split('/')[2] if '/' in b.source_url else b.source_url for b in audit.backlinks)) if hasattr(audit, 'backlinks') else 0,
            "top_backlinks": []
        }
        if hasattr(audit, 'backlinks'):
            for b in audit.backlinks[:20]:  # Top 20
                backlinks["top_backlinks"].append({
                    "source_url": b.source_url,
                    "target_url": b.target_url,
                    "anchor_text": b.anchor_text if hasattr(b, 'anchor_text') else '',
                    "domain_authority": (b.domain_authority if hasattr(b, 'domain_authority') else 0) or 0,
                    "page_authority": getattr(b, 'page_authority', 0) or 0,
                    "spam_score": getattr(b, 'spam_score', 0) or 0,
                    "link_type": "dofollow" if getattr(b, 'is_dofollow', True) else "nofollow"
                })
        
        rank_tracking = []
        if hasattr(audit, 'rank_trackings'):
            for r in audit.rank_trackings:
                rank_tracking.append({
                    "keyword": r.keyword,
                    "position": (r.position or 100),
                    "url": r.url,
                    "search_engine": getattr(r, 'search_engine', 'google'),
                    "location": r.location if hasattr(r, 'location') else 'US',
                    "device": r.device if hasattr(r, 'device') else 'desktop',
                    "previous_position": getattr(r, 'previous_position', None),
                    "change": ((r.position or 100) - getattr(r, 'previous_position', 0)) if getattr(r, 'previous_position', None) else 0
                })
        
        llm_visibility = []
        if hasattr(audit, 'llm_visibilities'):
            for l in audit.llm_visibilities:
                llm_visibility.append({
                    "query": l.query,
                    "llm_platform": l.llm_name if hasattr(l, 'llm_name') else getattr(l, 'llm_platform', ''),
                    "mentioned": l.is_visible if hasattr(l, 'is_visible') else getattr(l, 'mentioned', False),
                    "position": l.rank if hasattr(l, 'rank') else getattr(l, 'position', None),
                    "context": l.citation_text if hasattr(l, 'citation_text') else getattr(l, 'context', ''),
                    "sentiment": getattr(l, 'sentiment', 'neutral'),
                    "competitors_mentioned": getattr(l, 'competitors_mentioned', [])
                })
        
        ai_content_suggestions = []
        if hasattr(audit, 'ai_content_suggestions') and audit.ai_content_suggestions:
            # Load from database
            for a in audit.ai_content_suggestions:
                ai_content_suggestions.append({
                    "title": a.topic if hasattr(a, 'topic') else getattr(a, 'title', ''),
                    "target_keyword": getattr(a, 'target_keyword', ''),
                    "content_type": a.suggestion_type if hasattr(a, 'suggestion_type') else getattr(a, 'content_type', ''),
                    "priority": a.priority if hasattr(a, 'priority') else 'medium',
                    "estimated_traffic": getattr(a, 'estimated_traffic', 0) or 0,
                    "difficulty": getattr(a, 'difficulty', 0) or 0,
                    "outline": a.content_outline if hasattr(a, 'content_outline') else getattr(a, 'outline', {})
                })
        else:
            # Generate on-demand when missing
            logger.info(f"AI content suggestions not found in DB for audit {audit_id}, generating on-demand")
            try:
                from .ai_content_service import AIContentService
                
                # Generate suggestions based on keywords
                generated_suggestions = AIContentService.generate_content_suggestions(
                    keywords=keywords,
                    url=str(audit.url)
                )
                
                # Convert to expected format
                for suggestion in generated_suggestions:
                    ai_content_suggestions.append({
                        "title": suggestion.get("title", ""),
                        "target_keyword": suggestion.get("target_keyword", ""),
                        "content_type": suggestion.get("content_type", ""),
                        "priority": suggestion.get("priority", "medium"),
                        "estimated_traffic": suggestion.get("estimated_traffic", 0),
                        "difficulty": suggestion.get("difficulty", 0),
                        "outline": suggestion.get("outline", {})
                    })
                
                logger.info(f"Generated {len(ai_content_suggestions)} AI content suggestions on-demand")
            except Exception as e:
                logger.error(f"Error generating AI content suggestions: {e}", exc_info=True)
                # Continue with empty list
        
        context = {
            # Core audit data
            "target_audit": audit.target_audit or {},
            "external_intelligence": audit.external_intelligence or {},
            "search_results": audit.search_results or {},
            "competitor_audits": audit.competitor_audits or [],
            
            # PageSpeed data (complete)
            "pagespeed": audit.pagespeed_data or {},
            
            # Keywords data
            "keywords": keywords,
            "keywords_summary": {
                "total_keywords": len(keywords),
                "high_volume_keywords": len([k for k in keywords if k.get("search_volume", 0) > 1000]),
                "low_difficulty_opportunities": len([k for k in keywords if k.get("difficulty", 100) < 30]),
                "average_difficulty": sum(k.get("difficulty", 0) for k in keywords) / len(keywords) if keywords else 0
            },
            
            # Backlinks data
            "backlinks": backlinks,
            "backlinks_summary": {
                "total_backlinks": backlinks["total_backlinks"],
                "referring_domains": backlinks["referring_domains"],
                "average_domain_authority": sum(b.get("domain_authority", 0) for b in backlinks["top_backlinks"]) / len(backlinks["top_backlinks"]) if backlinks["top_backlinks"] else 0,
                "dofollow_count": len([b for b in backlinks["top_backlinks"] if b.get("link_type") == "dofollow"]),
                "nofollow_count": len([b for b in backlinks["top_backlinks"] if b.get("link_type") == "nofollow"])
            },
            
            # Rank tracking data
            "rank_tracking": rank_tracking,
            "rank_tracking_summary": {
                "total_tracked_keywords": len(rank_tracking),
                "top_10_rankings": len([r for r in rank_tracking if r.get("position", 100) <= 10]),
                "top_3_rankings": len([r for r in rank_tracking if r.get("position", 100) <= 3]),
                "average_position": sum(r.get("position", 100) for r in rank_tracking) / len(rank_tracking) if rank_tracking else 0,
                "improved_rankings": len([r for r in rank_tracking if r.get("change", 0) < 0]),  # Negative change = improvement
                "declined_rankings": len([r for r in rank_tracking if r.get("change", 0) > 0])
            },
            
            # LLM visibility data
            "llm_visibility": llm_visibility,
            "llm_visibility_summary": {
                "total_queries_analyzed": len(llm_visibility),
                "mentions_count": len([l for l in llm_visibility if l.get("mentioned")]),
                "average_position": sum(l.get("position", 100) for l in llm_visibility if l.get("mentioned") and l.get("position")) / len([l for l in llm_visibility if l.get("mentioned") and l.get("position")]) if any(l.get("mentioned") and l.get("position") for l in llm_visibility) else 0,
                "platforms": list(set(l.get("llm_platform") for l in llm_visibility if l.get("llm_platform"))),
                "positive_sentiment": len([l for l in llm_visibility if l.get("sentiment") == "positive"]),
                "neutral_sentiment": len([l for l in llm_visibility if l.get("sentiment") == "neutral"]),
                "negative_sentiment": len([l for l in llm_visibility if l.get("sentiment") == "negative"])
            },
            
            # AI content suggestions
            "ai_content_suggestions": ai_content_suggestions,
            "content_suggestions_summary": {
                "total_suggestions": len(ai_content_suggestions),
                "high_priority": len([a for a in ai_content_suggestions if a.get("priority") == "high"]),
                "medium_priority": len([a for a in ai_content_suggestions if a.get("priority") == "medium"]),
                "low_priority": len([a for a in ai_content_suggestions if a.get("priority") == "low"]),
                "estimated_total_traffic": sum(a.get("estimated_traffic", 0) for a in ai_content_suggestions)
            }
        }
        
        logger.info(f"Complete context loaded for audit {audit_id}: {len(keywords)} keywords, {backlinks['total_backlinks']} backlinks, {len(rank_tracking)} rankings, {len(llm_visibility)} LLM visibility entries, {len(ai_content_suggestions)} content suggestions")
        return context

    @staticmethod
    def create_from_audit(audit: Audit, markdown_content: str) -> str:
        """
        Crea un reporte PDF completo para una auditoría específica.
        Usa create_comprehensive_pdf para generar el PDF con índice y anexos.

        Args:
            audit: La instancia del modelo Audit.
            markdown_content: El contenido del reporte en formato Markdown.

        Returns:
            La ruta completa al archivo PDF generado.
        """
        if not PDF_GENERATOR_AVAILABLE:
            logger.error("PDF generator no está disponible. Instalar fpdf2: pip install fpdf2")
            raise ImportError("PDF generator not available")
        
        logger.info(f"Iniciando generación de PDF para auditoría {audit.id}")

        reports_dir = os.path.join(settings.REPORTS_BASE_DIR, f"audit_{audit.id}")
        os.makedirs(reports_dir, exist_ok=True)

        # Guardar el markdown en ag2_report.md (requerido por create_comprehensive_pdf)
        md_file_path = os.path.join(reports_dir, "ag2_report.md")
        with open(md_file_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)
        
        # Guardar fix_plan.json si existe en audit.fix_plan
        if hasattr(audit, 'fix_plan') and audit.fix_plan:
            fix_plan_path = os.path.join(reports_dir, "fix_plan.json")
            try:
                fix_plan_data = json.loads(audit.fix_plan) if isinstance(audit.fix_plan, str) else audit.fix_plan
                with open(fix_plan_path, "w", encoding="utf-8") as f:
                    json.dump(fix_plan_data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.warning(f"No se pudo guardar fix_plan.json: {e}")
        
        # Guardar aggregated_summary.json si existe en audit.target_audit
        if hasattr(audit, 'target_audit') and audit.target_audit:
            agg_summary_path = os.path.join(reports_dir, "aggregated_summary.json")
            try:
                target_audit_data = json.loads(audit.target_audit) if isinstance(audit.target_audit, str) else audit.target_audit
                with open(agg_summary_path, "w", encoding="utf-8") as f:
                    json.dump(target_audit_data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.warning(f"No se pudo guardar aggregated_summary.json: {e}")
        
        # Llamar a create_comprehensive_pdf (igual que ag2_pipeline.py)
        try:
            create_comprehensive_pdf(reports_dir)
            
            # Buscar el PDF generado
            import glob
            pdf_files = glob.glob(os.path.join(reports_dir, "Reporte_Consolidado_*.pdf"))
            if pdf_files:
                pdf_file_path = pdf_files[0]
                logger.info(f"Reporte PDF guardado en: {pdf_file_path}")
                return pdf_file_path
            else:
                logger.error(f"No se encontró el PDF generado en {reports_dir}")
                raise FileNotFoundError("PDF file not generated")
        except Exception as e:
            logger.error(f"Error generando PDF con create_comprehensive_pdf: {e}", exc_info=True)
            raise


    @staticmethod
    def _is_pagespeed_stale(pagespeed_data: dict, max_age_hours: int = 24) -> bool:
        """
        Check if PageSpeed data is stale and needs refresh.
        
        Args:
            pagespeed_data: Cached PageSpeed data
            max_age_hours: Maximum age in hours before considering stale
            
        Returns:
            True if data is stale or invalid
        """
        if not pagespeed_data:
            return True
        
        # Check for mobile data (required)
        mobile_data = pagespeed_data.get("mobile", {})
        if not mobile_data or "error" in mobile_data:
            return True
        
        # Check timestamp
        fetch_time = mobile_data.get("metadata", {}).get("fetch_time")
        if not fetch_time:
            return True
        
        try:
            from datetime import datetime, timedelta, timezone
            # Parse ISO format timestamp
            if 'Z' in fetch_time:
                fetch_datetime = datetime.fromisoformat(fetch_time.replace('Z', '+00:00'))
            else:
                fetch_datetime = datetime.fromisoformat(fetch_time)
            
            # Make sure both datetimes are timezone-aware
            if fetch_datetime.tzinfo is None:
                fetch_datetime = fetch_datetime.replace(tzinfo=timezone.utc)
            
            now = datetime.now(timezone.utc)
            age = now - fetch_datetime
            is_stale = age > timedelta(hours=max_age_hours)
            
            logger.info(f"PageSpeed data age: {age.total_seconds() / 3600:.1f} hours, stale: {is_stale}")
            return is_stale
        except Exception as e:
            logger.warning(f"Error checking PageSpeed staleness: {e}")
            return True

    @staticmethod
    async def generate_pdf_with_complete_context(db, audit_id: int, force_pagespeed_refresh: bool = False) -> str:
        """
        Generate PDF report with complete context from all features.
        
        This method:
        1. Automatically runs PageSpeed if not cached or stale
        2. Loads ALL audit data (keywords, backlinks, rankings, etc.)
        3. Regenerates markdown report with complete context for LLM
        4. Generates PDF with the updated report
        
        Args:
            db: Database session
            audit_id: Audit ID
            force_pagespeed_refresh: If True, re-run PageSpeed even if cached
            
        Returns:
            Path to generated PDF file
        """
        from .audit_service import AuditService
        from .pagespeed_service import PageSpeedService
        from .pipeline_service import PipelineService
        from ..core.config import settings
        from ..core.llm_kimi import get_llm_function
        
        logger.info(f"=== Starting PDF generation with complete context for audit {audit_id} ===")
        
        # 1. Load audit
        audit = AuditService.get_audit(db, audit_id)
        if not audit:
            raise ValueError(f"Audit {audit_id} not found")
        
        # 2. Check if PageSpeed data exists and is recent
        pagespeed_data = audit.pagespeed_data
        needs_refresh = (
            force_pagespeed_refresh or
            not pagespeed_data or
            PDFService._is_pagespeed_stale(pagespeed_data)
        )
        
        # 3. Run PageSpeed if needed
        if needs_refresh:
            logger.info(f"Running PageSpeed analysis for audit {audit_id} before PDF generation")
            try:
                pagespeed_data = await PageSpeedService.analyze_both_strategies(
                    url=str(audit.url),
                    api_key=settings.GOOGLE_PAGESPEED_API_KEY
                )
                
                # Store in database
                AuditService.set_pagespeed_data(db, audit_id, pagespeed_data)
                logger.info(f"✓ PageSpeed data collected and stored")
            except Exception as e:
                logger.error(f"PageSpeed collection failed: {e}")
                pagespeed_data = None
        else:
            logger.info(f"✓ Using cached PageSpeed data (fresh)")
        
        # 4. Generate GEO Tools (Keywords, Backlinks, Rankings) ON-DEMAND
        logger.info(f"Generating GEO Tools (Keywords, Backlinks, Rankings) for PDF...")
        try:
            from .keywords_service import KeywordsService
            from .backlinks_service import BacklinksService
            from .rank_tracking_service import RankTrackingService
            from urllib.parse import urlparse
            
            audit_url = str(audit.url)
            domain = urlparse(audit_url).netloc.replace("www.", "")
            
            # Get category from existing intelligence if available
            category = None
            if audit.external_intelligence and isinstance(audit.external_intelligence, dict):
                category = audit.external_intelligence.get("category", "")
            
            # Generate data using services (synchronous)
            logger.info(f"  - Generating Keywords for {domain}")
            target_audit = audit.target_audit or {}
            keywords_data_list = KeywordsService.generate_keywords_from_audit(target_audit, audit_url)
            
            logger.info(f"  - Generating Backlinks for {domain}")
            backlinks_data_dict = BacklinksService.generate_backlinks_from_audit(target_audit, audit_url)
            
            logger.info(f"  - Generating Rankings for {domain}")
            rankings_data_list = RankTrackingService.generate_rankings_from_keywords(keywords_data_list, audit_url)
            
            # Format data for context
            keywords_data = {
                "keywords": keywords_data_list,
                "total_keywords": len(keywords_data_list),
                "top_opportunities": sorted(keywords_data_list, key=lambda x: x.get("opportunity_score", 0), reverse=True)[:10]
            }
            backlinks_data = backlinks_data_dict
            rank_tracking_data = {
                "rankings": rankings_data_list,
                "total_keywords": len(rankings_data_list),
                "distribution": {
                    "top_3": len([r for r in rankings_data_list if r.get("position", 100) <= 3]),
                    "top_10": len([r for r in rankings_data_list if r.get("position", 100) <= 10]),
                    "top_20": len([r for r in rankings_data_list if r.get("position", 100) <= 20]),
                    "beyond_20": len([r for r in rankings_data_list if r.get("position", 100) > 20])
                }
            }
            
            logger.info(f"✓ GEO Tools generated: {len(keywords_data_list)} keywords, {backlinks_data_dict.get('total_backlinks', 0)} backlinks, {len(rankings_data_list)} rankings")
            
        except Exception as tool_error:
            logger.error(f"Error generating GEO tools: {tool_error}", exc_info=True)
            # Continue with empty data
            keywords_data = {}
            backlinks_data = {}
            rank_tracking_data = {}
        
        # 5. Load COMPLETE context from ALL features (LLM visibility, AI content, etc.)
        complete_context = PDFService._load_complete_audit_context(db, audit_id)
        logger.info(f"✓ Complete context loaded with {len(complete_context)} feature types")
        
        # 6. Regenerate markdown report with complete context
        logger.info(f"Regenerating markdown report with complete context...")
        try:
            llm_function = get_llm_function()
            
            # Regenerate report with complete context (using freshly generated GEO tools data)
            markdown_report, fix_plan = await PipelineService.generate_report(
                target_audit=audit.target_audit or {},
                external_intelligence=audit.external_intelligence or {},
                search_results=audit.search_results or {},
                competitor_audits=audit.competitor_audits or [],
                pagespeed_data=pagespeed_data,
                keywords_data=keywords_data,  # Freshly generated
                backlinks_data=backlinks_data,  # Freshly generated
                rank_tracking_data=rank_tracking_data,  # Freshly generated
                llm_visibility_data=complete_context.get("llm_visibility", []),
                ai_content_suggestions=complete_context.get("ai_content_suggestions", []),
                llm_function=llm_function
            )
            
            # Update audit with new report
            audit.report_markdown = markdown_report
            audit.fix_plan = fix_plan
            db.commit()
            
            logger.info(f"✓ Markdown report regenerated with complete context")
        except Exception as e:
            logger.warning(f"Could not regenerate markdown report: {e}. Using existing report.")
        
        # 7. Get pages and competitors
        pages = AuditService.get_audited_pages(db, audit_id)
        from .audit_service import CompetitorService
        competitors = CompetitorService.get_competitors(db, audit_id)
        
        logger.info(f"✓ Loaded {len(pages)} pages and {len(competitors)} competitors")
        
        # 8. Generate PDF with complete context
        pdf_path = await PDFService.generate_comprehensive_pdf(
            audit=audit,
            pages=pages,
            competitors=competitors,
            pagespeed_data=pagespeed_data
        )
        
        logger.info(f"=== PDF generation completed: {pdf_path} ===")
        return pdf_path

    @staticmethod
    async def generate_comprehensive_pdf(audit: Audit, pages: list, competitors: list, pagespeed_data: dict = None) -> str:
        """
        Genera un PDF completo con todos los datos de la auditoría:
        - Datos de auditoría principal
        - Páginas auditadas
        - Competidores
        - PageSpeed data
        - Keywords
        - Rank tracking
        
        Args:
            audit: La instancia del modelo Audit
            pages: Lista de páginas auditadas
            competitors: Lista de competidores
            pagespeed_data: Datos de PageSpeed (opcional)
            
        Returns:
            La ruta completa al archivo PDF generado
        """
        if not PDF_GENERATOR_AVAILABLE:
            logger.error("PDF generator no está disponible. Instalar fpdf2: pip install fpdf2")
            raise ImportError("PDF generator not available")
        
        logger.info(f"Generando PDF completo para auditoría {audit.id} con todos los datos")
        
        reports_dir = os.path.join(settings.REPORTS_BASE_DIR, f"audit_{audit.id}")
        os.makedirs(reports_dir, exist_ok=True)
        
        # 1. Guardar markdown report
        if audit.report_markdown:
            md_file_path = os.path.join(reports_dir, "ag2_report.md")
            with open(md_file_path, "w", encoding="utf-8") as f:
                f.write(audit.report_markdown)
        
        # 2. Guardar fix_plan.json
        if audit.fix_plan:
            fix_plan_path = os.path.join(reports_dir, "fix_plan.json")
            try:
                fix_plan_data = json.loads(audit.fix_plan) if isinstance(audit.fix_plan, str) else audit.fix_plan
                with open(fix_plan_path, "w", encoding="utf-8") as f:
                    json.dump(fix_plan_data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.warning(f"No se pudo guardar fix_plan.json: {e}")
        
        # 3. Guardar aggregated_summary.json (target audit)
        if audit.target_audit:
            agg_summary_path = os.path.join(reports_dir, "aggregated_summary.json")
            try:
                target_audit_data = json.loads(audit.target_audit) if isinstance(audit.target_audit, str) else audit.target_audit
                with open(agg_summary_path, "w", encoding="utf-8") as f:
                    json.dump(target_audit_data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.warning(f"No se pudo guardar aggregated_summary.json: {e}")
        
        # 4. Guardar PageSpeed data
        if pagespeed_data:
            pagespeed_path = os.path.join(reports_dir, "pagespeed.json")
            try:
                with open(pagespeed_path, "w", encoding="utf-8") as f:
                    json.dump(pagespeed_data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.warning(f"No se pudo guardar pagespeed.json: {e}")
        
        # 5. Guardar datos de páginas
        if pages:
            pages_dir = os.path.join(reports_dir, "pages")
            os.makedirs(pages_dir, exist_ok=True)
            for page in pages:
                try:
                    page_data = {
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
                    page_filename = f"page_{page.id}.json"
                    page_path = os.path.join(pages_dir, page_filename)
                    with open(page_path, "w", encoding="utf-8") as f:
                        json.dump(page_data, f, indent=2, ensure_ascii=False)
                except Exception as e:
                    logger.warning(f"No se pudo guardar datos de página {page.id}: {e}")
        
        # 6. Guardar datos de competidores
        if competitors:
            competitors_dir = os.path.join(reports_dir, "competitors")
            os.makedirs(competitors_dir, exist_ok=True)
            for idx, comp in enumerate(competitors):
                try:
                    comp_data = comp if isinstance(comp, dict) else {
                        "url": getattr(comp, 'url', ''),
                        "geo_score": getattr(comp, 'geo_score', 0),
                        "audit_data": getattr(comp, 'audit_data', {})
                    }
                    comp_filename = f"competitor_{idx + 1}.json"
                    comp_path = os.path.join(competitors_dir, comp_filename)
                    with open(comp_path, "w", encoding="utf-8") as f:
                        json.dump(comp_data, f, indent=2, ensure_ascii=False)
                except Exception as e:
                    logger.warning(f"No se pudo guardar datos de competidor {idx}: {e}")
        
        # 7. Generar PDF con create_comprehensive_pdf
        try:
            create_comprehensive_pdf(reports_dir)
            
            # Buscar el PDF generado
            import glob
            pdf_files = glob.glob(os.path.join(reports_dir, "Reporte_Consolidado_*.pdf"))
            if pdf_files:
                pdf_file_path = pdf_files[0]
                logger.info(f"PDF completo generado en: {pdf_file_path}")
                return pdf_file_path
            else:
                logger.error(f"No se encontró el PDF generado en {reports_dir}")
                raise FileNotFoundError("PDF file not generated")
        except Exception as e:
            logger.error(f"Error generando PDF con create_comprehensive_pdf: {e}", exc_info=True)
            raise
