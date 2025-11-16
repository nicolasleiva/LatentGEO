"""
Servicio para la generación de reportes en PDF.
"""
import os
import sys
import json
from datetime import datetime

from ..core.config import settings
from ..core.logger import get_logger
from ..models import Audit

logger = get_logger(__name__)

# Importar create_comprehensive_pdf desde el mismo directorio de servicios
try:
    from .create_pdf import create_comprehensive_pdf, FPDF_AVAILABLE
    PDF_GENERATOR_AVAILABLE = FPDF_AVAILABLE
except ImportError as e:
    logger.warning(f"No se pudo importar create_comprehensive_pdf: {e}. PDFs no estarán disponibles.")
    PDF_GENERATOR_AVAILABLE = False
    
    def create_comprehensive_pdf(report_folder_path):
        logger.error("create_comprehensive_pdf no está disponible")
        raise ImportError("create_pdf module not available")


class PDFService:
    """Encapsula la lógica para crear archivos PDF a partir de contenido."""

    @staticmethod
    def create_from_audit(audit: Audit, markdown_content: str) -> str:
        """
        Crea un reporte PDF completo para una auditoría específica.
        Usa create_comprehensive_pdf para generar el PDF con índice y anexos.

        Args:
            audit: La instancia del modelo Audit.
            markdown_content: El contenido del reporte en formato Markdown.

        Returns:
            La ruta completa al archivo PDF generado.
        """
        if not PDF_GENERATOR_AVAILABLE:
            logger.error("PDF generator no está disponible. Instalar fpdf2: pip install fpdf2")
            raise ImportError("PDF generator not available")
        
        logger.info(f"Iniciando generación de PDF para auditoría {audit.id}")

        reports_dir = os.path.join(settings.REPORTS_BASE_DIR, f"audit_{audit.id}")
        os.makedirs(reports_dir, exist_ok=True)

        # Guardar el markdown en ag2_report.md (requerido por create_comprehensive_pdf)
        md_file_path = os.path.join(reports_dir, "ag2_report.md")
        with open(md_file_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)
        
        # Guardar fix_plan.json si existe en audit.fix_plan
        if hasattr(audit, 'fix_plan') and audit.fix_plan:
            fix_plan_path = os.path.join(reports_dir, "fix_plan.json")
            try:
                fix_plan_data = json.loads(audit.fix_plan) if isinstance(audit.fix_plan, str) else audit.fix_plan
                with open(fix_plan_path, "w", encoding="utf-8") as f:
                    json.dump(fix_plan_data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.warning(f"No se pudo guardar fix_plan.json: {e}")
        
        # Guardar aggregated_summary.json si existe en audit.target_audit
        if hasattr(audit, 'target_audit') and audit.target_audit:
            agg_summary_path = os.path.join(reports_dir, "aggregated_summary.json")
            try:
                target_audit_data = json.loads(audit.target_audit) if isinstance(audit.target_audit, str) else audit.target_audit
                with open(agg_summary_path, "w", encoding="utf-8") as f:
                    json.dump(target_audit_data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.warning(f"No se pudo guardar aggregated_summary.json: {e}")
        
        # Llamar a create_comprehensive_pdf (igual que ag2_pipeline.py)
        try:
            create_comprehensive_pdf(reports_dir)
            
            # Buscar el PDF generado
            import glob
            pdf_files = glob.glob(os.path.join(reports_dir, "Reporte_Consolidado_*.pdf"))
            if pdf_files:
                pdf_file_path = pdf_files[0]
                logger.info(f"Reporte PDF guardado en: {pdf_file_path}")
                return pdf_file_path
            else:
                logger.error(f"No se encontró el PDF generado en {reports_dir}")
                raise FileNotFoundError("PDF file not generated")
        except Exception as e:
            logger.error(f"Error generando PDF con create_comprehensive_pdf: {e}", exc_info=True)
            raise