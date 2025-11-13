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

        audit = Audit(url=url, domain=domain, status=AuditStatus.PENDING)
        db.add(audit)
        db.commit()
        db.refresh(audit)

        logger.info(f"Auditoría creada: {audit.id} para {url}")
        return audit

    @staticmethod
    def get_audit(db: Session, audit_id: int) -> Optional[Audit]:
        """Obtener auditoría por ID"""
        return db.query(Audit).filter(Audit.id == audit_id).first()

    @staticmethod
    def get_audits(db: Session, skip: int = 0, limit: int = 20) -> List[Audit]:
        """Obtener lista de auditorías con paginación"""
        return (
            db.query(Audit)
            .order_by(desc(Audit.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )

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
    ):
        """Guardar resultados de auditoría completa"""
        audit = db.query(Audit).filter(Audit.id == audit_id).first()
        if not audit:
            return None

        audit.target_audit = target_audit
        audit.external_intelligence = external_intelligence
        audit.search_results = search_results
        audit.competitor_audits = competitor_audits
        audit.report_markdown = report_markdown
        audit.fix_plan = fix_plan

        # Actualizar metadata
        audit.is_ymyl = external_intelligence.get("is_ymyl", False)
        audit.category = external_intelligence.get("category", "Desconocida")
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

        db.commit()
        db.refresh(audit)
        logger.info(f"Resultados guardados para auditoría {audit_id}")
        return audit

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
        page = AuditedPage(
            audit_id=audit_id,
            url=url,
            path=path,
            audit_data=audit_data,
            overall_score=overall_score,
        )
        db.add(page)
        db.commit()
        db.refresh(page)
        return page

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
        completed = len(db.query(Audit).filter(Audit.status == AuditStatus.COMPLETED).all())
        running = len(db.query(Audit).filter(Audit.status == AuditStatus.RUNNING).all())
        failed = len(db.query(Audit).filter(Audit.status == AuditStatus.FAILED).all())
        pending = len(db.query(Audit).filter(Audit.status == AuditStatus.PENDING).all())
        
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
        return deleted


class CompetitorService:
    """Servicio para gestionar competidores"""

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
