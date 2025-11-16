"""
Modelos de Base de Datos
"""
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    DateTime,
    Text,
    JSON,
    Boolean,
    Enum,
    ForeignKey,
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum
from ..core.database import Base


class AuditStatus(str, enum.Enum):
    """Estados posibles de una auditoría"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Audit(Base):
    """Modelo para auditorías de sitios web"""

    __tablename__ = "audits"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String(255), nullable=False)
    domain = Column(String(255), index=True)

    status = Column(Enum(AuditStatus), default=AuditStatus.PENDING)
    progress = Column(Float, default=0.0)  # 0-100

    # Resumen de hallazgos
    total_pages = Column(Integer, default=0)
    critical_issues = Column(Integer, default=0)
    high_issues = Column(Integer, default=0)
    medium_issues = Column(Integer, default=0)
    low_issues = Column(Integer, default=0)

    # Datos de auditoría
    target_audit = Column(JSON, nullable=True)
    external_intelligence = Column(JSON, nullable=True)
    search_results = Column(JSON, nullable=True)
    competitor_audits = Column(JSON, nullable=True)
    pagespeed_data = Column(JSON, nullable=True)

    # Resultados
    report_markdown = Column(Text, nullable=True)
    fix_plan = Column(JSON, nullable=True)

    # Metadata
    is_ymyl = Column(Boolean, default=False)
    category = Column(String(255), nullable=True)
    language = Column(String(10), default="es")  # "en" o "es"
    competitors = Column(JSON, nullable=True)  # Lista de URLs de competidores
    market = Column(String(50), nullable=True)  # "us", "latam", "emea", etc.

    # Timestamps
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), index=True
    )
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Relación con reportes
    reports = relationship(
        "Report", back_populates="audit", cascade="all, delete-orphan"
    )
    pages = relationship(
        "AuditedPage", back_populates="audit", cascade="all, delete-orphan"
    )

    # Task ID de Celery
    task_id = Column(String(255), nullable=True, unique=True, index=True)
    error_message = Column(Text, nullable=True)
    
    # Propiedad dinámica para report_pdf_path (se calcula desde reports)
    @property
    def report_pdf_path(self):
        if hasattr(self, '_report_pdf_path'):
            return self._report_pdf_path
        return None
    
    @report_pdf_path.setter
    def report_pdf_path(self, value):
        self._report_pdf_path = value


class Report(Base):
    """Modelo para reportes generados"""

    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    audit_id = Column(Integer, ForeignKey("audits.id"), nullable=False)

    report_type = Column(String(50))  # "markdown", "pdf", "json"
    file_path = Column(String(500), nullable=True)
    file_size = Column(Integer, nullable=True)  # en bytes

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    audit = relationship("Audit", back_populates="reports")


class AuditedPage(Base):
    """Modelo para páginas auditadas"""

    __tablename__ = "audited_pages"

    id = Column(Integer, primary_key=True, index=True)
    audit_id = Column(Integer, ForeignKey("audits.id"), nullable=False)

    url = Column(String(500), nullable=False)
    path = Column(String(500))

    # Puntuaciones
    h1_score = Column(Float, default=0)
    structure_score = Column(Float, default=0)
    content_score = Column(Float, default=0)
    eeat_score = Column(Float, default=0)
    schema_score = Column(Float, default=0)
    overall_score = Column(Float, default=0)

    # Issues encontrados
    critical_issues = Column(Integer, default=0)
    high_issues = Column(Integer, default=0)
    medium_issues = Column(Integer, default=0)
    low_issues = Column(Integer, default=0)

    # Datos detallados
    audit_data = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    audit = relationship("Audit", back_populates="pages")


class CrawlJob(Base):
    """Modelo para trabajos de crawling"""

    __tablename__ = "crawl_jobs"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String(255), nullable=False)
    status = Column(Enum(AuditStatus), default=AuditStatus.PENDING)

    urls_found = Column(Integer, default=0)
    urls_data = Column(JSON, nullable=True)  # Lista de URLs encontradas

    task_id = Column(String(255), nullable=True, unique=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)


class Competitor(Base):
    """Modelo para competidores analizados"""

    __tablename__ = "competitors"

    id = Column(Integer, primary_key=True, index=True)
    audit_id = Column(Integer, ForeignKey("audits.id"), nullable=True)

    url = Column(String(500), nullable=False)
    domain = Column(String(255), index=True)

    geo_score = Column(Float, default=0)
    schema_types = Column(JSON, nullable=True)
    audit_data = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
