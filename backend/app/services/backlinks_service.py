"""
Servicio para análisis de backlinks.
Genera backlinks de ejemplo basados en el perfil del sitio.
"""
import logging
from typing import Dict, Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class BacklinksService:
    """Servicio para generar análisis de backlinks."""
    
    @staticmethod
    def generate_backlinks_from_audit(target_audit: Dict[str, Any], url: str) -> Dict[str, Any]:
        """
        Genera análisis de backlinks basado en el sitio.
        
        Args:
            target_audit: Datos de la auditoría técnica
            url: URL del sitio
            
        Returns:
            Diccionario con análisis de backlinks
        """
        try:
            logger.info(f"Generating backlinks analysis for {url}")
            
            domain = urlparse(url).netloc.replace('www.', '')
            
            # No inventar más datos de ejemplo para evitar confusión con datos reales
            backlinks = []
            
            # Calcular métricas agregadas
            total_backlinks = len(backlinks)
            referring_domains = len(set(b["source_url"].split('/')[2] for b in backlinks))
            avg_da = sum(b["domain_authority"] for b in backlinks) / total_backlinks if total_backlinks > 0 else 0
            dofollow_count = len([b for b in backlinks if b["is_dofollow"]])
            nofollow_count = total_backlinks - dofollow_count
            
            result = {
                "total_backlinks": total_backlinks,
                "referring_domains": referring_domains,
                "top_backlinks": backlinks[:20],  # Top 20
                "summary": {
                    "average_domain_authority": round(avg_da, 1),
                    "dofollow_count": dofollow_count,
                    "nofollow_count": nofollow_count,
                    "high_authority_count": len([b for b in backlinks if b["domain_authority"] >= 80]),
                    "spam_score_avg": round(sum(b["spam_score"] for b in backlinks) / total_backlinks, 1) if total_backlinks > 0 else 0
                }
            }
            
            logger.info(f"Generated {total_backlinks} backlinks for {url}")
            return result
            
        except Exception as e:
            logger.error(f"Error generating backlinks: {e}")
            return {
                "total_backlinks": 0,
                "referring_domains": 0,
                "top_backlinks": []
            }
