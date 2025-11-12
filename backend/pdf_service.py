"""
Servicio para la generación de reportes en PDF.
"""
import os
from datetime import datetime

from backend.app.core.logger import get_logger
from backend.app.core.config import settings
from backend.app.models import Audit

# Asumimos que create_pdf.py está en una ruta importable o ha sido refactorizado.
# Si create_pdf.py está en la raíz, necesitarás ajustar el path.
# Por ahora, lo importamos asumiendo que está accesible.
from create_pdf import PDFReport # Nota: Para una solución robusta, esta clase debería estar dentro del paquete 'app'.

logger = get_logger(__name__)


class PDFService:
    """Encapsula la lógica para crear archivos PDF a partir de contenido."""

    @staticmethod
    def create_from_audit(audit: Audit, markdown_content: str) -> str:
        """
        Crea un reporte PDF para una auditoría específica.

        Args:
            audit: La instancia del modelo Audit.
            markdown_content: El contenido del reporte en formato Markdown.

        Returns:
            La ruta completa al archivo PDF generado.
        """
        logger.info(f"Iniciando generación de PDF para auditoría {audit.id}")

        reports_dir = os.path.join(settings.REPORTS_BASE_DIR, str(audit.id))
        os.makedirs(reports_dir, exist_ok=True)

        pdf_file_name = f"audit_report_{audit.id}.pdf"
        pdf_file_path = os.path.join(reports_dir, pdf_file_name)

        pdf = PDFReport()
        pdf.create_cover_page(
            title=f"Audit Report for {audit.url}",
            url=str(audit.url),
            date_str=audit.completed_at.strftime("%Y-%m-%d") if audit.completed_at else datetime.now().strftime("%Y-%m-%d"),
        )
        pdf.add_page()
        pdf.write_markdown_text(markdown_content)
        pdf.output(pdf_file_path)

        logger.info(f"Reporte PDF guardado en: {pdf_file_path}")
        return pdf_file_path