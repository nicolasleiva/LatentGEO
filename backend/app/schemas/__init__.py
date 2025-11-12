"""
Esquemas Pydantic para validación y serialización
"""

from pydantic import BaseModel, HttpUrl, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class AuditStatusEnum(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# ===== AUDIT SCHEMAS =====


class AuditCreate(BaseModel):
    """Schema para crear una nueva auditoría"""

    url: HttpUrl = Field(..., description="URL del sitio a auditar")
    max_crawl: int = Field(50, description="Máximo de páginas a crawlear")
    max_audit: int = Field(5, description="Máximo de páginas a auditar en detalle")


class AuditUpdate(BaseModel):
    """Schema para actualizar auditoría"""

    progress: Optional[float] = None
    status: Optional[AuditStatusEnum] = None
    error_message: Optional[str] = None


class PageSummary(BaseModel):
    """Resumen de página auditada"""

    url: str
    path: str
    overall_score: float
    critical_issues: int
    high_issues: int
    medium_issues: int
    low_issues: int


class AuditSummary(BaseModel):
    """Resumen de auditoría"""

    id: int
    url: str
    domain: str
    status: AuditStatusEnum
    progress: float
    total_pages: int
    critical_issues: int
    high_issues: int
    medium_issues: int
    low_issues: int
    is_ymyl: bool
    category: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class AuditDetail(AuditSummary):
    """Detalle completo de auditoría"""

    report_markdown: Optional[str]
    fix_plan: Optional[List[Dict[str, Any]]]
    pages: List[PageSummary]

    model_config = ConfigDict(from_attributes=True)


class AuditResponse(BaseModel):
    """Response de auditoría"""

    id: int
    url: str
    domain: str
    status: AuditStatusEnum
    progress: float
    task_id: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ===== REPORT SCHEMAS =====


class ReportCreate(BaseModel):
    """Schema para crear reporte"""

    audit_id: int
    report_type: str = Field("pdf", description="Tipo: markdown, pdf, json")


class ReportResponse(BaseModel):
    """Response de reporte"""

    id: int
    audit_id: int
    report_type: str
    file_path: Optional[str]
    file_size: Optional[int]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ===== CRAWLER SCHEMAS =====


class CrawlRequest(BaseModel):
    """Request para crawlear sitio"""

    url: HttpUrl
    max_pages: int = Field(50, ge=1, le=500)


class CrawlResponse(BaseModel):
    """Response de crawl"""

    task_id: str
    url: str
    status: AuditStatusEnum
    created_at: datetime


class CrawlResult(BaseModel):
    """Resultado de crawl"""

    url: str
    urls_found: int
    urls: List[str]
    completed_at: datetime


# ===== ANALYTICS SCHEMAS =====


class IssueSummary(BaseModel):
    """Resumen de issues"""

    category: str
    critical: int
    high: int
    medium: int
    low: int
    total: int


class ScoreSummary(BaseModel):
    """Resumen de puntuaciones"""

    h1_score: float
    structure_score: float
    content_score: float
    eeat_score: float
    schema_score: float
    overall_score: float


class AuditAnalytics(BaseModel):
    """Analytics de auditoría"""

    audit_id: int
    domain: str
    total_pages: int
    issues_by_category: List[IssueSummary]
    average_scores: ScoreSummary
    top_issues: List[Dict[str, Any]]


class CompetitorAnalysis(BaseModel):
    """Análisis competitivo"""

    audit_id: int
    total_competitors: int
    competitors: List[Dict[str, Any]]
    your_geo_score: float
    average_competitor_score: float
    gaps: List[str]


# ===== PDF GENERATION SCHEMAS =====


class PDFRequest(BaseModel):
    """Request para generar PDF"""

    audit_id: int
    include_competitor_analysis: bool = False
    include_raw_data: bool = False


class PDFResponse(BaseModel):
    """Response de PDF"""

    task_id: str
    audit_id: int
    status: AuditStatusEnum
    file_url: Optional[str]


# ===== HEALTH SCHEMAS =====


class HealthResponse(BaseModel):
    """Response de health check"""

    status: str
    version: str
    database: str
    redis: str


# ===== PAGINATION SCHEMAS =====


class PaginationParams(BaseModel):
    """Parámetros de paginación"""

    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


class PaginatedResponse(BaseModel):
    """Response paginado genérico"""

    total: int
    page: int
    page_size: int
    pages: int
    data: List[Any]
