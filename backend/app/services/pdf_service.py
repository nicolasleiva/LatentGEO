"""
Servicio para la generación de reportes en PDF.
"""

import os
import sys
import json
from datetime import datetime
from typing import List, Dict, Any

from ..core.config import settings
from ..core.logger import get_logger
from ..models import Audit
from ..core.llm_kimi import get_llm_function

logger = get_logger(__name__)

# Importar create_comprehensive_pdf desde el mismo directorio de servicios
try:
    from .create_pdf import create_comprehensive_pdf, FPDF_AVAILABLE

    PDF_GENERATOR_AVAILABLE = FPDF_AVAILABLE
except ImportError as e:
    logger.warning(
        f"No se pudo importar create_comprehensive_pdf: {e}. PDFs no estarán disponibles."
    )
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
        if hasattr(audit, "keywords"):
            for k in audit.keywords:
                keywords.append(
                    {
                        "keyword": k.term
                        if hasattr(k, "term")
                        else k.keyword
                        if hasattr(k, "keyword")
                        else "",
                        "search_volume": (
                            k.volume
                            if hasattr(k, "volume")
                            else k.search_volume
                            if hasattr(k, "search_volume")
                            else 0
                        )
                        or 0,
                        "difficulty": (k.difficulty if hasattr(k, "difficulty") else 0)
                        or 0,
                        "cpc": (k.cpc if hasattr(k, "cpc") else 0) or 0,
                        "intent": k.intent if hasattr(k, "intent") else "",
                        "current_rank": getattr(k, "current_rank", None),
                        "opportunity_score": getattr(k, "opportunity_score", None),
                    }
                )

        backlinks = {
            "total_backlinks": len(audit.backlinks)
            if hasattr(audit, "backlinks")
            else 0,
            "referring_domains": len(
                set(
                    b.source_url.split("/")[2] if "/" in b.source_url else b.source_url
                    for b in audit.backlinks
                )
            )
            if hasattr(audit, "backlinks")
            else 0,
            "top_backlinks": [],
        }
        if hasattr(audit, "backlinks"):
            for b in audit.backlinks[:20]:  # Top 20
                backlinks["top_backlinks"].append(
                    {
                        "source_url": b.source_url,
                        "target_url": b.target_url,
                        "anchor_text": b.anchor_text
                        if hasattr(b, "anchor_text")
                        else "",
                        "domain_authority": (
                            b.domain_authority if hasattr(b, "domain_authority") else 0
                        )
                        or 0,
                        "page_authority": getattr(b, "page_authority", 0) or 0,
                        "spam_score": getattr(b, "spam_score", 0) or 0,
                        "link_type": "dofollow"
                        if getattr(b, "is_dofollow", True)
                        else "nofollow",
                    }
                )

        rank_tracking = []
        if hasattr(audit, "rank_trackings"):
            for r in audit.rank_trackings:
                rank_tracking.append(
                    {
                        "keyword": r.keyword,
                        "position": (r.position or 100),
                        "url": r.url,
                        "search_engine": getattr(r, "search_engine", "google"),
                        "location": r.location if hasattr(r, "location") else "US",
                        "device": r.device if hasattr(r, "device") else "desktop",
                        "previous_position": getattr(r, "previous_position", None),
                        "change": (
                            (r.position or 100) - getattr(r, "previous_position", 0)
                        )
                        if getattr(r, "previous_position", None)
                        else 0,
                    }
                )

        llm_visibility = []
        if hasattr(audit, "llm_visibilities"):
            for l in audit.llm_visibilities:
                llm_visibility.append(
                    {
                        "query": l.query,
                        "llm_platform": l.llm_name
                        if hasattr(l, "llm_name")
                        else getattr(l, "llm_platform", ""),
                        "mentioned": l.is_visible
                        if hasattr(l, "is_visible")
                        else getattr(l, "mentioned", False),
                        "position": l.rank
                        if hasattr(l, "rank")
                        else getattr(l, "position", None),
                        "context": l.citation_text
                        if hasattr(l, "citation_text")
                        else getattr(l, "context", ""),
                        "sentiment": getattr(l, "sentiment", "neutral"),
                        "competitors_mentioned": getattr(
                            l, "competitors_mentioned", []
                        ),
                    }
                )

        ai_content_suggestions = []
        if hasattr(audit, "ai_content_suggestions") and audit.ai_content_suggestions:
            # Load from database
            for a in audit.ai_content_suggestions:
                ai_content_suggestions.append(
                    {
                        "title": a.topic
                        if hasattr(a, "topic")
                        else getattr(a, "title", ""),
                        "target_keyword": getattr(a, "target_keyword", ""),
                        "content_type": a.suggestion_type
                        if hasattr(a, "suggestion_type")
                        else getattr(a, "content_type", ""),
                        "priority": a.priority if hasattr(a, "priority") else "medium",
                        "estimated_traffic": getattr(a, "estimated_traffic", 0) or 0,
                        "difficulty": getattr(a, "difficulty", 0) or 0,
                        "outline": a.content_outline
                        if hasattr(a, "content_outline")
                        else getattr(a, "outline", {}),
                    }
                )
        else:
            # Generate on-demand when missing
            logger.info(
                f"AI content suggestions not found in DB for audit {audit_id}, generating on-demand"
            )
            try:
                from .ai_content_service import AIContentService

                # Generate suggestions based on keywords
                generated_suggestions = AIContentService.generate_content_suggestions(
                    keywords=keywords, url=str(audit.url)
                )

                # Convert to expected format
                for suggestion in generated_suggestions:
                    ai_content_suggestions.append(
                        {
                            "title": suggestion.get("title", ""),
                            "target_keyword": suggestion.get("target_keyword", ""),
                            "content_type": suggestion.get("content_type", ""),
                            "priority": suggestion.get("priority", "medium"),
                            "estimated_traffic": suggestion.get("estimated_traffic", 0),
                            "difficulty": suggestion.get("difficulty", 0),
                            "outline": suggestion.get("outline", {}),
                        }
                    )

                logger.info(
                    f"Generated {len(ai_content_suggestions)} AI content suggestions on-demand"
                )
            except Exception as e:
                logger.error(
                    f"Error generating AI content suggestions: {e}", exc_info=True
                )
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
                "high_volume_keywords": len(
                    [k for k in keywords if k.get("search_volume", 0) > 1000]
                ),
                "low_difficulty_opportunities": len(
                    [k for k in keywords if k.get("difficulty", 100) < 30]
                ),
                "average_difficulty": sum(k.get("difficulty", 0) for k in keywords)
                / len(keywords)
                if keywords
                else 0,
            },
            # Backlinks data
            "backlinks": backlinks,
            "backlinks_summary": {
                "total_backlinks": backlinks["total_backlinks"],
                "referring_domains": backlinks["referring_domains"],
                "average_domain_authority": sum(
                    b.get("domain_authority", 0) for b in backlinks["top_backlinks"]
                )
                / len(backlinks["top_backlinks"])
                if backlinks["top_backlinks"]
                else 0,
                "dofollow_count": len(
                    [
                        b
                        for b in backlinks["top_backlinks"]
                        if b.get("link_type") == "dofollow"
                    ]
                ),
                "nofollow_count": len(
                    [
                        b
                        for b in backlinks["top_backlinks"]
                        if b.get("link_type") == "nofollow"
                    ]
                ),
            },
            # Rank tracking data
            "rank_tracking": rank_tracking,
            "rank_tracking_summary": {
                "total_tracked_keywords": len(rank_tracking),
                "top_10_rankings": len(
                    [r for r in rank_tracking if r.get("position", 100) <= 10]
                ),
                "top_3_rankings": len(
                    [r for r in rank_tracking if r.get("position", 100) <= 3]
                ),
                "average_position": sum(r.get("position", 100) for r in rank_tracking)
                / len(rank_tracking)
                if rank_tracking
                else 0,
                "improved_rankings": len(
                    [r for r in rank_tracking if r.get("change", 0) < 0]
                ),  # Negative change = improvement
                "declined_rankings": len(
                    [r for r in rank_tracking if r.get("change", 0) > 0]
                ),
            },
            # LLM visibility data
            "llm_visibility": llm_visibility,
            "llm_visibility_summary": {
                "total_queries_analyzed": len(llm_visibility),
                "mentions_count": len(
                    [l for l in llm_visibility if l.get("mentioned")]
                ),
                "average_position": sum(
                    l.get("position", 100)
                    for l in llm_visibility
                    if l.get("mentioned") and l.get("position")
                )
                / len(
                    [
                        l
                        for l in llm_visibility
                        if l.get("mentioned") and l.get("position")
                    ]
                )
                if any(l.get("mentioned") and l.get("position") for l in llm_visibility)
                else 0,
                "platforms": list(
                    set(
                        l.get("llm_platform")
                        for l in llm_visibility
                        if l.get("llm_platform")
                    )
                ),
                "positive_sentiment": len(
                    [l for l in llm_visibility if l.get("sentiment") == "positive"]
                ),
                "neutral_sentiment": len(
                    [l for l in llm_visibility if l.get("sentiment") == "neutral"]
                ),
                "negative_sentiment": len(
                    [l for l in llm_visibility if l.get("sentiment") == "negative"]
                ),
            },
            # AI content suggestions
            "ai_content_suggestions": ai_content_suggestions,
            "content_suggestions_summary": {
                "total_suggestions": len(ai_content_suggestions),
                "high_priority": len(
                    [a for a in ai_content_suggestions if a.get("priority") == "high"]
                ),
                "medium_priority": len(
                    [a for a in ai_content_suggestions if a.get("priority") == "medium"]
                ),
                "low_priority": len(
                    [a for a in ai_content_suggestions if a.get("priority") == "low"]
                ),
                "estimated_total_traffic": sum(
                    a.get("estimated_traffic", 0) for a in ai_content_suggestions
                ),
            },
        }

        logger.info(
            f"Complete context loaded for audit {audit_id}: {len(keywords)} keywords, {backlinks['total_backlinks']} backlinks, {len(rank_tracking)} rankings, {len(llm_visibility)} LLM visibility entries, {len(ai_content_suggestions)} content suggestions"
        )
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
            logger.error(
                "PDF generator no está disponible. Instalar fpdf2: pip install fpdf2"
            )
            raise ImportError("PDF generator not available")

        logger.info(f"Iniciando generación de PDF para auditoría {audit.id}")

        reports_dir = os.path.join(settings.REPORTS_BASE_DIR, f"audit_{audit.id}")
        os.makedirs(reports_dir, exist_ok=True)

        # Guardar el markdown en ag2_report.md (requerido por create_comprehensive_pdf)
        md_file_path = os.path.join(reports_dir, "ag2_report.md")
        with open(md_file_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)

        # Guardar fix_plan.json si existe en audit.fix_plan
        if hasattr(audit, "fix_plan") and audit.fix_plan:
            fix_plan_path = os.path.join(reports_dir, "fix_plan.json")
            try:
                fix_plan_data = (
                    json.loads(audit.fix_plan)
                    if isinstance(audit.fix_plan, str)
                    else audit.fix_plan
                )
                with open(fix_plan_path, "w", encoding="utf-8") as f:
                    json.dump(fix_plan_data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.warning(f"No se pudo guardar fix_plan.json: {e}")

        # Guardar aggregated_summary.json si existe en audit.target_audit
        if hasattr(audit, "target_audit") and audit.target_audit:
            agg_summary_path = os.path.join(reports_dir, "aggregated_summary.json")
            try:
                target_audit_data = (
                    json.loads(audit.target_audit)
                    if isinstance(audit.target_audit, str)
                    else audit.target_audit
                )
                with open(agg_summary_path, "w", encoding="utf-8") as f:
                    json.dump(target_audit_data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.warning(f"No se pudo guardar aggregated_summary.json: {e}")

        # Guardar PageSpeed data
        if hasattr(audit, "pagespeed_data") and audit.pagespeed_data:
            pagespeed_path = os.path.join(reports_dir, "pagespeed.json")
            try:
                ps_data = (
                    json.loads(audit.pagespeed_data)
                    if isinstance(audit.pagespeed_data, str)
                    else audit.pagespeed_data
                )
                with open(pagespeed_path, "w", encoding="utf-8") as f:
                    json.dump(ps_data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.warning(f"No se pudo guardar pagespeed.json: {e}")

        # Guardar Keywords data
        if hasattr(audit, "keywords") and audit.keywords:
            keywords_path = os.path.join(reports_dir, "keywords.json")
            try:
                keywords_list = []
                for k in audit.keywords:
                    keywords_list.append(
                        {
                            "term": k.term,
                            "volume": k.volume,
                            "difficulty": k.difficulty,
                            "cpc": k.cpc,
                            "intent": k.intent,
                        }
                    )
                with open(keywords_path, "w", encoding="utf-8") as f:
                    json.dump(keywords_list, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.warning(f"No se pudo guardar keywords.json: {e}")

        # Guardar Backlinks data
        if hasattr(audit, "backlinks") and audit.backlinks:
            backlinks_path = os.path.join(reports_dir, "backlinks.json")
            try:
                backlinks_list = []
                for b in audit.backlinks:
                    backlinks_list.append(
                        {
                            "source_url": b.source_url,
                            "target_url": b.target_url,
                            "anchor_text": b.anchor_text,
                            "is_dofollow": b.is_dofollow,
                            "domain_authority": b.domain_authority,
                        }
                    )
                with open(backlinks_path, "w", encoding="utf-8") as f:
                    json.dump(backlinks_list, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.warning(f"No se pudo guardar backlinks.json: {e}")

        # Guardar Rankings data
        if hasattr(audit, "rank_trackings") and audit.rank_trackings:
            rankings_path = os.path.join(reports_dir, "rankings.json")
            try:
                rankings_list = []
                for r in audit.rank_trackings:
                    rankings_list.append(
                        {
                            "keyword": r.keyword,
                            "position": r.position,
                            "url": r.url,
                            "device": r.device,
                            "location": r.location,
                            "top_results": r.top_results,
                        }
                    )
                with open(rankings_path, "w", encoding="utf-8") as f:
                    json.dump(rankings_list, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.warning(f"No se pudo guardar rankings.json: {e}")

        # Guardar LLM Visibility data
        if hasattr(audit, "llm_visibilities") and audit.llm_visibilities:
            visibility_path = os.path.join(reports_dir, "llm_visibility.json")
            try:
                visibility_list = []
                for v in audit.llm_visibilities:
                    visibility_list.append(
                        {
                            "llm_name": v.llm_name,
                            "query": v.query,
                            "is_visible": v.is_visible,
                            "rank": v.rank,
                            "citation_text": v.citation_text,
                        }
                    )
                with open(visibility_path, "w", encoding="utf-8") as f:
                    json.dump(visibility_list, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.warning(f"No se pudo guardar llm_visibility.json: {e}")

        # Guardar páginas individuales
        if hasattr(audit, "pages") and audit.pages:
            pages_dir = os.path.join(reports_dir, "pages")
            os.makedirs(pages_dir, exist_ok=True)
            for page in audit.pages:
                try:
                    # Crear nombre de archivo seguro
                    filename = (
                        page.url.replace("https://", "")
                        .replace("http://", "")
                        .replace("/", "_")
                        .replace("?", "_")
                        .replace("&", "_")
                    )
                    if not filename:
                        filename = "index"
                    page_path = os.path.join(pages_dir, f"report_{filename}.json")

                    page_data = (
                        json.loads(page.audit_data)
                        if isinstance(page.audit_data, str)
                        else page.audit_data
                    )
                    with open(page_path, "w", encoding="utf-8") as f:
                        json.dump(page_data, f, indent=2, ensure_ascii=False)
                except Exception as e:
                    logger.warning(f"No se pudo guardar página {page.url}: {e}")

        # Guardar competidores
        if hasattr(audit, "competitor_audits") and audit.competitor_audits:
            competitors_dir = os.path.join(reports_dir, "competitors")
            os.makedirs(competitors_dir, exist_ok=True)
            try:
                comp_list = (
                    json.loads(audit.competitor_audits)
                    if isinstance(audit.competitor_audits, str)
                    else audit.competitor_audits
                )
                if isinstance(comp_list, list):
                    for i, comp_data in enumerate(comp_list):
                        try:
                            domain = (
                                comp_data.get("domain")
                                or comp_data.get("url", "")
                                .replace("https://", "")
                                .replace("http://", "")
                                .split("/")[0]
                                or f"competitor_{i}"
                            )
                            comp_path = os.path.join(
                                competitors_dir, f"competitor_{domain}.json"
                            )
                            with open(comp_path, "w", encoding="utf-8") as f:
                                json.dump(comp_data, f, indent=2, ensure_ascii=False)
                        except Exception as e:
                            logger.warning(f"No se pudo guardar competidor {i}: {e}")
            except Exception as e:
                logger.warning(f"Error procesando competitor_audits: {e}")

        # Llamar a create_comprehensive_pdf (igual que ag2_pipeline.py)
        try:
            create_comprehensive_pdf(reports_dir)

            # Buscar el PDF generado
            import glob

            pdf_files = glob.glob(
                os.path.join(reports_dir, "Reporte_Consolidado_*.pdf")
            )
            if pdf_files:
                pdf_file_path = pdf_files[0]
                logger.info(f"Reporte PDF guardado en: {pdf_file_path}")
                return pdf_file_path
            else:
                logger.error(f"No se encontró el PDF generado en {reports_dir}")
                raise FileNotFoundError("PDF file not generated")
        except Exception as e:
            logger.error(
                f"Error generando PDF con create_comprehensive_pdf: {e}", exc_info=True
            )
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
            if not isinstance(fetch_time, str):
                logger.warning(f"fetch_time is not a string: {type(fetch_time)}")
                return True

            if "Z" in fetch_time:
                fetch_datetime = datetime.fromisoformat(
                    fetch_time.replace("Z", "+00:00")
                )
            else:
                fetch_datetime = datetime.fromisoformat(fetch_time)

            # Make sure both datetimes are timezone-aware
            if fetch_datetime.tzinfo is None:
                fetch_datetime = fetch_datetime.replace(tzinfo=timezone.utc)

            now = datetime.now(timezone.utc)
            age = now - fetch_datetime
            is_stale = age > timedelta(hours=max_age_hours)

            logger.info(
                f"PageSpeed data age: {age.total_seconds() / 3600:.1f} hours, stale: {is_stale}"
            )
            return is_stale
        except Exception as e:
            logger.warning(f"Error checking PageSpeed staleness: {e}")
            return True

    @staticmethod
    async def generate_pdf_with_complete_context(
        db, audit_id: int, force_pagespeed_refresh: bool = False
    ) -> str:
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

        logger.info(
            f"=== Starting PDF generation with complete context for audit {audit_id} ==="
        )

        # 1. Load audit
        audit = AuditService.get_audit(db, audit_id)
        if not audit:
            raise ValueError(f"Audit {audit_id} not found")

        # 2. Check if PageSpeed data exists and is recent
        pagespeed_data = audit.pagespeed_data
        needs_refresh = (
            force_pagespeed_refresh
            or not pagespeed_data
            or PDFService._is_pagespeed_stale(pagespeed_data)
        )

        # 3. Run PageSpeed if needed
        if needs_refresh:
            logger.info(
                f"Running PageSpeed analysis for audit {audit_id} before PDF generation"
            )
            try:
                pagespeed_data = await PageSpeedService.analyze_both_strategies(
                    url=str(audit.url), api_key=settings.GOOGLE_PAGESPEED_API_KEY
                )

                # Store in database
                AuditService.set_pagespeed_data(db, audit_id, pagespeed_data)
                logger.info(f"✓ PageSpeed data collected and stored")
            except Exception as e:
                logger.error(f"PageSpeed collection failed: {e}")
                # Fallback to existing (stale) data if available
                # Fallback to existing (stale) data if available
                try:
                    db.refresh(audit)
                    if audit.pagespeed_data:
                        logger.warning(
                            "Falling back to existing (stale) PageSpeed data"
                        )
                        pagespeed_data = audit.pagespeed_data
                    else:
                        pagespeed_data = None
                except Exception:
                    pagespeed_data = (
                        audit.pagespeed_data if audit.pagespeed_data else None
                    )
        else:
            logger.info(f"✓ Using cached PageSpeed data (fresh)")

        # 4. Generate GEO Tools (Keywords, Backlinks, Rankings) REAL
        logger.info(f"Generating GEO Tools (Keywords, Backlinks, Rankings) for PDF...")

        # Initialize with defaults types
        keywords_data = {}
        backlinks_data = {}
        rank_tracking_data = {}
        llm_visibility_data = []
        ai_content_suggestions_list = []

        # Import services here to avoid circular imports if any
        try:
            from .keyword_service import KeywordService
            from .backlink_service import BacklinkService
            from .rank_tracker_service import RankTrackerService
            from .llm_visibility_service import LLMVisibilityService
            from .ai_content_service import AIContentService
            from urllib.parse import urlparse

            audit_url = str(audit.url)
            domain = urlparse(audit_url).netloc.replace("www.", "")
            keywords_data_list = []

            # 1. Keywords - Always run fresh research for PDF
            try:
                keyword_svc = KeywordService(db)
                logger.info(f"  - Performing fresh keyword research for PDF...")
                keywords_objs = await keyword_svc.research_keywords(audit_id, domain)

                keywords_data_list = [
                    {
                        "keyword": k.term,
                        "search_volume": k.volume,
                        "difficulty": k.difficulty,
                        "cpc": k.cpc,
                        "intent": k.intent,
                        "opportunity_score": getattr(k, "opportunity_score", 50),
                    }
                    for k in keywords_objs
                ]

                keywords_data = {
                    "items": keywords_data_list,
                    "total": len(keywords_data_list),
                    "total_keywords": len(keywords_data_list),
                    "top_opportunities": sorted(
                        keywords_data_list,
                        key=lambda x: x.get("opportunity_score", 0),
                        reverse=True,
                    )[:10],
                }
            except Exception as e:
                logger.error(f"Error generating Keywords for PDF: {e}")

            # Fallback to DB if empty
            if not keywords_data or not keywords_data.get("items"):
                try:
                    db.refresh(audit)
                    if audit.keywords:
                        logger.info(f"Using existing Keywords from DB as fallback (found {len(audit.keywords)})")
                        keywords_objs = audit.keywords
                        keywords_data_list = [
                            {
                                "keyword": k.term,
                                "search_volume": k.volume,
                                "difficulty": int(k.difficulty) if k.difficulty else 0, # Ensure int
                                "cpc": k.cpc,
                                "intent": k.intent,
                                "opportunity_score": getattr(k, 'opportunity_score', 50)
                            } for k in keywords_objs
                        ]
                        keywords_data = {
                            "items": keywords_data_list,
                            "total": len(keywords_data_list),
                            "total_keywords": len(keywords_data_list),
                            "top_opportunities": sorted(
                                keywords_data_list,
                                key=lambda x: x.get("opportunity_score", 0),
                                reverse=True,
                            )[:10],
                        }
                except Exception as fb_err:
                    logger.error(f"Fallback for Keywords failed: {fb_err}")

            # 2. Backlinks - Always run fresh analysis for PDF
            try:
                backlink_svc = BacklinkService(db)
                logger.info(f"  - Performing fresh backlinks analysis for PDF...")
                backlinks_objs = await backlink_svc.analyze_backlinks(audit_id, domain)

                backlinks_list = [
                    {
                        "source_url": b.source_url,
                        "target_url": b.target_url,
                        "anchor_text": b.anchor_text,
                        "domain_authority": b.domain_authority or 0,
                        "is_dofollow": b.is_dofollow,
                    }
                    for b in backlinks_objs
                ]

                backlinks_data = {
                    "items": backlinks_list[:20],
                    "total": len(backlinks_list),
                    "total_backlinks": len(backlinks_list),
                    "referring_domains": len(
                        set(
                            urlparse(b["source_url"]).netloc
                            for b in backlinks_list
                            if "://" in b["source_url"]
                        )
                    ),
                    "top_backlinks": backlinks_list[:20],
                    "summary": {
                        "average_domain_authority": round(
                            sum(b["domain_authority"] for b in backlinks_list)
                            / len(backlinks_list),
                            1,
                        )
                        if backlinks_list
                        else 0,
                        "dofollow_count": len(
                            [b for b in backlinks_list if b["is_dofollow"]]
                        ),
                        "nofollow_count": len(
                            [b for b in backlinks_list if not b["is_dofollow"]]
                        ),
                    },
                }
            except Exception as e:
                logger.error(f"Error generating Backlinks for PDF: {e}")

            # Fallback to DB if empty
            if not backlinks_data or not backlinks_data.get("items"):
                try:
                    # db.refresh(audit) # Already refreshed above if keywords failed, but safe to do again?
                    # Optimization: check if we need refresh? doing it again handles case where only backlinks failed.
                    db.refresh(audit)
                    if audit.backlinks:
                        logger.info(
                            f"Using existing Backlinks from DB as fallback (found {len(audit.backlinks)})"
                        )
                        backlinks_objs = audit.backlinks
                        backlinks_list = [
                            {
                                "source_url": b.source_url,
                                "target_url": b.target_url,
                                "anchor_text": b.anchor_text,
                                "domain_authority": b.domain_authority or 0,
                                "is_dofollow": b.is_dofollow,
                            }
                            for b in backlinks_objs
                        ]

                        backlinks_data = {
                            "items": backlinks_list[:20],
                            "total": len(backlinks_list),
                            "total_backlinks": len(backlinks_list),
                            "referring_domains": len(
                                set(
                                    urlparse(b["source_url"]).netloc
                                    for b in backlinks_list
                                    if "://" in b["source_url"]
                                )
                            ),
                            "top_backlinks": backlinks_list[:20],
                            "summary": {
                                "average_domain_authority": round(
                                    sum(b["domain_authority"] for b in backlinks_list)
                                    / len(backlinks_list),
                                    1,
                                )
                                if backlinks_list
                                else 0,
                                "dofollow_count": len(
                                    [b for b in backlinks_list if b["is_dofollow"]]
                                ),
                                "nofollow_count": len(
                                    [b for b in backlinks_list if not b["is_dofollow"]]
                                ),
                            },
                        }
                except Exception as fb_err:
                    logger.error(f"Fallback for Backlinks failed: {fb_err}")

            # 3. Rankings - Always run fresh tracking for PDF
            try:
                rank_svc = RankTrackerService(db)
                logger.info(f"  - Performing fresh rankings tracking for PDF...")
                # Ensure we use keywords_objs if available, otherwise empty
                kw_terms = (
                    [k.term for k in keywords_data_list[:10]]
                    if keywords_data_list
                    else []
                )

                if kw_terms:
                    rankings_objs = await rank_svc.track_rankings(
                        audit_id, domain, kw_terms
                    )
                else:
                    rankings_objs = []

                rankings_list = [
                    {
                        "keyword": r.keyword,
                        "position": r.position,
                        "url": r.url,
                        "change": 0,
                    }
                    for r in rankings_objs
                ]

                rank_tracking_data = {
                    "items": rankings_list,
                    "total": len(rankings_list),
                    "total_keywords": len(rankings_list),
                    "rankings": rankings_list,
                    "distribution": {
                        "top_3": len(
                            [
                                r
                                for r in rankings_list
                                if r.get("position", 100) <= 3
                                and r.get("position", 0) > 0
                            ]
                        ),
                        "top_10": len(
                            [
                                r
                                for r in rankings_list
                                if r.get("position", 100) <= 10
                                and r.get("position", 0) > 0
                            ]
                        ),
                        "top_20": len(
                            [
                                r
                                for r in rankings_list
                                if r.get("position", 100) <= 20
                                and r.get("position", 0) > 0
                            ]
                        ),
                        "beyond_20": len(
                            [
                                r
                                for r in rankings_list
                                if r.get("position", 100) > 20
                                or r.get("position", 0) == 0
                            ]
                        ),
                    },
                }
            except Exception as e:
                logger.error(f"Error generating Rankings for PDF: {e}")

            # Fallback to DB if empty
            if not rank_tracking_data or not rank_tracking_data.get("items"):
                # Check audit.rank_trackings (note the relationship name might be singular or plural, check model)
                # Based on test file it is 'rank_trackings'
                try:
                    db.refresh(audit)
                    if getattr(audit, "rank_trackings", None):
                        logger.info(
                            f"Using existing Rankings from DB as fallback (found {len(audit.rank_trackings)})"
                        )
                        rankings_objs = audit.rank_trackings
                        rankings_list = [
                            {
                                "keyword": r.keyword,
                                "position": r.position,
                                "url": r.url,
                                "change": 0,
                            }
                            for r in rankings_objs
                        ]

                        rank_tracking_data = {
                            "rankings": rankings_list,
                            "total_keywords": len(rankings_list),
                            "distribution": {
                                "top_3": len(
                                    [
                                        r
                                        for r in rankings_list
                                        if r.get("position", 100) <= 3
                                        and r.get("position", 0) > 0
                                    ]
                                ),
                                "top_10": len(
                                    [
                                        r
                                        for r in rankings_list
                                        if r.get("position", 100) <= 10
                                        and r.get("position", 0) > 0
                                    ]
                                ),
                                "top_20": len(
                                    [
                                        r
                                        for r in rankings_list
                                        if r.get("position", 100) <= 20
                                        and r.get("position", 0) > 0
                                    ]
                                ),
                                "beyond_20": len(
                                    [
                                        r
                                        for r in rankings_list
                                        if r.get("position", 100) > 20
                                        or r.get("position", 0) == 0
                                    ]
                                ),
                            },
                        }
                except Exception as fb_err:
                    logger.error(f"Fallback for Rankings failed: {fb_err}")

            # 4. LLM Visibility
            try:
                if keywords_data_list:  # Reuse list from step 1
                    llm_visibility_data = (
                        await LLMVisibilityService.generate_llm_visibility(
                            keywords_data_list, audit_url
                        )
                    )
                else:
                    llm_visibility_data = []
            except Exception as e:
                logger.error(f"Error generating LLM Visibility for PDF: {e}")
                # Fallback to DB
                try:
                    db.refresh(audit)
                    if audit.llm_visibilities:
                        llm_visibility_data = [
                            {
                                "query": l.query,
                                "llm_name": l.llm_name,
                                "is_visible": l.is_visible,
                                "rank": l.rank,
                                "citation_text": l.citation_text,
                            }
                            for l in audit.llm_visibilities
                        ]
                except:
                    pass

            # 5. AI Content Suggestions
            try:
                if keywords_data_list:  # Reuse list from step 1
                    ai_content_suggestions_list = (
                        AIContentService.generate_content_suggestions(
                            keywords=keywords_data_list, url=audit_url
                        )
                    )
                else:
                    ai_content_suggestions_list = []
            except Exception as e:
                logger.error(f"Error generating AI Content Suggestions for PDF: {e}")
                # Fallback to DB
                try:
                    db.refresh(audit)
                    if audit.ai_content_suggestions:
                        ai_content_suggestions_list = [
                            {
                                "topic": a.topic,
                                "suggestion_type": a.suggestion_type,
                                "content_outline": a.content_outline,
                                "priority": a.priority,
                                "page_url": a.page_url,
                            }
                            for a in audit.ai_content_suggestions
                        ]
                except:
                    pass

            logger.info(
                f"✓ GEO Tools data collected: {len(keywords_data.get('keywords', []))} keywords, {len(backlinks_data.get('top_backlinks', []))} backlinks, {len(rank_tracking_data.get('rankings', []))} rankings"
            )

        except Exception as tool_error:
            logger.error(
                f"Critical error initializing GEO tools services: {tool_error}",
                exc_info=True,
            )
            # Fallback is handled by initialization values

        # 5. Load COMPLETE context from ALL features (LLM visibility, AI content, etc.)
        complete_context = PDFService._load_complete_audit_context(db, audit_id)
        logger.info(
            f"✓ Complete context loaded with {len(complete_context)} feature types"
        )

        # 6. Regenerate markdown report with complete context
        logger.info(f"Regenerating markdown report with complete context...")
        try:
            llm_function = get_llm_function()

            # Use fresh generated data (keywords_data, backlinks_data, etc.)
            # rather than complete_context which may have stale or incorrectly formatted data
            # Also properly handle the case where llm_visibility_data is a list vs dict
            llm_viz_for_report = (
                llm_visibility_data if isinstance(llm_visibility_data, list) else []
            )
            ai_suggestions_for_report = (
                ai_content_suggestions_list
                if isinstance(ai_content_suggestions_list, list)
                else []
            )

            # Product Intelligence (ecommerce) - for LLM product positioning
            product_intelligence_data = {}
            try:
                from dataclasses import asdict
                from .product_intelligence_service import ProductIntelligenceService

                # Build pages_data from audited pages
                pages = AuditService.get_audited_pages(db, audit_id)
                pages_data = []
                for page in pages:
                    try:
                        page_data = (
                            json.loads(page.audit_data)
                            if isinstance(page.audit_data, str)
                            else page.audit_data or {}
                        )
                        schema_info = (
                            page_data.get("schema", {})
                            if isinstance(page_data, dict)
                            else {}
                        )
                        schemas = []

                        raw_jsonld_blocks = schema_info.get("raw_jsonld", [])
                        if isinstance(raw_jsonld_blocks, list):
                            for raw in raw_jsonld_blocks:
                                try:
                                    parsed = (
                                        json.loads(raw) if isinstance(raw, str) else raw
                                    )
                                    if isinstance(parsed, list):
                                        for item in parsed:
                                            if isinstance(item, dict):
                                                schemas.append(
                                                    {
                                                        "type": item.get("@type")
                                                        or item.get("type"),
                                                        "properties": item,
                                                    }
                                                )
                                    elif isinstance(parsed, dict):
                                        schemas.append(
                                            {
                                                "type": parsed.get("@type")
                                                or parsed.get("type"),
                                                "properties": parsed,
                                            }
                                        )
                                except Exception:
                                    continue

                        if not schemas:
                            schema_types = schema_info.get("schema_types", [])
                            if isinstance(schema_types, list):
                                for t in schema_types:
                                    schemas.append({"type": t, "properties": {}})

                        title = ""
                        if isinstance(page_data, dict):
                            title = page_data.get("content", {}).get(
                                "title"
                            ) or page_data.get("title", "")

                        pages_data.append(
                            {"url": page.url, "title": title, "schemas": schemas}
                        )
                    except Exception:
                        pages_data.append({"url": page.url, "title": "", "schemas": []})

                product_service = ProductIntelligenceService(llm_function=llm_function)
                product_result = await product_service.analyze(
                    audit_data=audit.target_audit or {},
                    pages_data=pages_data,
                    llm_visibility_data=llm_viz_for_report,
                    competitor_data=audit.competitor_audits or None,
                )
                product_intelligence_data = asdict(product_result)
                logger.info(
                    f"✓ Product intelligence loaded (ecommerce={product_intelligence_data.get('is_ecommerce')})"
                )
            except Exception as e:
                logger.warning(f"Product intelligence generation failed: {e}")

            logger.info(f"  Using fresh data for report generation:")
            logger.info(
                f"    - Keywords: {len(keywords_data.get('keywords', [])) if isinstance(keywords_data, dict) else 0}"
            )
            logger.info(
                f"    - Backlinks: {len(backlinks_data.get('top_backlinks', [])) if isinstance(backlinks_data, dict) else 0}"
            )
            logger.info(
                f"    - Rankings: {len(rank_tracking_data.get('rankings', [])) if isinstance(rank_tracking_data, dict) else 0}"
            )
            logger.info(f"    - LLM Visibility: {len(llm_viz_for_report)}")
            logger.info(
                f"    - AI Content Suggestions: {len(ai_suggestions_for_report)}"
            )

            # Regenerate report with complete context (using FRESH data from GEO tools)
            markdown_report, fix_plan = await PipelineService.generate_report(
                target_audit=audit.target_audit or {},
                external_intelligence=audit.external_intelligence or {},
                search_results=audit.search_results or {},
                competitor_audits=audit.competitor_audits or [],
                pagespeed_data=pagespeed_data,
                keywords_data=keywords_data,  # Fresh data from KeywordService
                backlinks_data=backlinks_data,  # Fresh data from BacklinkService
                product_intelligence_data=product_intelligence_data,
                rank_tracking_data=rank_tracking_data,  # Fresh data from RankTrackerService
                llm_visibility_data=llm_viz_for_report,  # Fresh data from LLMVisibilityService
                ai_content_suggestions=ai_suggestions_for_report,  # Fresh data from AIContentService
                llm_function=llm_function,
            )

            # Update audit with new report (hard fail if regeneration failed)
            if not markdown_report or len(markdown_report.strip()) <= 100:
                raise RuntimeError(
                    f"Report regeneration failed: content too short ({len(markdown_report or '')} chars)"
                )

            audit.report_markdown = markdown_report
            logger.info(
                f"✓ Markdown report regenerated with complete context ({len(markdown_report)} chars)"
            )

            # Ensure fix_plan is generated - NO FALLBACK for production
            if not fix_plan or len(fix_plan) == 0:
                logger.warning(
                    "Fix plan is empty. No fallback used as per production requirements."
                )
                fix_plan = []

            audit.fix_plan = fix_plan
            db.commit()

            logger.info(f"Fix plan length: {len(fix_plan) if fix_plan else 0}")
        except Exception as e:
            logger.error(
                f"Could not regenerate markdown report; aborting PDF generation: {e}",
                exc_info=True,
            )
            raise

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
            pagespeed_data=pagespeed_data,
            keywords_data=keywords_data,
            backlinks_data=backlinks_data,
            rank_tracking_data=rank_tracking_data,
            llm_visibility_data=llm_visibility_data,
        )

        logger.info(f"=== PDF generation completed: {pdf_path} ===")
        return pdf_path

    @staticmethod
    async def generate_comprehensive_pdf(
        audit: Audit,
        pages: list,
        competitors: list,
        pagespeed_data: dict = None,
        keywords_data: dict = None,
        backlinks_data: dict = None,
        rank_tracking_data: dict = None,
        llm_visibility_data: list = None,
    ) -> str:
        """
        Genera un PDF completo con todos los datos de la auditoría:
        - Datos de auditoría principal
        - Páginas auditadas
        - Competidores
        - PageSpeed data
        - Keywords
        - Backlinks
        - Rank tracking
        - LLM Visibility

        Args:
            audit: La instancia del modelo Audit
            pages: Lista de páginas auditadas
            competitors: Lista de competidores
            pagespeed_data: Datos de PageSpeed (opcional)
            keywords_data: Datos de Keywords (opcional)
            backlinks_data: Datos de Backlinks (opcional)
            rank_tracking_data: Datos de Rank Tracking (opcional)
            llm_visibility_data: Datos de LLM Visibility (opcional)

        Returns:
            La ruta completa al archivo PDF generado
        """
        if not PDF_GENERATOR_AVAILABLE:
            logger.error(
                "PDF generator no está disponible. Instalar fpdf2: pip install fpdf2"
            )
            raise ImportError("PDF generator not available")

        logger.info(
            f"Generando PDF completo para auditoría {audit.id} con todos los datos"
        )

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
                fix_plan_data = (
                    json.loads(audit.fix_plan)
                    if isinstance(audit.fix_plan, str)
                    else audit.fix_plan
                )
                with open(fix_plan_path, "w", encoding="utf-8") as f:
                    json.dump(fix_plan_data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.warning(f"No se pudo guardar fix_plan.json: {e}")

        # 3. Guardar aggregated_summary.json (target audit)
        if audit.target_audit:
            agg_summary_path = os.path.join(reports_dir, "aggregated_summary.json")
            try:
                target_audit_data = (
                    json.loads(audit.target_audit)
                    if isinstance(audit.target_audit, str)
                    else audit.target_audit
                )
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

        # 4.1 Guardar Keywords data
        if keywords_data:
            keywords_path = os.path.join(reports_dir, "keywords.json")
            try:
                # keywords_data can be a dict or a list
                data_to_save = (
                    keywords_data.get("keywords", keywords_data)
                    if isinstance(keywords_data, dict)
                    else keywords_data
                )
                with open(keywords_path, "w", encoding="utf-8") as f:
                    json.dump(data_to_save, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.warning(f"No se pudo guardar keywords.json: {e}")

        # 4.2 Guardar Backlinks data
        if backlinks_data:
            backlinks_path = os.path.join(reports_dir, "backlinks.json")
            try:
                # backlinks_data can be a dict or a list
                data_to_save = (
                    backlinks_data.get("top_backlinks", backlinks_data)
                    if isinstance(backlinks_data, dict)
                    else backlinks_data
                )
                with open(backlinks_path, "w", encoding="utf-8") as f:
                    json.dump(data_to_save, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.warning(f"No se pudo guardar backlinks.json: {e}")

        # 4.3 Guardar Rankings data
        if rank_tracking_data:
            rankings_path = os.path.join(reports_dir, "rankings.json")
            try:
                # rank_tracking_data can be a dict or a list
                data_to_save = (
                    rank_tracking_data.get("rankings", rank_tracking_data)
                    if isinstance(rank_tracking_data, dict)
                    else rank_tracking_data
                )
                with open(rankings_path, "w", encoding="utf-8") as f:
                    json.dump(data_to_save, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.warning(f"No se pudo guardar rankings.json: {e}")

        # 4.4 Guardar LLM Visibility data
        if llm_visibility_data:
            visibility_path = os.path.join(reports_dir, "llm_visibility.json")
            try:
                with open(visibility_path, "w", encoding="utf-8") as f:
                    json.dump(llm_visibility_data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.warning(f"No se pudo guardar llm_visibility.json: {e}")

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
                        "audit_data": page.audit_data,
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
                    comp_data = (
                        comp
                        if isinstance(comp, dict)
                        else {
                            "url": getattr(comp, "url", ""),
                            "geo_score": getattr(comp, "geo_score", 0),
                            "audit_data": getattr(comp, "audit_data", {}),
                        }
                    )
                    # Extract domain from URL if not present
                    if "domain" not in comp_data:
                        from urllib.parse import urlparse

                        url = comp_data.get("url", "")
                        if url:
                            domain = urlparse(url).netloc.replace("www.", "")
                        else:
                            domain = f"competitor_{idx + 1}"
                        comp_data["domain"] = domain
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

            pdf_files = glob.glob(
                os.path.join(reports_dir, "Reporte_Consolidado_*.pdf")
            )
            if pdf_files:
                pdf_file_path = pdf_files[0]
                logger.info(f"PDF completo generado en: {pdf_file_path}")
                return pdf_file_path
            else:
                logger.error(f"No se encontró el PDF generado en {reports_dir}")
                raise FileNotFoundError("PDF file not generated")
        except Exception as e:
            logger.error(
                f"Error generando PDF con create_comprehensive_pdf: {e}", exc_info=True
            )
            raise
