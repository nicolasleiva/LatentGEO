"""
Modelos de Base de Datos
"""

# ruff: noqa: E402

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

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
    source = Column(String(50), default="web")  # web, hubspot, etc.

    # User association (Auth0)
    user_id = Column(String(255), nullable=True, index=True)  # Auth0 user sub
    user_email = Column(
        String(255), nullable=True, index=True
    )  # User email for display

    status = Column(Enum(AuditStatus), default=AuditStatus.PENDING)
    progress = Column(Float, default=0.0)  # 0-100

    # Resumen de hallazgos
    total_pages = Column(Integer, default=0)
    critical_issues = Column(Integer, default=0)
    high_issues = Column(Integer, default=0)
    medium_issues = Column(Integer, default=0)
    low_issues = Column(Integer, default=0)
    geo_score = Column(Float, default=0.0)

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
    language = Column(String(10), default="en")  # forced to "en"
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
    backlinks = relationship(
        "Backlink", back_populates="audit", cascade="all, delete-orphan"
    )
    keywords = relationship(
        "Keyword", back_populates="audit", cascade="all, delete-orphan"
    )
    rank_trackings = relationship(
        "RankTracking", back_populates="audit", cascade="all, delete-orphan"
    )
    llm_visibilities = relationship(
        "LLMVisibility", back_populates="audit", cascade="all, delete-orphan"
    )
    ai_content_suggestions = relationship(
        "AIContentSuggestion", back_populates="audit", cascade="all, delete-orphan"
    )
    geo_commerce_campaigns = relationship(
        "GeoCommerceCampaign", back_populates="audit", cascade="all, delete-orphan"
    )
    geo_article_batches = relationship(
        "GeoArticleBatch", back_populates="audit", cascade="all, delete-orphan"
    )

    # Task ID de Celery
    task_id = Column(String(255), nullable=True, unique=True, index=True)
    error_message = Column(Text, nullable=True)

    # Propiedad dinámica para report_pdf_path (se calcula desde reports)
    @property
    def report_pdf_path(self):
        if hasattr(self, "_report_pdf_path"):
            return self._report_pdf_path
        return None

    @report_pdf_path.setter
    def report_pdf_path(self, value):
        self._report_pdf_path = value


class Report(Base):
    """Modelo para reportes generados"""

    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    audit_id = Column(Integer, ForeignKey("audits.id"), nullable=False, index=True)

    report_type = Column(String(50))  # "markdown", "pdf", "json"
    file_path = Column(String(500), nullable=True)
    file_size = Column(Integer, nullable=True)  # en bytes

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    audit = relationship("Audit", back_populates="reports")


class AuditedPage(Base):
    """Modelo para páginas auditadas"""

    __tablename__ = "audited_pages"

    id = Column(Integer, primary_key=True, index=True)
    audit_id = Column(Integer, ForeignKey("audits.id"), nullable=False, index=True)

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
    audit_id = Column(Integer, ForeignKey("audits.id"), nullable=True, index=True)

    url = Column(String(500), nullable=False)
    domain = Column(String(255), index=True)

    geo_score = Column(Float, default=0)
    schema_types = Column(JSON, nullable=True)
    audit_data = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Backlink(Base):
    """Modelo para backlinks"""

    __tablename__ = "backlinks"

    id = Column(Integer, primary_key=True, index=True)
    audit_id = Column(Integer, ForeignKey("audits.id"), nullable=False, index=True)

    source_url = Column(String(500), nullable=False)
    target_url = Column(String(500), nullable=False)
    anchor_text = Column(String(500), nullable=True)
    is_dofollow = Column(Boolean, default=True)
    domain_authority = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    audit = relationship("Audit", back_populates="backlinks")


class Keyword(Base):
    """Modelo para keyword research"""

    __tablename__ = "keywords"

    id = Column(Integer, primary_key=True, index=True)
    audit_id = Column(Integer, ForeignKey("audits.id"), nullable=False, index=True)

    term = Column(String(255), nullable=False)
    volume = Column(Integer, default=0)
    difficulty = Column(Integer, default=0)
    cpc = Column(Float, default=0.0)
    intent = Column(String(50), nullable=True)  # informational, commercial, etc.

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    audit = relationship("Audit", back_populates="keywords")


class RankTracking(Base):
    """Modelo para seguimiento de rankings"""

    __tablename__ = "rank_trackings"

    id = Column(Integer, primary_key=True, index=True)
    audit_id = Column(Integer, ForeignKey("audits.id"), nullable=False, index=True)

    keyword = Column(String(255), nullable=False)
    position = Column(Integer, nullable=False)
    url = Column(String(500), nullable=False)
    device = Column(String(20), default="desktop")  # desktop, mobile
    location = Column(String(50), default="US")
    top_results = Column(
        JSON, nullable=True
    )  # Top 10 results: [{position, url, title, domain}]

    tracked_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    audit = relationship("Audit", back_populates="rank_trackings")


class LLMVisibility(Base):
    """Modelo para visibilidad en LLMs"""

    __tablename__ = "llm_visibilities"

    id = Column(Integer, primary_key=True, index=True)
    audit_id = Column(Integer, ForeignKey("audits.id"), nullable=False, index=True)

    llm_name = Column(String(50), nullable=False)  # ChatGPT, Perplexity, Gemini
    query = Column(String(500), nullable=False)
    is_visible = Column(Boolean, default=False)
    rank = Column(Integer, nullable=True)  # Si aparece en lista
    citation_text = Column(Text, nullable=True)

    checked_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    audit = relationship("Audit", back_populates="llm_visibilities")


