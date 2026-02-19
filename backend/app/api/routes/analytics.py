"""
API Endpoints para Analytics
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ...core.access_control import ensure_audit_access
from ...core.auth import AuthUser, get_current_user
from ...core.database import get_db
from ...core.logger import get_logger
from ...services.audit_service import AuditService, CompetitorService

logger = get_logger(__name__)

router = APIRouter(
    prefix="/analytics",
    tags=["analytics"],
    responses={404: {"description": "No encontrado"}},
)


def _get_owned_audit(db: Session, audit_id: int, current_user: AuthUser):
    audit = AuditService.get_audit(db, audit_id)
    return ensure_audit_access(audit, current_user)


@router.get("/audit/{audit_id}", response_model=dict)
async def get_audit_analytics(
    audit_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """Obtener análisis y estadísticas de auditoría"""
    try:
        audit = _get_owned_audit(db, audit_id, current_user)

        pages = AuditService.get_audited_pages(db, audit_id)

        # Calcular promedios de puntuaciones
        if pages:
            avg_h1 = sum(p.h1_score for p in pages) / len(pages)
            avg_structure = sum(p.structure_score for p in pages) / len(pages)
            avg_content = sum(p.content_score for p in pages) / len(pages)
            avg_eeat = sum(p.eeat_score for p in pages) / len(pages)
            avg_schema = sum(p.schema_score for p in pages) / len(pages)
            avg_overall = sum(p.overall_score for p in pages) / len(pages)
        else:
            avg_h1 = avg_structure = avg_content = avg_eeat = avg_schema = (
                avg_overall
            ) = 0

        return {
            "audit_id": audit_id,
            "domain": audit.domain,
            "total_pages": audit.total_pages,
            "is_ymyl": audit.is_ymyl,
            "category": audit.category,
            "issues": {
                "critical": audit.critical_issues,
                "high": audit.high_issues,
                "medium": audit.medium_issues,
                "low": audit.low_issues,
                "total": audit.critical_issues
                + audit.high_issues
                + audit.medium_issues
                + audit.low_issues,
            },
            "scores": {
                "h1_score": round(avg_h1, 2),
                "structure_score": round(avg_structure, 2),
                "content_score": round(avg_content, 2),
                "eeat_score": round(avg_eeat, 2),
                "schema_score": round(avg_schema, 2),
                "overall_score": round(avg_overall, 2),
            },
            "pages": [
                {
                    "url": p.url,
                    "path": p.path,
                    "overall_score": p.overall_score,
                    "issues": {
                        "critical": p.critical_issues,
                        "high": p.high_issues,
                        "medium": p.medium_issues,
                        "low": p.low_issues,
                    },
                }
                for p in pages
            ],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo análisis: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error obteniendo análisis",
        )


@router.get("/competitors/{audit_id}", response_model=dict)
async def get_competitor_analysis(
    audit_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """Obtener análisis competitivo"""
    try:
        audit = _get_owned_audit(db, audit_id, current_user)

        competitors = CompetitorService.get_competitors(db, audit_id)

        # Calcular GEO score del cliente (basado en fix_plan)
        client_geo_score = 0
        if audit.fix_plan:
            total_issues = len(audit.fix_plan)
            critical = len(
                [f for f in audit.fix_plan if f.get("priority") == "CRITICAL"]
            )
            high = len([f for f in audit.fix_plan if f.get("priority") == "HIGH"])

            # Fórmula simple: 10 - (críticos * 2 + altos * 1) / max(1, total_issues)
            client_geo_score = max(
                1, 10 - ((critical * 2 + high * 1) / max(1, total_issues))
            )

        competitor_scores = [c.geo_score for c in competitors]
        avg_competitor_score = (
            sum(competitor_scores) / len(competitor_scores) if competitor_scores else 0
        )

        # Identificar gaps
        gaps = []
        if competitors:
            for comp in competitors[:3]:  # Top 3 competidores
                if comp.audit_data and comp.audit_data.get("schema_types"):
                    client_schemas = (
                        audit.target_audit.get("schema", {}).get("schema_types", [])
                        if audit.target_audit
                        else []
                    )
                    comp_schemas = comp.audit_data.get("schema_types", [])
                    missing_schemas = set(comp_schemas) - set(client_schemas)
                    if missing_schemas:
                        gaps.append(f"Schema faltante: {', '.join(missing_schemas)}")

        return {
            "audit_id": audit_id,
            "total_competitors": len(competitors),
            "your_geo_score": round(client_geo_score, 2),
            "average_competitor_score": round(avg_competitor_score, 2),
            "position": (
                "Por encima del promedio"
                if client_geo_score > avg_competitor_score
                else "Por debajo del promedio"
            ),
            "competitors": [
                {"domain": c.domain, "url": c.url, "geo_score": c.geo_score}
                for c in sorted(competitors, key=lambda x: x.geo_score, reverse=True)
            ],
            "identified_gaps": gaps[:5],  # Top 5 gaps
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo análisis competitivo: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error obteniendo análisis",
        )


@router.get("/dashboard", response_model=dict)
async def get_dashboard_data(
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """Obtener datos para dashboard principal"""
    try:
        from ...models import AuditStatus

        # Estadísticas generales
        user_filters = {
            "user_email": current_user.email,
            "user_id": current_user.user_id,
        }
        completed = len(
            AuditService.get_audits_by_status(db, AuditStatus.COMPLETED, **user_filters)
        )
        running = len(
            AuditService.get_audits_by_status(db, AuditStatus.RUNNING, **user_filters)
        )
        failed = len(
            AuditService.get_audits_by_status(db, AuditStatus.FAILED, **user_filters)
        )
        pending = len(
            AuditService.get_audits_by_status(db, AuditStatus.PENDING, **user_filters)
        )
        total_audits = completed + running + failed + pending

        # Auditorías recientes
        recent_audits = AuditService.get_audits(db, skip=0, limit=10, **user_filters)

        # Dominios únicos
        unique_domains = len(set(audit.domain for audit in recent_audits))

        # Issues totales
        total_issues = sum(
            audit.critical_issues
            + audit.high_issues
            + audit.medium_issues
            + audit.low_issues
            for audit in recent_audits
        )

        return {
            "summary": {
                "total_audits": total_audits,
                "completed_audits": completed,
                "running_audits": running + pending,
                "failed_audits": failed,
                "success_rate": round((completed / max(1, total_audits)) * 100, 2),
            },
            "recent_audits": [
                {
                    "id": audit.id,
                    "url": audit.url,
                    "domain": audit.domain,
                    "status": audit.status.value,
                    "progress": audit.progress,
                    "total_pages": audit.total_pages,
                    "issues": {
                        "critical": audit.critical_issues,
                        "high": audit.high_issues,
                        "medium": audit.medium_issues,
                        "low": audit.low_issues,
                    },
                    "created_at": audit.created_at.isoformat(),
                }
                for audit in recent_audits
            ],
            "metrics": {
                "unique_domains": unique_domains,
                "total_issues": total_issues,
                "average_issues_per_audit": round(
                    total_issues / max(1, len(recent_audits)), 2
                ),
            },
        }
    except Exception as e:
        logger.error(f"Error obteniendo dashboard: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error obteniendo datos del dashboard",
        )


@router.get("/issues/{audit_id}", response_model=dict)
async def get_issues_by_priority(
    audit_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """Obtener issues agrupados por prioridad"""
    try:
        audit = _get_owned_audit(db, audit_id, current_user)
        if not audit or not audit.fix_plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Auditoría o plan de acción no encontrado",
            )

        fix_plan = audit.fix_plan if isinstance(audit.fix_plan, list) else []

        by_priority = {"CRITICAL": [], "HIGH": [], "MEDIUM": [], "LOW": []}

        for issue in fix_plan:
            priority = issue.get("priority", "MEDIUM")
            if priority in by_priority:
                by_priority[priority].append(
                    {
                        "page_path": issue.get("page_path"),
                        "issue_code": issue.get("issue_code"),
                        "description": issue.get("description"),
                        "suggestion": issue.get("suggestion"),
                    }
                )

        return {
            "audit_id": audit_id,
            "total_issues": len(fix_plan),
            "by_priority": by_priority,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo issues: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error obteniendo issues",
        )
