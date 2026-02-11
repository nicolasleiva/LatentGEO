"""
Score History Service - Tracking histórico de scores
"""
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from ..models import ScoreHistory, Audit


class ScoreHistoryService:
    """Servicio para gestionar el historial de scores"""

    @staticmethod
    def _apply_owner_filter(query, owner_ids: Optional[List[str]]):
        """Aplica filtro de ownership para evitar mezcla de datos entre usuarios."""
        if owner_ids:
            normalized = [owner for owner in owner_ids if owner]
            if normalized:
                return query.filter(ScoreHistory.user_id.in_(normalized))
        return query
    
    @staticmethod
    def record_score(
        db: Session,
        domain: str,
        audit_id: int,
        scores: Dict[str, Any],
        user_id: Optional[str] = None
    ) -> ScoreHistory:
        """Registra un nuevo snapshot de scores para un dominio"""
        
        history_entry = ScoreHistory(
            domain=domain,
            user_id=user_id,
            audit_id=audit_id,
            overall_score=scores.get("overall_score", 0),
            seo_score=scores.get("seo_score", 0),
            geo_score=scores.get("geo_score", 0),
            performance_score=scores.get("performance_score", 0),
            accessibility_score=scores.get("accessibility_score", 0),
            best_practices_score=scores.get("best_practices_score", 0),
            lcp=scores.get("lcp"),
            fid=scores.get("fid"),
            cls=scores.get("cls"),
            critical_issues=scores.get("critical_issues", 0),
            high_issues=scores.get("high_issues", 0),
            medium_issues=scores.get("medium_issues", 0),
            low_issues=scores.get("low_issues", 0),
            total_pages=scores.get("total_pages", 0),
            citation_rate=scores.get("citation_rate", 0),
            llm_mentions=scores.get("llm_mentions", 0),
        )
        
        db.add(history_entry)
        db.commit()
        db.refresh(history_entry)
        
        return history_entry
    
    @staticmethod
    def get_history(
        db: Session,
        domain: str,
        days: int = 90,
        owner_ids: Optional[List[str]] = None,
    ) -> List[ScoreHistory]:
        """Obtiene el historial de scores para un dominio"""
        
        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        query = db.query(ScoreHistory).filter(
            ScoreHistory.domain == domain,
            ScoreHistory.recorded_at >= start_date
        )
        
        query = ScoreHistoryService._apply_owner_filter(query, owner_ids)
        
        return query.order_by(ScoreHistory.recorded_at.asc()).all()
    
    @staticmethod
    def get_monthly_comparison(
        db: Session,
        domain: str,
        owner_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Compara scores del mes actual vs el mes anterior"""
        
        now = datetime.now(timezone.utc)
        current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        previous_month_start = (current_month_start - timedelta(days=1)).replace(day=1)
        
        def get_month_avg(start: datetime, end: datetime) -> Dict[str, float]:
            query = db.query(
                func.avg(ScoreHistory.overall_score).label("overall_score"),
                func.avg(ScoreHistory.seo_score).label("seo_score"),
                func.avg(ScoreHistory.geo_score).label("geo_score"),
                func.avg(ScoreHistory.performance_score).label("performance_score"),
                func.avg(ScoreHistory.accessibility_score).label("accessibility_score"),
                func.avg(ScoreHistory.lcp).label("lcp"),
                func.avg(ScoreHistory.cls).label("cls"),
                func.sum(ScoreHistory.critical_issues).label("critical_issues"),
                func.sum(ScoreHistory.high_issues).label("high_issues"),
                func.count().label("audit_count")
            ).filter(
                ScoreHistory.domain == domain,
                ScoreHistory.recorded_at >= start,
                ScoreHistory.recorded_at < end
            )
            
            query = ScoreHistoryService._apply_owner_filter(query, owner_ids)
            
            result = query.first()
            
            return {
                "overall_score": round(result.overall_score or 0, 1),
                "seo_score": round(result.seo_score or 0, 1),
                "geo_score": round(result.geo_score or 0, 1),
                "performance_score": round(result.performance_score or 0, 1),
                "accessibility_score": round(result.accessibility_score or 0, 1),
                "lcp": round(result.lcp or 0, 0),
                "cls": round(result.cls or 0, 3),
                "critical_issues": int(result.critical_issues or 0),
                "high_issues": int(result.high_issues or 0),
                "audit_count": result.audit_count or 0
            }
        
        current_month = get_month_avg(current_month_start, now)
        previous_month = get_month_avg(previous_month_start, current_month_start)
        
        # Calcular diferencias
        def calc_diff(current: float, previous: float) -> Dict[str, Any]:
            if previous == 0:
                change_pct = 100 if current > 0 else 0
            else:
                change_pct = round(((current - previous) / previous) * 100, 1)
            
            return {
                "current": current,
                "previous": previous,
                "change": round(current - previous, 1),
                "change_pct": change_pct,
                "trend": "up" if current > previous else ("down" if current < previous else "stable")
            }
        
        return {
            "domain": domain,
            "current_month": current_month_start.strftime("%B %Y"),
            "previous_month": previous_month_start.strftime("%B %Y"),
            "comparison": {
                "overall_score": calc_diff(current_month["overall_score"], previous_month["overall_score"]),
                "seo_score": calc_diff(current_month["seo_score"], previous_month["seo_score"]),
                "geo_score": calc_diff(current_month["geo_score"], previous_month["geo_score"]),
                "performance_score": calc_diff(current_month["performance_score"], previous_month["performance_score"]),
                "lcp": calc_diff(current_month["lcp"], previous_month["lcp"]),
                "critical_issues": calc_diff(current_month["critical_issues"], previous_month["critical_issues"]),
                "audit_count": calc_diff(current_month["audit_count"], previous_month["audit_count"]),
            }
        }
    
    @staticmethod
    def get_all_domains_summary(
        db: Session,
        owner_ids: Optional[List[str]] = None,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """Obtiene un resumen de todos los dominios del usuario"""
        
        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        query = db.query(
            ScoreHistory.domain,
            func.avg(ScoreHistory.overall_score).label("avg_score"),
            func.count().label("audit_count"),
            func.max(ScoreHistory.recorded_at).label("last_audit")
        ).filter(
            ScoreHistory.recorded_at >= start_date
        )
        
        query = ScoreHistoryService._apply_owner_filter(query, owner_ids)
        
        results = query.group_by(ScoreHistory.domain).order_by(
            func.avg(ScoreHistory.overall_score).desc()
        ).limit(20).all()
        
        return [
            {
                "domain": r.domain,
                "avg_score": round(r.avg_score or 0, 1),
                "audit_count": r.audit_count,
                "last_audit": r.last_audit.isoformat() if r.last_audit else None
            }
            for r in results
        ]


# Función helper para extraer scores de un audit completado
def extract_scores_from_audit(audit: Audit) -> Dict[str, Any]:
    """Extrae scores de un audit completado para guardar en historial"""
    
    scores = {
        "overall_score": 0,
        "seo_score": 0,
        "geo_score": 0,
        "performance_score": 0,
        "accessibility_score": 0,
        "best_practices_score": 0,
        "critical_issues": audit.critical_issues or 0,
        "high_issues": audit.high_issues or 0,
        "medium_issues": audit.medium_issues or 0,
        "low_issues": audit.low_issues or 0,
        "total_pages": audit.total_pages or 0,
    }
    
    # Extract from target_audit if available
    if audit.target_audit:
        ta = audit.target_audit
        if isinstance(ta, dict):
            scores["seo_score"] = ta.get("seo_score", 0)
            scores["geo_score"] = ta.get("geo_score", 0)
            scores["overall_score"] = (scores["seo_score"] + scores["geo_score"]) / 2
    
    # Extract from pagespeed_data if available
    if audit.pagespeed_data:
        ps = audit.pagespeed_data
        if isinstance(ps, dict):
            mobile = ps.get("mobile", {})
            scores["performance_score"] = mobile.get("performance_score", 0)
            scores["accessibility_score"] = mobile.get("accessibility_score", 0)
            scores["best_practices_score"] = mobile.get("best_practices_score", 0)
            
            cwv = mobile.get("core_web_vitals", {})
            scores["lcp"] = cwv.get("lcp")
            scores["fid"] = cwv.get("fid")
            scores["cls"] = cwv.get("cls")
    
    return scores