class AIContentSuggestion(Base):
    """Modelo para sugerencias de contenido IA"""

    __tablename__ = "ai_content_suggestions"

    id = Column(Integer, primary_key=True, index=True)
    audit_id = Column(Integer, ForeignKey("audits.id"), nullable=False, index=True)

    page_url = Column(String(500), nullable=True)
    topic = Column(String(255), nullable=False)
    suggestion_type = Column(
        String(50), nullable=False
    )  # new_content, optimization, faq
    content_outline = Column(JSON, nullable=True)
    priority = Column(String(20), default="medium")

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    audit = relationship("Audit", back_populates="ai_content_suggestions")


class GeoCommerceCampaign(Base):
    """Campaign payload for ecommerce GEO growth playbooks."""

    __tablename__ = "geo_commerce_campaigns"

    id = Column(Integer, primary_key=True, index=True)
    audit_id = Column(Integer, ForeignKey("audits.id"), nullable=False, index=True)
    market = Column(String(50), nullable=True)
    channels = Column(JSON, nullable=True)
    objective = Column(String(500), nullable=True)
    payload = Column(JSON, nullable=False)
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), index=True
    )

    audit = relationship("Audit", back_populates="geo_commerce_campaigns")


class GeoArticleBatch(Base):
    """Batch of generated GEO articles for a given audit."""

    __tablename__ = "geo_article_batches"

    id = Column(Integer, primary_key=True, index=True)
    audit_id = Column(Integer, ForeignKey("audits.id"), nullable=False, index=True)
    requested_count = Column(Integer, default=1)
    language = Column(String(10), default="en")
    tone = Column(String(30), default="executive")
    include_schema = Column(Boolean, default=True)
    status = Column(String(20), default="completed")
    summary = Column(JSON, nullable=True)
    articles = Column(JSON, nullable=True)
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), index=True
    )

    audit = relationship("Audit", back_populates="geo_article_batches")


class CitationTracking(Base):
    """Modelo para tracking de citaciones en LLMs"""

    __tablename__ = "citation_tracking"

    id = Column(Integer, primary_key=True, index=True)
    audit_id = Column(Integer, ForeignKey("audits.id"), nullable=False, index=True)

    query = Column(String(500), nullable=False)
    llm_name = Column(String(50), nullable=False)  # kimi, chatgpt, perplexity
    is_mentioned = Column(Boolean, default=False)
    citation_text = Column(Text, nullable=True)
    sentiment = Column(String(20), nullable=True)  # positive, neutral, negative
    position = Column(Integer, nullable=True)  # Posición de la mención
    full_response = Column(Text, nullable=True)

    tracked_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), index=True
    )


class DiscoveredQuery(Base):
    """Modelo para queries descubiertas"""

    __tablename__ = "discovered_queries"

    id = Column(Integer, primary_key=True, index=True)
    audit_id = Column(Integer, ForeignKey("audits.id"), nullable=False, index=True)

    query = Column(String(500), nullable=False)
    intent = Column(
        String(50), nullable=True
    )  # informational, commercial, transactional
    mentions_brand = Column(Boolean, default=False)
    potential_score = Column(Integer, default=0)
    sample_response = Column(Text, nullable=True)

    discovered_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class CompetitorCitationAnalysis(Base):
    """Modelo para análisis de citaciones de competidores"""

    __tablename__ = "competitor_citation_analysis"

    id = Column(Integer, primary_key=True, index=True)
    audit_id = Column(Integer, ForeignKey("audits.id"), nullable=False, index=True)

    your_mentions = Column(Integer, default=0)
    competitor_data = Column(JSON, nullable=True)  # Datos de competidores
    gap_analysis = Column(JSON, nullable=True)  # Análisis de brechas

    analyzed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ScoreHistory(Base):
    """Modelo para historial de scores - permite tracking temporal"""

    __tablename__ = "score_history"

    id = Column(Integer, primary_key=True, index=True)
    domain = Column(String(255), nullable=False, index=True)
    user_id = Column(String(255), nullable=True, index=True)  # Auth0 user sub

    # Scores principales
    overall_score = Column(Float, default=0)
    seo_score = Column(Float, default=0)
    geo_score = Column(Float, default=0)
    performance_score = Column(Float, default=0)
    accessibility_score = Column(Float, default=0)
    best_practices_score = Column(Float, default=0)

    # Core Web Vitals
    lcp = Column(Float, nullable=True)  # Largest Contentful Paint (ms)
    fid = Column(Float, nullable=True)  # First Input Delay (ms)
    cls = Column(Float, nullable=True)  # Cumulative Layout Shift

    # Issues count
    critical_issues = Column(Integer, default=0)
    high_issues = Column(Integer, default=0)
    medium_issues = Column(Integer, default=0)
    low_issues = Column(Integer, default=0)
    total_pages = Column(Integer, default=0)

    # Citation/GEO metrics
    citation_rate = Column(Float, default=0)
    llm_mentions = Column(Integer, default=0)

    # Metadata
    audit_id = Column(Integer, ForeignKey("audits.id"), nullable=True, index=True)
    recorded_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), index=True
    )


# Importar modelos de GitHub
from .github import GitHubConnection as GitHubConnection  # noqa: E402
from .github import GitHubPullRequest as GitHubPullRequest
from .github import GitHubRepository as GitHubRepository
from .github import GitHubWebhookEvent as GitHubWebhookEvent

# Importar modelos de HubSpot
from .hubspot import HubSpotChange as HubSpotChange  # noqa: E402
from .hubspot import HubSpotConnection as HubSpotConnection
from .hubspot import HubSpotPage as HubSpotPage
