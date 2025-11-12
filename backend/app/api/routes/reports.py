"""
API Endpoints para PDF y Reportes
"""
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    BackgroundTasks,
)
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session
from pathlib import Path
import os, uuid, json
from app.models import AuditStatus
from ...core.database import get_db
from ...schemas import ReportResponse, PDFRequest, PDFResponse
from ...services.audit_service import AuditService, ReportService
from ...core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/reports",
    tags=["reports"],
    responses={404: {"description": "No encontrado"}},
)

# Importar la lógica de creación de PDF del script heredado
try:
    from create_pdf import create_comprehensive_pdf, FPDF_AVAILABLE
except ImportError:
    FPDF_AVAILABLE = False


@router.get("/audit/{audit_id}", response_model=dict)
async def get_audit_reports(audit_id: int, db: Session = Depends(get_db)):
    """Obtener todos los reportes de una auditoría"""
    try:
        audit = AuditService.get_audit(db, audit_id)
        if not audit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Auditoría no encontrada"
            )

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


async def generate_pdf_background(
    audit_id: int, report_dir: str, db: Session
):
    """
    Tarea en segundo plano para generar el PDF.
    """
    logger.info(f"Iniciando generación de PDF para auditoría {audit_id} en {report_dir}")
    try:
        audit = AuditService.get_audit(db, audit_id)
        if not audit:
            logger.error(f"Auditoría {audit_id} no encontrada para generar PDF.")
            return

        # 1. Guardar los datos de la BD en archivos temporales que create_pdf espera
        with open(os.path.join(report_dir, "ag2_report.md"), "w", encoding="utf-8") as f:
            f.write(audit.report_markdown or "# Reporte no disponible")
        with open(os.path.join(report_dir, "fix_plan.json"), "w", encoding="utf-8") as f:
            json.dump(audit.fix_plan or [], f, indent=2, ensure_ascii=False)
        with open(os.path.join(report_dir, "aggregated_summary.json"), "w", encoding="utf-8") as f:
            json.dump(audit.target_audit or {}, f, indent=2, ensure_ascii=False)

        # 2. Llamar a la función de creación de PDF
        if FPDF_AVAILABLE:
            create_comprehensive_pdf(report_dir)
            pdf_filename = f"Reporte_Consolidado_{os.path.basename(report_dir)}.pdf"
            pdf_path = os.path.join(report_dir, pdf_filename)
            if os.path.exists(pdf_path):
                logger.info(f"PDF generado exitosamente: {pdf_path}")
                # Aquí podrías actualizar la BD con la ruta del archivo
            else:
                logger.error(f"create_comprehensive_pdf no generó el archivo esperado.")
        else:
            logger.error("FPDF no está disponible. No se puede generar el PDF.")

    except Exception as e:
        logger.error(f"Error en la generación de PDF en segundo plano: {e}")


@router.post(
    "/generate-pdf", response_model=PDFResponse, status_code=status.HTTP_202_ACCEPTED
)
async def generate_pdf(
    pdf_request: PDFRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Generar PDF de auditoría (asincrónico)

    - **audit_id**: ID de la auditoría (requerido)
    - **include_competitor_analysis**: Incluir análisis competitivo (default: false)
    - **include_raw_data**: Incluir datos crudos (default: false)
    """
    if not FPDF_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="La funcionalidad de PDF no está disponible. Instala 'fpdf2'.",
        )

    try:
        audit = AuditService.get_audit(db, pdf_request.audit_id)
        if not audit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Auditoría no encontrada"
            )

        if audit.status != AuditStatus.completed or not audit.report_markdown:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La auditoría no está completada o no tiene reporte.",
            )

        # Crear un directorio único para los archivos de este reporte
        report_session_id = str(uuid.uuid4())
        report_dir = os.path.join("reports", audit.domain, report_session_id)
        os.makedirs(report_dir, exist_ok=True)

        # Añadir la tarea de generación de PDF al background
        background_tasks.add_task(
            generate_pdf_background,
            audit_id=audit.id,
            report_dir=report_dir,
            db=db,
        )

        return PDFResponse(
            task_id=report_session_id,
            audit_id=pdf_request.audit_id,
            status=AuditStatus.PENDING,
            # En un sistema real, aquí devolverías una URL para consultar el estado
            file_url=None,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generando PDF: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error generando PDF",
        )


@router.get("/download/{report_id}")
async def download_report(report_id: int, db: Session = Depends(get_db)):
    """Descargar archivo de reporte"""
    try:
        report = ReportService.get_report(db, report_id)
        if not report or not report.file_path:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Reporte no encontrado"
            )

        file_path = Path(report.file_path)
        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Archivo no encontrado"
            )

        return FileResponse(
            path=file_path,
            filename=file_path.name,
            media_type="application/octet-stream",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error descargando reporte: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error descargando reporte",
        )


@router.get("/markdown/{audit_id}")
async def get_markdown_report(audit_id: int, db: Session = Depends(get_db)):
    """Obtener reporte en formato Markdown"""
    try:
        audit = AuditService.get_audit(db, audit_id)
        if not audit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Auditoría no encontrada"
            )

        if audit.status != AuditStatus.completed or not audit.report_markdown:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El reporte aún no está listo.",
            )

        return JSONResponse(content={
            "audit_id": audit_id,
            "markdown": audit.report_markdown,
            "created_at": audit.completed_at,
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo markdown: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error obteniendo reporte",
        )


@router.get("/json/{audit_id}")
async def get_json_report(audit_id: int, db: Session = Depends(get_db)):
    """Obtener reporte en formato JSON"""
    try:
        audit = AuditService.get_audit(db, audit_id)
        if not audit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Auditoría no encontrada"
            )

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
