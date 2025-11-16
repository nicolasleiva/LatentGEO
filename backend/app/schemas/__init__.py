from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class AuditStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class AuditCreate(BaseModel):
    url: HttpUrl
    max_pages: Optional[int] = 100
    language: Optional[str] = "es"  # "en" o "es"
    competitors: Optional[List[str]] = None  # URLs de competidores
    market: Optional[str] = None  # "us", "latam", "emea", "argentina", etc.

class AuditResponse(BaseModel):
    id: int
    url: str
    status: str
    progress: int
    created_at: datetime
    target_audit: Optional[Dict[str, Any]] = None
    external_intelligence: Optional[Dict[str, Any]] = None
    competitor_audits: Optional[List[Dict[str, Any]]] = None
    fix_plan: Optional[List[Dict[str, Any]]] = None
    report_markdown: Optional[str] = None
    total_pages: Optional[int] = None
    critical_issues: Optional[int] = None
    high_issues: Optional[int] = None
    medium_issues: Optional[int] = None
    pagespeed_data: Optional[Dict[str, Any]] = None
    language: Optional[str] = None
    competitors: Optional[List[str]] = None
    market: Optional[str] = None
    
    class Config:
        from_attributes = True

class AuditSummary(BaseModel):
    id: int
    url: str
    status: str
    progress: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class AuditDetail(BaseModel):
    id: int
    url: str
    status: str
    progress: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    target_audit: Optional[Dict[str, Any]] = None
    report_markdown: Optional[str] = None
    fix_plan: Optional[List[Dict[str, Any]]] = None
    
    class Config:
        from_attributes = True

class ReportResponse(BaseModel):
    id: int
    audit_id: int
    report_type: str
    file_path: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class PDFRequest(BaseModel):
    audit_id: int

class PDFResponse(BaseModel):
    success: bool
    file_path: Optional[str] = None
    message: str

class AuditAnalytics(BaseModel):
    total_audits: int
    completed: int
    running: int
    failed: int
    success_rate: float

class CompetitorAnalysis(BaseModel):
    url: str
    domain: str
    geo_score: float
    audit_data: Dict[str, Any]

class AuditConfigRequest(BaseModel):
    """Request para configurar auditoría con chat"""
    audit_id: int
    language: Optional[str] = None
    competitors: Optional[List[str]] = None
    market: Optional[str] = None

class ChatMessage(BaseModel):
    """Mensaje de chat"""
    role: str  # "user" o "assistant"
    content: str
    options: Optional[List[str]] = None  # Opciones de respuesta
