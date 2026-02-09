"""
Servicio para análisis de palabras clave.
Genera keywords basadas en el contenido del sitio auditado.
"""
import logging
from app.core.config import settings
from typing import List, Dict, Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class KeywordsService:
    """Servicio para generar análisis de palabras clave."""
    
    @staticmethod
    def generate_keywords_from_audit(target_audit: Dict[str, Any], url: str) -> List[Dict[str, Any]]:
        """
        Genera keywords basadas en el análisis del sitio.
        
        Args:
            target_audit: Datos de la auditoría técnica
            url: URL del sitio
            
        Returns:
            Lista de keywords con métricas
        """
        if settings.ENVIRONMENT == "production" or settings.STRICT_CONFIG:
            raise RuntimeError("KeywordsService is a stub in production. Use KeywordService.")
        try:
            logger.info(f"Generating keywords for {url}")
            
            # Extraer dominio y categoría
            domain = urlparse(url).netloc.replace('www.', '')
            
            # Extraer H1s y títulos del sitio
            h1_examples = []
            if isinstance(target_audit, dict):
                structure = target_audit.get('structure', {})
                h1_check = structure.get('h1_check', {})
                h1_details = h1_check.get('details', {})
                h1_example = h1_details.get('example', '')
                if h1_example:
                    h1_examples.append(h1_example)
            
            # No inventar más datos de ejemplo para evitar confusión con datos reales
            keywords = []
            
            logger.info(f"Generated {len(keywords)} keywords for {url}")
            return keywords
            
        except Exception as e:
            logger.error(f"Error generating keywords: {e}")
            return []
