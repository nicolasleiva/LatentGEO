"""
API Endpoints para PDF y Reportes
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from ...core.access_control import ensure_audit_access
from ...core.auth import AuthUser, get_current_user
from ...core.database import get_db
from ...core.logger import get_logger
from ...models import AuditStatus
from ...schemas import PDFRequest, ReportResponse
from ...services.audit_service import AuditService, ReportService

logger = get_logger(__name__)

router = APIRouter(
    prefix="/reports",
    tags=["reports"],
    responses={404: {"description": "No encontrado"}},
)


def _get_owned_audit(db: Session, audit_id: int, current_user: AuthUser):
    audit = AuditService.get_audit(db, audit_id)
    return ensure_audit_access(audit, current_user)


@router.get("/audit/{audit_id}", response_model=dict)
async def get_audit_reports(
    audit_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """Obtener todos los reportes de una auditoría"""
    try:
        _get_owned_audit(db, audit_id, current_user)

        reports = ReportService.get_reports_by_audit(db, audit_id)
        return {
            "audit_id": audit_id,
            "total_reports": len(reports),
            "reports": [ReportResponse.from_orm(r) for r in reports],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo reportes: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error obteniendo reportes",
        )


@router.post(
    "/generate-pdf", response_model=None, status_code=status.HTTP_307_TEMPORARY_REDIRECT
)
async def generate_pdf(
    pdf_request: PDFRequest,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """
    Deprecated legacy endpoint.
    Use `POST /api/v1/audits/{audit_id}/generate-pdf` instead.
    """
    try:
        audit = _get_owned_audit(db, pdf_request.audit_id, current_user)
        redirect_to = f"/api/v1/audits/{audit.id}/generate-pdf"
        logger.warning(
            "Deprecated endpoint /api/v1/reports/generate-pdf invoked for audit %s. Redirecting to %s",
            audit.id,
            redirect_to,
        )
        return RedirectResponse(
            url=redirect_to,
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={
                "X-Deprecated-Endpoint": "/api/v1/reports/generate-pdf",
                "X-Replacement-Endpoint": redirect_to,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error redirecting deprecated PDF endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error redirecting deprecated endpoint",
        )


@router.get("/download/{report_id}")
async def download_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """Descargar archivo de reporte"""
    try:
        report = ReportService.get_report(db, report_id)
        if not report or not report.file_path:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Reporte no encontrado"
            )

        _get_owned_audit(db, report.audit_id, current_user)

        if not report.file_path.startswith("supabase://"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Legacy local report paths are disabled in Supabase-only mode. "
                    "Regenera el reporte para moverlo a Supabase."
                ),
            )

        from ...core.config import settings
        from ...services.supabase_service import SupabaseService

        storage_path = report.file_path.replace("supabase://", "", 1)
        try:
            signed_url = SupabaseService.get_signed_url(
                bucket=settings.SUPABASE_STORAGE_BUCKET,
                path=storage_path,
            )
            return RedirectResponse(url=signed_url, status_code=302)
        except Exception as e:
            logger.error(f"Error generating Supabase URL: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error retrieving file from cloud storage",
            ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error descargando reporte: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error descargando reporte",
        )


@router.get("/markdown/{audit_id}")
async def get_markdown_report(
    audit_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """Obtener reporte en formato Markdown"""
    try:
        audit = _get_owned_audit(db, audit_id, current_user)

        if audit.status != AuditStatus.COMPLETED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El reporte aún no está listo.",
            )
        if not audit.report_markdown:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report not generated. Generate PDF first.",
            )

        return JSONResponse(
            content={
                "audit_id": audit_id,
                "markdown": audit.report_markdown,
                "created_at": (
                    audit.completed_at.isoformat() if audit.completed_at else None
                ),
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo markdown: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error obteniendo reporte",
        )


@router.get("/json/{audit_id}")
async def get_json_report(
    audit_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """Obtener reporte en formato JSON"""
    try:
        audit = _get_owned_audit(db, audit_id, current_user)

        return {
            "audit_id": audit_id,
            "url": audit.url,
            "domain": audit.domain,
            "status": audit.status.value,
            "is_ymyl": audit.is_ymyl,
            "category": audit.category,
            "target_audit": audit.target_audit,
            "external_intelligence": audit.external_intelligence,
            "search_results": audit.search_results,
            "fix_plan": audit.fix_plan,
            "created_at": audit.created_at,
            "completed_at": audit.completed_at,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo JSON: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error obteniendo reporte",
        )
