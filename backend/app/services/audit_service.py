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
        """Crear nueva auditoría"""
        url = str(audit_create.url)
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
            market=audit_create.market
        )
        db.add(audit)
        db.flush()
        db.commit()
        db.refresh(audit)

        logger.info(f"Auditoría creada: {audit.id} para {url}, competitors: {audit_create.competitors}")
        return audit

    @staticmethod
    def get_audit(db: Session, audit_id: int) -> Optional[Audit]:
        """Obtener auditoría por ID con report_pdf_path"""
        audit = db.query(Audit).filter(Audit.id == audit_id).first()
        if audit:
            # Agregar report_pdf_path desde los reportes
            pdf_report = db.query(Report).filter(
                Report.audit_id == audit_id,
                Report.report_type == "PDF"
            ).order_by(desc(Report.created_at)).first()
            
            # Agregar como atributo dinámico
            audit.report_pdf_path = pdf_report.file_path if pdf_report else None
        return audit

    @staticmethod
    def get_audits(db: Session, skip: int = 0, limit: int = 20) -> List[Audit]:
        """Obtener lista de auditorías con paginación"""
        audits = (
            db.query(Audit)
            .order_by(desc(Audit.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )
        
        # Agregar report_pdf_path a cada auditoría
        for audit in audits:
            pdf_report = db.query(Report).filter(
                Report.audit_id == audit.id,
                Report.report_type == "PDF"
            ).order_by(desc(Report.created_at)).first()
            audit.report_pdf_path = pdf_report.file_path if pdf_report else None
        
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
    def set_audit_results(
        db: Session,
        audit_id: int,
        target_audit: Dict[str, Any],
        external_intelligence: Dict[str, Any],
        search_results: Dict[str, Any],
        competitor_audits: List[Dict[str, Any]],
        report_markdown: str,
        fix_plan: List[Dict[str, Any]],
        pagespeed_data: Dict[str, Any] = None,
    ):
        """Guardar resultados de auditoría completa"""
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
        if pagespeed_data:
            logger.info(f"PageSpeed data saved to DB for audit {audit_id}")
        else:
            logger.warning(f"No PageSpeed data to save for audit {audit_id}")

        # Actualizar metadata
        audit.is_ymyl = external_intelligence.get("is_ymyl", False)
        audit.category = external_intelligence.get("category", "Desconocida")
        # target_audit ya es dict o {}
        audit.total_pages = target_audit.get("audited_pages_count", 0)

        # Contar issues
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
        from .audit_service import CompetitorService
        for comp_data in competitor_audits:
            if isinstance(comp_data, dict) and comp_data.get("url"):
                try:
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
        AuditService._save_audit_files(audit_id, target_audit, external_intelligence, 
                                     search_results, competitor_audits, fix_plan)

        db.commit()
        db.refresh(audit)
        logger.info(f"Resultados guardados para auditoría {audit_id}")
        return audit

    @staticmethod
    def _save_audit_files(
        audit_id: int,
        target_audit: Dict[str, Any],
        external_intelligence: Dict[str, Any],
        search_results: Dict[str, Any],
        competitor_audits: List[Dict[str, Any]],
        fix_plan: List[Dict[str, Any]]
    ):
        """Guardar archivos JSON de auditoría como en ag2_pipeline.py"""
        try:
            # Crear directorio de reportes
            reports_dir = os.path.join(settings.REPORTS_DIR or "reports", f"audit_{audit_id}")
            pages_dir = os.path.join(reports_dir, "pages")
            os.makedirs(reports_dir, exist_ok=True)
            
            # IMPORTANTE: NO limpiar carpeta pages si ya contiene archivos de páginas individuales
            # Estos archivos fueron guardados previamente por save_page_audit
            if os.path.exists(pages_dir):
                existing_files = [f for f in os.listdir(pages_dir) if f.startswith('report_') and f.endswith('.json')]
                if existing_files:
                    logger.info(f"Preservando {len(existing_files)} archivos de páginas individuales en {pages_dir}")
                else:
                    logger.info(f"Carpeta pages existe pero está vacía, recreando")
                    import shutil
                    shutil.rmtree(pages_dir)
                    os.makedirs(pages_dir, exist_ok=True)
            else:
                os.makedirs(pages_dir, exist_ok=True)
                logger.info(f"Carpeta pages creada: {pages_dir}")

            # Guardar resumen agregado
            aggregated_path = os.path.join(reports_dir, "aggregated_summary.json")
            with open(aggregated_path, 'w', encoding='utf-8') as f:
                json.dump(target_audit, f, ensure_ascii=False, indent=2)

            # Cargar PageSpeed si existe
            pagespeed_path = os.path.join(reports_dir, "pagespeed.json")
            pagespeed_data = {}
            if os.path.exists(pagespeed_path):
                try:
                    with open(pagespeed_path, 'r', encoding='utf-8') as f:
                        pagespeed_data = json.load(f)
                except:
                    pass
            
            # Generar análisis de PageSpeed con LLM
            pagespeed_analysis = ""
            if pagespeed_data:
                try:
                    from ..core.llm_kimi import get_llm_function
                    llm = get_llm_function()
                    
                    mobile = pagespeed_data.get('mobile', {})
                    desktop = pagespeed_data.get('desktop', {})
                    
                    # Extraer todas las oportunidades y diagnósticos
                    mobile_opps = mobile.get('opportunities', {})
                    mobile_diags = mobile.get('diagnostics', {})
                    
                    top_opps = []
                    for key, val in mobile_opps.items():
                        if isinstance(val, dict) and val.get('title'):
                            top_opps.append(f"- {val['title']}: {val.get('displayValue', 'N/A')}")
                    
                    top_diags = []
                    for key, val in mobile_diags.items():
                        if isinstance(val, dict) and val.get('displayValue'):
                            top_diags.append(f"- {val.get('title', key)}: {val['displayValue']}")
                    
                    opps_text = '\n'.join(top_opps[:10])
                    diags_text = '\n'.join(top_diags[:10])
                    
                    prompt = f"""Genera resumen ejecutivo de rendimiento web (max 200 palabras):

Mobile Perf: {mobile.get('performance_score')}/100, LCP: {mobile.get('core_web_vitals', {}).get('lcp', 0)/1000:.2f}s
Desktop Perf: {desktop.get('performance_score')}/100
Top Issues: {opps_text[:200]}

Formato:

### Diagnostico
[2 lineas: evaluacion general]

### Impacto en Negocio  
[2 lineas: efecto en usuarios/conversiones]

### Acciones Prioritarias
1. [Accion + beneficio]
2. [Accion + beneficio]
3. [Accion + beneficio]

Sin datos numericos repetidos. Sin tablas. Markdown limpio."""
                    
                    import asyncio
                    pagespeed_analysis = asyncio.run(llm(
                        system_prompt="Eres consultor de rendimiento web. Genera resumenes ejecutivos concisos para PDFs. Markdown limpio, sin bloques de codigo.",
                        user_prompt=prompt
                    ))
                    pagespeed_analysis = pagespeed_analysis.replace('```markdown', '').replace('```', '').strip()
                    
                    # Guardar análisis
                    analysis_path = os.path.join(reports_dir, "pagespeed_analysis.md")
                    with open(analysis_path, 'w', encoding='utf-8') as f:
                        f.write(pagespeed_analysis)
                except Exception as e:
                    logger.error(f"Error generando análisis PageSpeed: {e}")
            
            # Guardar contexto final del LLM
            final_context = {
                "target_audit": target_audit,
                "external_intelligence": external_intelligence,
                "search_results": search_results,
                "competitor_audits": competitor_audits,
                "pagespeed": pagespeed_data,
                "pagespeed_analysis": pagespeed_analysis
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
            scores = []
            
            # Score de estructura semántica
            if audit_data.get("structure", {}).get("semantic_html", {}).get("score_percent"):
                scores.append(audit_data["structure"]["semantic_html"]["score_percent"])
            
            # Score de tono conversacional
            if audit_data.get("content", {}).get("conversational_tone", {}).get("score"):
                scores.append(audit_data["content"]["conversational_tone"]["score"] * 10)  # Normalizar a 100
            
            # Penalizar por problemas críticos
            penalty = 0
            if audit_data.get("structure", {}).get("h1_check", {}).get("status") != "pass":
                penalty += 10
            if audit_data.get("eeat", {}).get("author_presence", {}).get("status") != "pass":
                penalty += 15
            if audit_data.get("schema", {}).get("schema_presence", {}).get("status") != "present":
                penalty += 20
            
            base_score = sum(scores) / len(scores) if scores else 50
            final_score = max(0, base_score - penalty)
            
            return round(final_score, 1)
        except Exception:
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
            if eeat.get("author_presence", {}).get("status") == "pass":
                scores.append(100)
            if eeat.get("expertise_signals"):
                scores.append(80)
            return sum(scores) / len(scores) if scores else 0
        except:
            return 0.0
    
    @staticmethod
    def _extract_schema_score(audit_data: Dict[str, Any]) -> float:
        try:
            schema = audit_data.get("schema", {}).get("schema_presence", {})
            if schema.get("status") == "present":
                types_count = len(schema.get("types", []))
                return min(100, types_count * 20)  # 20 puntos por tipo
            return 0.0
        except:
            return 0.0
    
    @staticmethod
    def _count_page_issues(audit_data: Dict[str, Any]) -> tuple:
        critical = high = medium = low = 0
        try:
            # Contar issues críticos
            if audit_data.get("structure", {}).get("h1_check", {}).get("status") != "pass":
                critical += 1
            if not audit_data.get("schema", {}).get("schema_presence", {}).get("status") == "present":
                high += 1
            if audit_data.get("eeat", {}).get("author_presence", {}).get("status") != "pass":
                high += 1
            
            # Issues de estructura
            semantic = audit_data.get("structure", {}).get("semantic_html", {})
            if semantic.get("score_percent", 100) < 50:
                medium += 1
            
            # Issues de contenido
            content = audit_data.get("content", {})
            if content.get("conversational_tone", {}).get("score", 10) < 5:
                medium += 1
        except:
            pass
        
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
        """Calcular GEO score basado en datos de auditoría (0-10)"""
        try:
            score = 10.0
            
            # Penalización por falta de Schema (-3 puntos)
            schema_status = audit_data.get("schema", {}).get("schema_presence", {}).get("status")
            if schema_status != "present":
                score -= 3.0
            
            # Penalización por HTML semántico bajo (-2 puntos si < 50%)
            semantic_score = audit_data.get("structure", {}).get("semantic_html", {}).get("score_percent", 0)
            if semantic_score < 50:
                score -= 2.0
            elif semantic_score < 70:
                score -= 1.0
            
            # Penalización por falta de autor (-2 puntos)
            author_status = audit_data.get("eeat", {}).get("author_presence", {}).get("status")
            if author_status != "pass":
                score -= 2.0
            
            # Penalización por tono no conversacional (-1 punto si < 3)
            conversational = audit_data.get("content", {}).get("conversational_tone", {}).get("score", 0)
            if conversational < 3:
                score -= 1.0
            
            # Penalización por falta de H1 (-1 punto)
            h1_status = audit_data.get("structure", {}).get("h1_check", {}).get("status")
            if h1_status != "pass":
                score -= 1.0
            
            return max(0.0, min(10.0, score))
        except Exception as e:
            logger.error(f"Error calculando GEO score: {e}")
            return 5.0  # Score por defecto

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
