"""
Score History API Routes - Tracking histórico y comparativas temporales
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime

from ..core.database import get_db
from ..services.score_history_service import ScoreHistoryService

router = APIRouter(prefix="/api/score-history", tags=["Score History"])


@router.get("/domain/{domain}")
async def get_domain_history(
    domain: str,
    days: int = Query(default=90, ge=7, le=365),
    user_email: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Obtiene el historial de scores para un dominio específico.
    
    - **domain**: Dominio a consultar (ej: example.com)
    - **days**: Cantidad de días de historial (default: 90)
    - **user_email**: Filtrar por usuario (opcional)
    """
    history = ScoreHistoryService.get_history(
        db=db,
        domain=domain,
        days=days,
        user_id=user_email
    )
    
    return {
        "domain": domain,
        "days": days,
        "total_records": len(history),
        "history": [
            {
                "id": h.id,
                "recorded_at": h.recorded_at.isoformat(),
                "overall_score": h.overall_score,
                "seo_score": h.seo_score,
                "geo_score": h.geo_score,
                "performance_score": h.performance_score,
                "accessibility_score": h.accessibility_score,
                "lcp": h.lcp,
                "cls": h.cls,
                "critical_issues": h.critical_issues,
                "high_issues": h.high_issues,
                "total_pages": h.total_pages,
                "citation_rate": h.citation_rate,
                "audit_id": h.audit_id
            }
            for h in history
        ]
    }


@router.get("/domain/{domain}/comparison")
async def get_monthly_comparison(
    domain: str,
    user_email: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Compara los scores del mes actual vs el mes anterior.
    
    Retorna:
    - Promedio de cada métrica para ambos meses
    - Diferencia absoluta y porcentual
    - Tendencia (up/down/stable)
    """
    comparison = ScoreHistoryService.get_monthly_comparison(
        db=db,
        domain=domain,
        user_id=user_email
    )
    
    return comparison


@router.get("/summary")
async def get_domains_summary(
    user_email: Optional[str] = None,
    days: int = Query(default=30, ge=7, le=90),
    db: Session = Depends(get_db)
):
    """
    Obtiene un resumen de todos los dominios auditados.
    
    Útil para dashboards que muestran múltiples sitios.
    """
    summary = ScoreHistoryService.get_all_domains_summary(
        db=db,
        user_id=user_email,
        days=days
    )
    
    return {
        "days": days,
        "domains": summary
    }


@router.post("/record")
async def record_score_manually(
    domain: str,
    audit_id: int,
    overall_score: float = 0,
    seo_score: float = 0,
    geo_score: float = 0,
    performance_score: float = 0,
    user_email: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Registra manualmente un score en el historial.
    
    Normalmente se llama automáticamente cuando una auditoría se completa.
    """
    scores = {
        "overall_score": overall_score,
        "seo_score": seo_score,
        "geo_score": geo_score,
        "performance_score": performance_score,
    }
    
    entry = ScoreHistoryService.record_score(
        db=db,
        domain=domain,
        audit_id=audit_id,
        scores=scores,
        user_id=user_email
    )
    
    return {
        "success": True,
        "id": entry.id,
        "domain": domain,
        "recorded_at": entry.recorded_at.isoformat()
    }
