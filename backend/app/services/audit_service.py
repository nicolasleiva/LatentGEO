"""
Servicio de Auditoría - Lógica principal
"""
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
import json
import os

from ..models import Audit, AuditedPage, Report, Competitor, AuditStatus, CrawlJob
from ..schemas import AuditCreate, AuditSummary, AuditDetail
from ..core.config import settings
from ..core.logger import get_logger

# Importar servicios adicionales
from .crawler_service import CrawlerService
from .audit_local_service import AuditLocalService
from .pipeline_service import PipelineService

logger = get_logger(__name__)


class AuditService:
    """Servicio para gestionar auditorías"""

    @staticmethod
    def create_audit(db: Session, audit_create: AuditCreate) -> Audit:
        """Crear nueva auditoría con prevención de duplicados (Level 3)"""
        url = str(audit_create.url)
        
        # Level 3: Idempotency - Check for active audits for this URL
        active_audit = db.query(Audit).filter(
            Audit.url == url,
            Audit.status.in_([AuditStatus.PENDING, AuditStatus.RUNNING])
        ).first()
        
        if active_audit:
            logger.info(f"Audit already active for {url}: {active_audit.id}")
            return active_audit

        domain = (
            url.replace("https://", "")
            .replace("http://", "")
            .split("/")[0]
            .lstrip("www.")
        )

        audit = Audit(
            url=url,
            domain=domain,
            status=AuditStatus.PENDING,
            language="en",
            competitors=audit_create.competitors,
            market=audit_create.market,
            source=audit_create.source,
            user_id=audit_create.user_id,
            user_email=audit_create.user_email
        )
        db.add(audit)
        db.flush()
        db.commit()
        db.refresh(audit)

        # Level 2: Invalidate list cache for this user
        if audit.user_email:
            from .cache_service import cache
            cache.delete(f"audits_list_{audit.user_email}")

        logger.info(f"Auditoría creada: {audit.id} para {url}, user: {audit_create.user_email}")
        return audit

    @staticmethod
    def get_audit(db: Session, audit_id: int) -> Optional[Audit]:
        """Obtener auditoría por ID con caching (Level 2)"""
        # Level 2 Caching: Use CacheService for frequent reads
        from .cache_service import cache
        cache_key = f"audit_detail_{audit_id}"
        
        # We can't easily cache SQLAlchemy models, so we only cache if COMPLETED/FAILED
        audit = db.query(Audit).filter(Audit.id == audit_id).first()
        
        if audit:
            # Check if we should enrich with PDF path
            pdf_report = db.query(Report).filter(
                Report.audit_id == audit_id,
                Report.report_type == "PDF"
            ).order_by(desc(Report.created_at)).first()
            audit.report_pdf_path = pdf_report.file_path if pdf_report else None
            
        return audit

    @staticmethod
    def get_audits(db: Session, skip: int = 0, limit: int = 20, user_email: str = None) -> List[Audit]:
        """Obtener lista de auditorías con paginación y filtro opcional por usuario"""
        query = db.query(Audit)
        
        # Filtrar por usuario si se proporciona
        if user_email:
            query = query.filter(Audit.user_email == user_email)
        
        audits = (
            query
            .order_by(desc(Audit.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )
        
        # Optimización: Cargar PDFs en una sola query
        if audits:
            audit_ids = [a.id for a in audits]
            pdf_reports = db.query(Report).filter(
                Report.audit_id.in_(audit_ids),
                Report.report_type == "PDF"
            ).order_by(desc(Report.created_at)).all()
            
            # Mapear PDFs a audits
            pdf_map = {}
            for pdf in pdf_reports:
                if pdf.audit_id not in pdf_map:
                    pdf_map[pdf.audit_id] = pdf.file_path
            
            for audit in audits:
                audit.report_pdf_path = pdf_map.get(audit.id)
        
        return audits

    @staticmethod
    def get_audits_count(db: Session) -> int:
        """Obtener total de auditorías"""
        return db.query(Audit).count()

    @staticmethod
    def get_audits_by_status(db: Session, status: AuditStatus) -> List[Audit]:
        """Obtener auditorías por estado"""
        return db.query(Audit).filter(Audit.status == status).all()

    @staticmethod
    def update_audit_progress(
        db: Session,
        audit_id: int,
        progress: float,
        status: Optional[AuditStatus] = None,
        error_message: Optional[str] = None,
    ):
        """Actualizar progreso de auditoría"""
        audit = db.query(Audit).filter(Audit.id == audit_id).first()
        if not audit:
            return None

        audit.progress = min(progress, 100.0)

        if status:
            audit.status = status
            if status == AuditStatus.RUNNING and not audit.started_at:
                audit.started_at = datetime.now(timezone.utc)
            elif status == AuditStatus.COMPLETED:
                audit.completed_at = datetime.now(timezone.utc)

        if error_message:
            audit.error_message = error_message

        db.commit()
        db.refresh(audit)
        
        # Level 2/3: Broadcast progress via Redis Pub/Sub
        try:
            from .cache_service import cache
            if cache.enabled:
                progress_msg = {
                    "audit_id": audit_id,
                    "progress": audit.progress,
                    "status": audit.status.value if audit.status else None,
                    "error_message": audit.error_message
                }
                cache.redis_client.publish(f"audit_progress_{audit_id}", json.dumps(progress_msg))
        except Exception as e:
            logger.error(f"Error publishing progress to Redis: {e}")

        return audit

    @staticmethod
    def set_audit_task_id(db: Session, audit_id: int, task_id: str):
        """Guardar el ID de la tarea de Celery en la auditoría"""
        audit = db.query(Audit).filter(Audit.id == audit_id).first()
        if not audit:
            return None
        audit.task_id = task_id
        db.commit()
        db.refresh(audit)
        return audit

    @staticmethod
    def _sanitize_json_value(value: Any, _stack: Optional[set] = None) -> Any:
        """Sanitize JSON payloads to avoid circular references and non-serializable objects."""
        if _stack is None:
            _stack = set()

        if value is None or isinstance(value, (str, int, float, bool)):
            return value

        if isinstance(value, datetime):
            return value.isoformat()

        obj_id = id(value)
        if obj_id in _stack:
            return "[Circular]"

        if isinstance(value, dict):
            _stack.add(obj_id)
            try:
                sanitized = {}
                for key, val in value.items():
                    safe_key = key if isinstance(key, (str, int, float, bool)) else str(key)
                    sanitized[str(safe_key)] = AuditService._sanitize_json_value(val, _stack)
                return sanitized
            finally:
                _stack.discard(obj_id)

        if isinstance(value, (list, tuple, set)):
            _stack.add(obj_id)
            try:
                return [AuditService._sanitize_json_value(item, _stack) for item in value]
            finally:
                _stack.discard(obj_id)

        for attr in ("model_dump", "dict"):
            if hasattr(value, attr) and callable(getattr(value, attr)):
                try:
                    return AuditService._sanitize_json_value(getattr(value, attr)(), _stack)
                except Exception:
                    pass

        return str(value)

    @staticmethod
    async def set_audit_results(
        db: Session,
        audit_id: int,
        target_audit: Dict[str, Any],
        external_intelligence: Dict[str, Any],
        search_results: Dict[str, Any],
        competitor_audits: List[Dict[str, Any]],
        report_markdown: str,
        fix_plan: List[Dict[str, Any]],
        pagespeed_data: Dict[str, Any] = None,
        keywords: List[Dict[str, Any]] = None,
        backlinks: List[Dict[str, Any]] = None,
        rankings: List[Dict[str, Any]] = None,
        llm_visibility: List[Dict[str, Any]] = None,
    ):
        """Guardar resultados de auditoría completa (Async version)"""
        audit = db.query(Audit).filter(Audit.id == audit_id).first()
        if not audit:
            return None

        # Normalizar target_audit por seguridad (acepta tuple/list o dict)
        if isinstance(target_audit, (tuple, list)):
            target_audit = target_audit[0] if target_audit else {}
        if not isinstance(target_audit, dict):
            target_audit = {}

        external_intelligence = external_intelligence or {}
        search_results = search_results or {}
        competitor_audits = competitor_audits or []
        fix_plan = fix_plan or []
        pagespeed_data = pagespeed_data or {}

        safe_target_audit = AuditService._sanitize_json_value(target_audit)
        safe_external_intelligence = AuditService._sanitize_json_value(external_intelligence)
        safe_search_results = AuditService._sanitize_json_value(search_results)
        safe_competitor_audits = AuditService._sanitize_json_value(competitor_audits)
        safe_fix_plan = AuditService._sanitize_json_value(fix_plan)
        safe_pagespeed_data = AuditService._sanitize_json_value(pagespeed_data)

        if not isinstance(safe_competitor_audits, list):
            safe_competitor_audits = []
        if not isinstance(safe_fix_plan, list):
            safe_fix_plan = []
        if not isinstance(safe_external_intelligence, dict):
            safe_external_intelligence = {}
        if not isinstance(safe_search_results, dict):
            safe_search_results = {}
        if not isinstance(safe_pagespeed_data, dict):
            safe_pagespeed_data = {}

        audit.target_audit = safe_target_audit
        audit.external_intelligence = safe_external_intelligence
        audit.search_results = safe_search_results
        audit.competitor_audits = safe_competitor_audits
        audit.report_markdown = report_markdown
        audit.fix_plan = safe_fix_plan
        audit.pagespeed_data = safe_pagespeed_data

        # Calcular y guardar GEO Score para el target audit
        try:
            # CompetitorService ya está definido en este archivo (línea 914)
            geo_score = CompetitorService._calculate_geo_score(target_audit)
            audit.geo_score = geo_score
            logger.info(f"GEO Score calculado para audit {audit_id}: {geo_score}")
        except Exception as e:
            logger.error(f"Error calculando GEO score: {e}")

        # Actualizar metadata
        audit.is_ymyl = external_intelligence.get("is_ymyl", False)
        category_value = external_intelligence.get("category")
        if not category_value or str(category_value).strip().lower() in {
            "",
            "unclassified",
            "unknown category",
            "none",
        }:
            try:
                from app.services.pipeline_service import PipelineService

                core_terms = PipelineService._extract_core_terms_from_target(
                    target_audit, max_terms=3, include_generic=False
                )
                if core_terms:
                    category_value = " ".join(core_terms).title()
            except Exception as e:
                logger.warning(f"No se pudo inferir categoría desde core terms: {e}")
        if not category_value:
            category_value = "Unclassified"
        if isinstance(category_value, dict):
            # Persist structured category as JSON string for String column compatibility
            try:
                category_value = json.dumps(category_value, ensure_ascii=False)
            except Exception:
                category_value = str(category_value)
        audit.category = category_value
        # target_audit ya es dict o {}
        audit.total_pages = target_audit.get("audited_pages_count", 0)

        # Persist inferred market when missing (avoid empty Market Context)
        try:
            market_value = external_intelligence.get("market") or target_audit.get("market")
            if not market_value:
                market_value = PipelineService._infer_market_from_url(audit.url)
            if market_value and not audit.market:
                audit.market = market_value
        except Exception as e:
            logger.warning(f"No se pudo inferir mercado para audit {audit_id}: {e}")

        # Contar issues reales desde las páginas auditadas (Más preciso para el dashboard)
        saved_pages = db.query(AuditedPage).filter(AuditedPage.audit_id == audit_id).all()
        
        if saved_pages:
            audit.total_pages = len(saved_pages)
            audit.critical_issues = sum(p.critical_issues for p in saved_pages)
            audit.high_issues = sum(p.high_issues for p in saved_pages)
            audit.medium_issues = sum(p.medium_issues for p in saved_pages)
            audit.low_issues = sum(p.low_issues for p in saved_pages)
            logger.info(f"Issues calculados desde {len(saved_pages)} páginas: C={audit.critical_issues}, H={audit.high_issues}")
        else:
            # Fallback a fix_plan si no hay páginas guardadas
            fix_plan_list = fix_plan if isinstance(fix_plan, list) else []
            audit.critical_issues = len(
                [f for f in fix_plan_list if f.get("priority") == "CRITICAL"]
            )
            audit.high_issues = len(
                [f for f in fix_plan_list if f.get("priority") == "HIGH"]
            )
            audit.medium_issues = len(
                [f for f in fix_plan_list if f.get("priority") == "MEDIUM"]
            )
            audit.low_issues = len([f for f in fix_plan_list if f.get("priority") == "LOW"])
        
        # Guardar competidores con GEO scores calculados
        for comp_data in safe_competitor_audits:
            if isinstance(comp_data, dict) and comp_data.get("url"):
                try:
                    # CompetitorService ya está definido en este archivo (línea 914)
                    CompetitorService.add_competitor(
                        db=db,
                        audit_id=audit_id,
                        url=comp_data.get("url"),
                        geo_score=0,  # Se calculará automáticamente
                        audit_data=comp_data
                    )
                except Exception as e:
                    logger.error(f"Error guardando competidor {comp_data.get('url')}: {e}")

        # Guardar JSONs como en ag2_pipeline.py
        await AuditService._save_audit_files(
            audit_id,
            safe_target_audit,
            safe_external_intelligence,
            safe_search_results,
            safe_competitor_audits,
            safe_fix_plan,
            safe_pagespeed_data,
            keywords,
            backlinks,
            rankings,
            llm_visibility
        )

        db.commit()
        db.refresh(audit)
        logger.info(f"Resultados guardados para auditoría {audit_id}")
        return audit

    @staticmethod
    async def _save_audit_files(
        audit_id: int,
        target_audit: Dict[str, Any],
        external_intelligence: Dict[str, Any],
        search_results: Dict[str, Any],
        competitor_audits: List[Dict[str, Any]],
        fix_plan: List[Dict[str, Any]],
        pagespeed_data: Dict[str, Any] = None,
        keywords: List[Dict[str, Any]] = None,
        backlinks: List[Dict[str, Any]] = None,
        rankings: List[Dict[str, Any]] = None,
        llm_visibility: List[Dict[str, Any]] = None,
    ):
        """Guardar archivos JSON de auditoría como en ag2_pipeline.py"""
        try:
            safe_target_audit = AuditService._sanitize_json_value(target_audit)
            safe_external_intelligence = AuditService._sanitize_json_value(external_intelligence or {})
            safe_search_results = AuditService._sanitize_json_value(search_results or {})
            safe_competitor_audits = AuditService._sanitize_json_value(competitor_audits or [])
            safe_fix_plan = AuditService._sanitize_json_value(fix_plan or [])
            safe_pagespeed_data = AuditService._sanitize_json_value(pagespeed_data or {})
            safe_keywords = AuditService._sanitize_json_value(keywords or [])
            safe_backlinks = AuditService._sanitize_json_value(backlinks or [])
            safe_rankings = AuditService._sanitize_json_value(rankings or [])
            safe_llm_visibility = AuditService._sanitize_json_value(llm_visibility or [])

            if not isinstance(safe_competitor_audits, list):
                safe_competitor_audits = []
            if not isinstance(safe_fix_plan, list):
                safe_fix_plan = []

            # Crear directorio de reportes
            reports_dir = os.path.join(settings.REPORTS_DIR or "reports", f"audit_{audit_id}")
            pages_dir = os.path.join(reports_dir, "pages")
            competitors_dir = os.path.join(reports_dir, "competitors")
            os.makedirs(reports_dir, exist_ok=True)
            os.makedirs(pages_dir, exist_ok=True)
            os.makedirs(competitors_dir, exist_ok=True)
            import re

            # Guardar resumen agregado
            aggregated_path = os.path.join(reports_dir, "aggregated_summary.json")
            with open(aggregated_path, 'w', encoding='utf-8') as f:
                json.dump(safe_target_audit, f, ensure_ascii=False, indent=2)

            # Guardar fix_plan
            fix_plan_path = os.path.join(reports_dir, "fix_plan.json")
            with open(fix_plan_path, 'w', encoding='utf-8') as f:
                json.dump(safe_fix_plan, f, ensure_ascii=False, indent=2)

            # Guardar PageSpeed
            if pagespeed_data:
                pagespeed_path = os.path.join(reports_dir, "pagespeed.json")
                with open(pagespeed_path, 'w', encoding='utf-8') as f:
                    json.dump(safe_pagespeed_data, f, ensure_ascii=False, indent=2)

            # Guardar Keywords
            if keywords:
                keywords_path = os.path.join(reports_dir, "keywords.json")
                with open(keywords_path, 'w', encoding='utf-8') as f:
                    json.dump(safe_keywords, f, ensure_ascii=False, indent=2)

            # Guardar Backlinks
            if backlinks:
                backlinks_path = os.path.join(reports_dir, "backlinks.json")
                with open(backlinks_path, 'w', encoding='utf-8') as f:
                    json.dump(safe_backlinks, f, ensure_ascii=False, indent=2)

            # Guardar Rankings
            if rankings:
                rankings_path = os.path.join(reports_dir, "rankings.json")
                with open(rankings_path, 'w', encoding='utf-8') as f:
                    json.dump(safe_rankings, f, ensure_ascii=False, indent=2)

            # Guardar LLM Visibility
            if llm_visibility:
                visibility_path = os.path.join(reports_dir, "llm_visibility.json")
                with open(visibility_path, 'w', encoding='utf-8') as f:
                    json.dump(safe_llm_visibility, f, ensure_ascii=False, indent=2)

            # Guardar competidores individuales
            for i, comp in enumerate(safe_competitor_audits):
                try:
                    domain = comp.get('domain') or f"competitor_{i}"
                    safe_domain = re.sub(r'[^\w\-_.]', '_', domain)
                    if not comp.get("geo_score"):
                        comp["geo_score"] = CompetitorService._calculate_geo_score(comp)
                    if "benchmark" not in comp:
                        comp["benchmark"] = CompetitorService._format_competitor_data(
                            comp, comp.get("geo_score", 0.0), comp.get("url")
                        )
                    comp_path = os.path.join(competitors_dir, f"competitor_{safe_domain}.json")
                    with open(comp_path, 'w', encoding='utf-8') as f:
                        json.dump(comp, f, ensure_ascii=False, indent=2)
                except:
                    pass
            
            # Guardar contexto final del LLM
            final_context = {
                "target_audit": safe_target_audit,
                "external_intelligence": safe_external_intelligence,
                "search_results": safe_search_results,
                "competitor_audits": safe_competitor_audits,
                "pagespeed": safe_pagespeed_data,
                "keywords": safe_keywords,
                "backlinks": safe_backlinks,
                "rank_tracking": safe_rankings,
                "llm_visibility": safe_llm_visibility
            }
            context_path = os.path.join(reports_dir, "final_llm_context.json")
            with open(context_path, 'w', encoding='utf-8') as f:
                json.dump(final_context, f, ensure_ascii=False, indent=2)

            # Guardar fix plan
            fix_plan_path = os.path.join(reports_dir, "fix_plan.json")
            with open(fix_plan_path, 'w', encoding='utf-8') as f:
                json.dump(fix_plan, f, ensure_ascii=False, indent=2)

            logger.info(f"Archivos JSON guardados en {reports_dir}")
        except Exception as e:
            logger.error(f"Error guardando archivos JSON para auditoría {audit_id}: {e}")

    @staticmethod
    def save_page_audit(
        db: Session,
        audit_id: int,
        page_url: str,
        audit_data: Dict[str, Any],
        page_index: int = 0
    ) -> AuditedPage:
        """Guardar auditoría de página individual como en ag2_pipeline.py"""
        try:
            safe_audit_data = AuditService._sanitize_json_value(audit_data or {})

            # Crear directorio de páginas
            reports_dir = os.path.join(settings.REPORTS_DIR or "reports", f"audit_{audit_id}")
            pages_dir = os.path.join(reports_dir, "pages")
            os.makedirs(pages_dir, exist_ok=True)

            # Generar nombre de archivo seguro
            import re
            safe_filename = re.sub(r"https?://", "", page_url).replace("/", "_").replace(":", "_")
            page_json_path = os.path.join(pages_dir, f"report_{page_index}_{safe_filename}.json")

            # Guardar JSON de la página
            with open(page_json_path, 'w', encoding='utf-8') as f:
                json.dump(safe_audit_data, f, ensure_ascii=False, indent=2)

            # Extraer path de la URL
            from urllib.parse import urlparse
            parsed_url = urlparse(page_url)
            path = parsed_url.path or "/"

            # Calcular score general
            overall_score = AuditService._calculate_overall_score(safe_audit_data)

            # Guardar en base de datos
            audited_page = AuditService.add_audited_page(
                db=db,
                audit_id=audit_id,
                url=page_url,
                path=path,
                audit_data=safe_audit_data,
                overall_score=overall_score
            )

            logger.info(f"Página auditada guardada: {page_url} -> {page_json_path}")
            return audited_page

        except Exception as e:
            logger.error(f"Error guardando auditoría de página {page_url}: {e}")
            raise

    @staticmethod
    def _calculate_overall_score(audit_data: Dict[str, Any]) -> float:
        """Calcular score general de la página basado en los datos de auditoría"""
        try:
            # Usar los extractores individuales para obtener scores de 0-100
            h1 = AuditService._extract_h1_score(audit_data)
            structure = AuditService._extract_structure_score(audit_data)
            content = AuditService._extract_content_score(audit_data)
            eeat = AuditService._extract_eeat_score(audit_data)
            schema = AuditService._extract_schema_score(audit_data)
            
            # Pesos para el promedio ponderado
            weights = {
                "h1": 0.15,
                "structure": 0.20,
                "content": 0.20,
                "eeat": 0.25,
                "schema": 0.20
            }
            
            overall = (
                h1 * weights["h1"] +
                structure * weights["structure"] +
                content * weights["content"] +
                eeat * weights["eeat"] +
                schema * weights["schema"]
            )
            
            return round(overall, 1)
        except Exception as e:
            logger.error(f"Error en _calculate_overall_score: {e}")
            return 50.0  # Score por defecto

    @staticmethod
    def add_audited_page(
        db: Session,
        audit_id: int,
        url: str,
        path: str,
        audit_data: Dict[str, Any],
        overall_score: float,
    ):
        """Añadir página auditada"""
        audit_data = AuditService._sanitize_json_value(audit_data or {})
        # Extraer scores individuales
        h1_score = AuditService._extract_h1_score(audit_data)
        structure_score = AuditService._extract_structure_score(audit_data)
        content_score = AuditService._extract_content_score(audit_data)
        eeat_score = AuditService._extract_eeat_score(audit_data)
        schema_score = AuditService._extract_schema_score(audit_data)
        
        # Contar issues por severidad
        critical, high, medium, low = AuditService._count_page_issues(audit_data)
        
        page = AuditedPage(
            audit_id=audit_id,
            url=url,
            path=path,
            audit_data=audit_data,
            overall_score=overall_score,
            h1_score=h1_score,
            structure_score=structure_score,
            content_score=content_score,
            eeat_score=eeat_score,
            schema_score=schema_score,
            critical_issues=critical,
            high_issues=high,
            medium_issues=medium,
            low_issues=low,
        )
        db.add(page)
        db.commit()
        db.refresh(page)
        return page
    
    @staticmethod
    def _extract_h1_score(audit_data: Dict[str, Any]) -> float:
        try:
            h1_check = audit_data.get("structure", {}).get("h1_check", {})
            return 100.0 if h1_check.get("status") == "pass" else 0.0
        except:
            return 0.0
    
    @staticmethod
    def _extract_structure_score(audit_data: Dict[str, Any]) -> float:
        try:
            return audit_data.get("structure", {}).get("semantic_html", {}).get("score_percent", 0)
        except:
            return 0.0
    
    @staticmethod
    def _extract_content_score(audit_data: Dict[str, Any]) -> float:
        try:
            tone = audit_data.get("content", {}).get("conversational_tone", {}).get("score", 0)
            return tone * 10  # Normalizar a 100
        except:
            return 0.0
    
    @staticmethod
    def _extract_eeat_score(audit_data: Dict[str, Any]) -> float:
        try:
            eeat = audit_data.get("eeat", {})
            scores = []
            
            # 1. Autor (40%)
            if eeat.get("author_presence", {}).get("status") == "pass":
                scores.append(100)
            else:
                scores.append(0)
            
            # 2. Citaciones/Fuentes (30%)
            citations = eeat.get("citations_and_sources", {})
            if citations.get("authoritative_links", 0) > 0:
                scores.append(100)
            elif citations.get("external_links", 0) > 0:
                scores.append(60)
            else:
                scores.append(20)
                
            # 3. Transparencia (30%)
            transp = eeat.get("transparency_signals", {})
            transp_score = sum(1 for v in transp.values() if v) / max(1, len(transp)) * 100
            scores.append(transp_score)
            
            weights = [0.4, 0.3, 0.3]
            weighted_score = sum(s * w for s, w in zip(scores, weights))
            
            return round(weighted_score, 1)
        except:
            return 0.0
    
    @staticmethod
    def _extract_schema_score(audit_data: Dict[str, Any]) -> float:
        try:
            schema_data = audit_data.get("schema", {})
            schema_presence = schema_data.get("schema_presence", {})
            if schema_presence.get("status") == "present":
                # Usar schema_types que es lo que devuelve AuditLocalService
                types = schema_data.get("schema_types", [])
                if not types:
                    # Fallback si por alguna razón no está en schema_types pero hay bloques
                    types = schema_data.get("types", [])
                
                types_count = len(types)
                return min(100, max(20, types_count * 20))  # Mínimo 20 si está presente
            return 0.0
        except:
            return 0.0
    
    @staticmethod
    def _count_page_issues(audit_data: Dict[str, Any]) -> tuple:
        critical = high = medium = low = 0
        try:
            # 1. Structure & SEO Basics
            struct = audit_data.get("structure", {})
            # H1 missing or multiple is CRITICAL
            h1_status = struct.get("h1_check", {}).get("status")
            if h1_status in ["missing", "fail"]:
                critical += 1
            elif h1_status in ["multiple", "warn"]:
                high += 1
            
            # Title missing/empty is CRITICAL, too long/short is MEDIUM
            title_status = struct.get("title_check", {}).get("status")
            if title_status == "missing" or title_status == "empty":
                critical += 1
            elif title_status in ["too_long", "too_short"]:
                medium += 1

            # Meta Desc missing is HIGH
            meta_status = struct.get("meta_desc_check", {}).get("status")
            if meta_status == "missing" or meta_status == "empty":
                high += 1
            elif meta_status in ["too_long", "too_short"]:
                low += 1

            # 2. Schema (GEO Critical)
            # Missing schema is CRITICAL for GEO
            schema_status = audit_data.get("schema", {}).get("schema_presence", {}).get("status")
            if schema_status != "present":
                critical += 1
            
            # 3. EEAT (High Impact)
            # Author missing is HIGH
            eeat = audit_data.get("eeat", {})
            if eeat.get("author_presence", {}).get("status") != "pass":
                high += 1
            
            # 4. Content Quality
            content = audit_data.get("content", {})
            if content.get("conversational_tone", {}).get("score", 10) < 5:
                medium += 1
            
            # 5. Images
            img_status = struct.get("image_alt_check", {}).get("status")
            if img_status == "missing_alts":
                medium += 1

            # 6. PageSpeed (si está disponible en datos de auditoría local simulados)
            # Por ahora no se incluye aquí porque viene por separado, pero si existiera:
            pass

        except Exception as e:
            logger.error(f"Error contando issues de página: {e}")
        
        return critical, high, medium, low

    @staticmethod
    def get_audited_pages(db: Session, audit_id: int) -> List[AuditedPage]:
        """Obtener páginas auditadas"""
        return db.query(AuditedPage).filter(AuditedPage.audit_id == audit_id).all()

    @staticmethod
    def delete_audit(db: Session, audit_id: int) -> bool:
        """Eliminar una auditoría y sus datos asociados"""
        audit = db.query(Audit).filter(Audit.id == audit_id).first()
        if not audit:
            return False
        db.delete(audit)
        db.commit()
        logger.info(f"Auditoría {audit_id} eliminada")
        return True

    @staticmethod
    def get_stats_summary(db: Session) -> Dict[str, Any]:
        """Obtener resumen de estadísticas de auditorías"""
        total = db.query(Audit).count()
        completed = db.query(Audit).filter(Audit.status == AuditStatus.COMPLETED).count()
        running = db.query(Audit).filter(Audit.status == AuditStatus.RUNNING).count()
        failed = db.query(Audit).filter(Audit.status == AuditStatus.FAILED).count()
        pending = db.query(Audit).filter(Audit.status == AuditStatus.PENDING).count()
        
        return {
            "total_audits": total,
            "completed": completed,
            "running": running,
            "failed": failed,
            "pending": pending,
            "success_rate": round((completed / max(1, total)) * 100, 2)
        }
    
    @staticmethod
    def set_pagespeed_data(db: Session, audit_id: int, pagespeed_data: Dict[str, Any]) -> Audit:
        """Store PageSpeed data in audit record"""
        audit = db.query(Audit).filter(Audit.id == audit_id).first()
        if audit:
            audit.pagespeed_data = pagespeed_data
            db.commit()
            db.refresh(audit)
            logger.info(f"PageSpeed data stored for audit {audit_id}")
        else:
            logger.warning(f"Audit {audit_id} not found for PageSpeed data storage")
        return audit
    
    @staticmethod
    def get_pagespeed_data(db: Session, audit_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve PageSpeed data from audit record"""
        audit = db.query(Audit).filter(Audit.id == audit_id).first()
        return audit.pagespeed_data if audit else None
    
    @staticmethod
    def get_complete_audit_context(db: Session, audit_id: int) -> Dict[str, Any]:
        """
        Get complete audit context for LLM/GitHub App.
        
        Returns all available data:
        - target_audit
        - external_intelligence
        - search_results
        - competitor_audits
        - pagespeed_data
        - keywords
        - backlinks
        - rank_tracking
        - llm_visibility
        - ai_content_suggestions
        """
        audit = db.query(Audit).filter(Audit.id == audit_id).first()
        if not audit:
            logger.warning(f"Audit {audit_id} not found for complete context")
            return {}
        
        # Load related data
        keywords = []
        for k in audit.keywords:
            keywords.append({
                "term": k.term,
                "keyword": k.term,
                "search_volume": k.volume,
                "volume": k.volume,
                "difficulty": k.difficulty,
                "cpc": k.cpc,
                "intent": k.intent
            })
        
        backlinks_list = []
        for b in audit.backlinks:
            backlinks_list.append({
                "source_url": b.source_url,
                "target_url": b.target_url,
                "anchor_text": b.anchor_text,
                "domain_authority": b.domain_authority,
                "authority": b.domain_authority,
                "da": b.domain_authority,
                "is_dofollow": b.is_dofollow
            })
        
        rank_tracking = []
        for r in audit.rank_trackings:
            rank_tracking.append({
                "keyword": r.keyword,
                "position": r.position,
                "rank": r.position,
                "url": r.url,
                "device": r.device,
                "location": r.location
            })
        
        llm_visibility = []
        for l in audit.llm_visibilities:
            llm_visibility.append({
                "query": l.query,
                "llm_name": l.llm_name,
                "is_visible": l.is_visible,
                "rank": l.rank,
                "citation_text": l.citation_text
            })
        
        ai_content = []
        for a in audit.ai_content_suggestions:
            ai_content.append({
                "topic": a.topic,
                "suggestion_type": a.suggestion_type,
                "content_outline": a.content_outline,
                "priority": a.priority,
                "page_url": a.page_url
            })
        
        context = {
            "target_audit": audit.target_audit or {},
            "external_intelligence": audit.external_intelligence or {},
            "search_results": audit.search_results or {},
            "competitor_audits": audit.competitor_audits or [],
            "pagespeed": audit.pagespeed_data or {},
            "keywords": {"items": keywords, "total": len(keywords)},
            "backlinks": {"items": backlinks_list, "total": len(backlinks_list)},
            "rank_tracking": {"items": rank_tracking, "total": len(rank_tracking)},
            "llm_visibility": {"items": llm_visibility, "total": len(llm_visibility)},
            "ai_content_suggestions": {"items": ai_content, "total": len(ai_content)}
        }
        
        logger.info(f"Complete context loaded for audit {audit_id}")
        return context


class ReportService:
    """Servicio para gestionar reportes"""

    @staticmethod
    def create_report(
        db: Session, audit_id: int, report_type: str, file_path: Optional[str] = None
    ) -> Report:
        """Crear nuevo reporte"""
        file_size = None
        if file_path and os.path.exists(file_path):
            file_size = os.path.getsize(file_path)

        report = Report(
            audit_id=audit_id,
            report_type=report_type,
            file_path=file_path,
            file_size=file_size,
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        logger.info(f"Reporte creado: {report.id} (tipo: {report_type})")
        return report

    @staticmethod
    def get_reports_by_audit(db: Session, audit_id: int) -> List[Report]:
        """Obtener reportes de auditoría"""
        return (
            db.query(Report)
            .filter(Report.audit_id == audit_id)
            .order_by(desc(Report.created_at))
            .all()
        )

    @staticmethod
    def get_report(db: Session, report_id: int) -> Optional[Report]:
        """Obtener reporte por ID"""
        return db.query(Report).filter(Report.id == report_id).first()

    @staticmethod
    def delete_old_reports(db: Session, audit_id: int) -> int:
        """Eliminar reportes antiguos de una auditoría"""
        reports = db.query(Report).filter(Report.audit_id == audit_id).all()
        deleted = 0
        for report in reports:
            if report.file_path and os.path.exists(report.file_path):
                try:
                    os.remove(report.file_path)
                    deleted += 1
                except Exception as e:
                    logger.warning(f"No se pudo eliminar {report.file_path}: {e}")
            db.delete(report)
        db.commit()
        return deleted


class CompetitorService:
    """Servicio para gestionar competidores"""

    @staticmethod
    def _calculate_geo_score(audit_data: Dict[str, Any]) -> float:
        """Calcular GEO score basado en datos de auditoría (0-100).

        - Usa solo señales disponibles (no penaliza por ausencia de datos).
        - Normaliza métricas a 0-100 y aplica pesos.
        """
        try:
            weights = []

            def _coerce_number(value: Any) -> Optional[float]:
                if isinstance(value, (int, float)):
                    return float(value)
                try:
                    return float(value)
                except Exception:
                    return None

            def _add_metric(score_value: Optional[float], weight: float) -> None:
                if score_value is None:
                    return
                clamped = max(0.0, min(100.0, score_value))
                weights.append((clamped, weight))

            # 1) Schema presence (weight 30)
            schema_status = (
                audit_data.get("schema", {})
                .get("schema_presence", {})
                .get("status")
            )
            if schema_status is not None:
                _add_metric(100.0 if schema_status == "present" else 0.0, 30.0)

            # 2) Semantic HTML / Structure (weight 20)
            structure = audit_data.get("structure", {}) or {}
            semantic_score = _coerce_number(
                (structure.get("semantic_html") or {}).get("score_percent")
            )
            used_site_metrics_structure = False
            if semantic_score is None:
                site_metrics = audit_data.get("site_metrics", {}) or {}
                structure_score_percent = _coerce_number(
                    site_metrics.get("structure_score_percent")
                )
                if structure_score_percent is not None:
                    semantic_score = structure_score_percent
                    used_site_metrics_structure = True
            _add_metric(semantic_score, 20.0)

            # 3) E-E-A-T Author presence (weight 20)
            author_status = (
                audit_data.get("eeat", {})
                .get("author_presence", {})
                .get("status")
            )
            if author_status is not None:
                _add_metric(100.0 if author_status == "pass" else 0.0, 20.0)

            # 4) Conversational Tone (weight 15)
            tone_score = _coerce_number(
                (audit_data.get("content", {}) or {})
                .get("conversational_tone", {})
                .get("score")
            )
            if tone_score is not None:
                _add_metric((tone_score / 10.0) * 100.0, 15.0)

            # 5) H1 presence (weight 15)
            h1_status = structure.get("h1_check", {}).get("status")
            if h1_status is not None and not used_site_metrics_structure:
                _add_metric(100.0 if h1_status == "pass" else 0.0, 15.0)

            if not weights:
                return 0.0

            total_weight = sum(weight for _, weight in weights)
            total_score = sum(score * weight for score, weight in weights) / total_weight
            final_score = max(0.0, min(100.0, total_score))
            return round(final_score, 1)
        except Exception as e:
            logger.error(f"Error calculando GEO score: {e}")
            return 0.0  # Sin datos suficientes para calcular

    @staticmethod
    def _format_competitor_data(audit_data: Dict[str, Any], geo_score: float, url: str = None) -> Dict[str, Any]:
        """Formatear datos de competitor para el frontend con todos los campos necesarios"""
        try:
            # Extraer URL
            comp_url = url or audit_data.get("url", "")
            domain = comp_url.replace("https://", "").replace("http://", "").split("/")[0]
            
            # Extraer datos individuales de schema
            schema_data = audit_data.get("schema", {})
            schema_status = schema_data.get("schema_presence", {}).get("status")
            schema_present = schema_status == "present"
            
            # Extraer semantic HTML score
            structure_data = audit_data.get("structure", {})
            semantic_html = structure_data.get("semantic_html", {})
            semantic_score = semantic_html.get("score_percent", 0)
            if not isinstance(semantic_score, (int, float)):
                semantic_score = 0

            # H1 status + header hierarchy health
            h1_status = structure_data.get("h1_check", {}).get("status")
            h1_coverage = 100 if h1_status == "pass" else 0
            header_issues = structure_data.get("header_hierarchy", {}).get("issues") or []
            header_hierarchy_coverage = 100 if not header_issues else 0

            # Prefer site_metrics if present (aggregate)
            site_metrics = audit_data.get("site_metrics", {}) if isinstance(audit_data.get("site_metrics"), dict) else {}
            structure_score = site_metrics.get("structure_score_percent")
            if not isinstance(structure_score, (int, float)):
                structure_score = round((semantic_score + h1_coverage + header_hierarchy_coverage) / 3, 1)
            
            # Extraer E-E-A-T
            eeat_data = audit_data.get("eeat", {})
            author_status = eeat_data.get("author_presence", {}).get("status")
            eeat_score = 100 if author_status == "pass" else 0
            
            # Extraer H1
            h1_present = h1_status == "pass"
            
            # Extraer conversational tone
            content_data = audit_data.get("content", {})
            conversational_tone = content_data.get("conversational_tone", {})
            tone_score = conversational_tone.get("score", 0)
            if not isinstance(tone_score, (int, float)):
                tone_score = 0
            tone_score = max(0.0, min(10.0, float(tone_score)))
            
            return {
                "url": comp_url,
                "domain": domain,
                "geo_score": geo_score,
                "schema_present": schema_present,
                "structure_score": structure_score,
                "eeat_score": eeat_score,
                "h1_present": h1_present,
                "h1_status": h1_status,
                "tone_score": tone_score,
            }
        except Exception as e:
            logger.error(f"Error formateando datos de competidor: {e}")
            return {
                "url": url or audit_data.get("url", ""),
                "domain": "",
                "geo_score": geo_score,
                "schema_present": False,
                "structure_score": 0,
                "eeat_score": 0,
                "h1_present": False,
                "tone_score": 0,
            }

    @staticmethod
    def add_competitor(
        db: Session,
        audit_id: int,
        url: str,
        geo_score: float,
        audit_data: Dict[str, Any],
    ) -> Competitor:
        """Añadir competidor analizado"""
        domain = url.replace("https://", "").replace("http://", "").split("/")[0]

        # Si no se proporciona geo_score, calcularlo
        raw_audit_data = audit_data if isinstance(audit_data, dict) else {}
        if geo_score == 0 or geo_score is None:
            geo_score = CompetitorService._calculate_geo_score(raw_audit_data)

        safe_audit_data = AuditService._sanitize_json_value(raw_audit_data)

        # NUEVO: Guardar archivo JSON del competidor
        try:
            from datetime import datetime
            reports_dir = os.path.join(settings.REPORTS_DIR or "reports", f"audit_{audit_id}")
            competitors_dir = os.path.join(reports_dir, "competitors")
            os.makedirs(competitors_dir, exist_ok=True)
            
            # Generar nombre de archivo seguro
            import re
            safe_domain = re.sub(r'[^\w\-_.]', '_', domain)
            competitor_json_path = os.path.join(competitors_dir, f"competitor_{safe_domain}.json")
            
            # Preparar datos completos del competidor
            competitor_full_data = {
                "url": url,
                "domain": domain,
                "geo_score": geo_score,
                "audit_data": safe_audit_data,
                "analyzed_at": datetime.now().isoformat()
            }
            
            # Guardar JSON
            with open(competitor_json_path, 'w', encoding='utf-8') as f:
                json.dump(competitor_full_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Competidor guardado: {domain} -> {competitor_json_path} (GEO Score: {geo_score})")
        except Exception as e:
            logger.error(f"Error guardando archivo JSON del competidor {domain}: {e}")

        competitor = Competitor(
            audit_id=audit_id,
            url=url,
            domain=domain,
            geo_score=geo_score,
            audit_data=safe_audit_data,
        )
        db.add(competitor)
        db.commit()
        db.refresh(competitor)
        return competitor

    @staticmethod
    def get_competitors(db: Session, audit_id: int) -> List[Competitor]:
        """Obtener competidores de auditoría"""
        return db.query(Competitor).filter(Competitor.audit_id == audit_id).all()

    @staticmethod
    def get_top_competitors_by_score(db: Session, limit: int = 5) -> List[Competitor]:
        """Obtener competidores mejor posicionados"""
        return (
            db.query(Competitor).order_by(desc(Competitor.geo_score)).limit(limit).all()
        )
