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
            language=audit_create.language or "es",
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

        audit.target_audit = target_audit
        audit.external_intelligence = external_intelligence
        audit.search_results = search_results
        audit.competitor_audits = competitor_audits
        audit.report_markdown = report_markdown
        audit.fix_plan = fix_plan
        audit.pagespeed_data = pagespeed_data

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
        audit.category = external_intelligence.get("category", "Desconocida")
        # target_audit ya es dict o {}
        audit.total_pages = target_audit.get("audited_pages_count", 0)

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
        for comp_data in competitor_audits:
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
            audit_id, target_audit, external_intelligence, 
            search_results, competitor_audits, fix_plan, 
            pagespeed_data, keywords, backlinks, rankings, llm_visibility
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
            # Crear directorio de reportes
            reports_dir = os.path.join(settings.REPORTS_DIR or "reports", f"audit_{audit_id}")
            pages_dir = os.path.join(reports_dir, "pages")
            competitors_dir = os.path.join(reports_dir, "competitors")
            os.makedirs(reports_dir, exist_ok=True)
            os.makedirs(pages_dir, exist_ok=True)
            os.makedirs(competitors_dir, exist_ok=True)

            # Guardar resumen agregado
            aggregated_path = os.path.join(reports_dir, "aggregated_summary.json")
            with open(aggregated_path, 'w', encoding='utf-8') as f:
                json.dump(target_audit, f, ensure_ascii=False, indent=2)

            # Guardar fix_plan
            fix_plan_path = os.path.join(reports_dir, "fix_plan.json")
            with open(fix_plan_path, 'w', encoding='utf-8') as f:
                json.dump(fix_plan, f, ensure_ascii=False, indent=2)

            # Guardar PageSpeed
            if pagespeed_data:
                pagespeed_path = os.path.join(reports_dir, "pagespeed.json")
                with open(pagespeed_path, 'w', encoding='utf-8') as f:
                    json.dump(pagespeed_data, f, ensure_ascii=False, indent=2)

            # Guardar Keywords
            if keywords:
                keywords_path = os.path.join(reports_dir, "keywords.json")
                with open(keywords_path, 'w', encoding='utf-8') as f:
                    json.dump(keywords, f, ensure_ascii=False, indent=2)

            # Guardar Backlinks
            if backlinks:
                backlinks_path = os.path.join(reports_dir, "backlinks.json")
                with open(backlinks_path, 'w', encoding='utf-8') as f:
                    json.dump(backlinks, f, ensure_ascii=False, indent=2)

            # Guardar Rankings
            if rankings:
                rankings_path = os.path.join(reports_dir, "rankings.json")
                with open(rankings_path, 'w', encoding='utf-8') as f:
                    json.dump(rankings, f, ensure_ascii=False, indent=2)

            # Guardar LLM Visibility
            if llm_visibility:
                visibility_path = os.path.join(reports_dir, "llm_visibility.json")
                with open(visibility_path, 'w', encoding='utf-8') as f:
                    json.dump(llm_visibility, f, ensure_ascii=False, indent=2)

            # Guardar competidores individuales
            for i, comp in enumerate(competitor_audits):
                try:
                    domain = comp.get('domain') or f"competitor_{i}"
                    comp_path = os.path.join(competitors_dir, f"competitor_{domain}.json")
                    with open(comp_path, 'w', encoding='utf-8') as f:
                        json.dump(comp, f, ensure_ascii=False, indent=2)
                except:
                    pass
            
            # Guardar contexto final del LLM
            final_context = {
                "target_audit": target_audit,
                "external_intelligence": external_intelligence,
                "search_results": search_results,
                "competitor_audits": competitor_audits,
                "pagespeed": pagespeed_data,
                "keywords": keywords,
                "backlinks": backlinks,
                "rank_tracking": rankings,
                "llm_visibility": llm_visibility
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
                json.dump(audit_data, f, ensure_ascii=False, indent=2)

            # Extraer path de la URL
            from urllib.parse import urlparse
            parsed_url = urlparse(page_url)
            path = parsed_url.path or "/"

            # Calcular score general
            overall_score = AuditService._calculate_overall_score(audit_data)

            # Guardar en base de datos
            audited_page = AuditService.add_audited_page(
                db=db,
                audit_id=audit_id,
                url=page_url,
                path=path,
                audit_data=audit_data,
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
            if h1_status == "missing":
                critical += 1
            elif h1_status == "multiple":
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
        """Calcular GEO score basado en datos de auditoría (0-100)"""
        try:
            score = 100.0
            penalties = []
            
            # 1. Schema (-30.0) - CRITICAL
            schema_data = audit_data.get("schema", {})
            schema_status = schema_data.get("schema_presence", {}).get("status")
            if schema_status != "present":
                score -= 30.0
                penalties.append("no_schema")
            
            # 2. Semantic HTML (-20.0 / -10.0)
            semantic = audit_data.get("structure", {}).get("semantic_html", {})
            semantic_score = semantic.get("score_percent", 0) if semantic else 0
            if semantic_score < 50:
                score -= 20.0
                penalties.append("bad_semantic")
            elif semantic_score < 75:
                score -= 10.0
                penalties.append("poor_semantic")
            
            # 3. Author / EEAT (-20.0)
            eeat = audit_data.get("eeat", {})
            author_status = eeat.get("author_presence", {}).get("status") if eeat else "missing"
            if author_status != "pass":
                score -= 20.0
                penalties.append("no_author")
            
            # 4. Conversational Tone (-15.0) - Important for AI
            content = audit_data.get("content", {})
            conversational = content.get("conversational_tone", {}).get("score", 0) if content else 0
            if conversational < 4:
                score -= 15.0
                penalties.append("robotic_tone")
            
            # 5. H1 (-15.0)
            h1_status = audit_data.get("structure", {}).get("h1_check", {}).get("status")
            if h1_status != "pass":
                score -= 15.0
                penalties.append("bad_h1")

            final_score = max(0.0, min(100.0, score))
            return round(final_score, 1)
        except Exception as e:
            logger.error(f"Error calculando GEO score: {e}")
            return 50.0  # Score por defecto

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
            structure_score = semantic_html.get("score_percent", 0)
            
            # Extraer E-E-A-T
            eeat_data = audit_data.get("eeat", {})
            author_status = eeat_data.get("author_presence", {}).get("status")
            eeat_score = 100 if author_status == "pass" else 0
            
            # Extraer H1
            h1_status = structure_data.get("h1_check", {}).get("status")
            h1_present = h1_status == "pass"
            
            # Extraer conversational tone
            content_data = audit_data.get("content", {})
            conversational_tone = content_data.get("conversational_tone", {})
            tone_score = conversational_tone.get("score", 0)
            
            return {
                "url": comp_url,
                "domain": domain,
                "geo_score": geo_score,
                "schema_present": schema_present,
                "structure_score": structure_score,
                "eeat_score": eeat_score,
                "h1_present": h1_present,
                "tone_score": tone_score,
                "audit_data": audit_data  # Mantener datos completos para otros usos
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
                "audit_data": audit_data
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
        if geo_score == 0 or geo_score is None:
            geo_score = CompetitorService._calculate_geo_score(audit_data)

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
                "audit_data": audit_data,
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
            audit_data=audit_data,
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
