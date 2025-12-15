"""
Servicio para rank tracking.
Genera datos de posicionamiento basados en keywords.
"""
import logging
from typing import List, Dict, Any
import random

logger = logging.getLogger(__name__)


class RankTrackingService:
    """Servicio para generar datos de rank tracking."""
    
    @staticmethod
    def generate_rankings_from_keywords(keywords: List[Dict[str, Any]], url: str) -> List[Dict[str, Any]]:
        """
        Genera datos de rank tracking basados en keywords.
        
        Args:
            keywords: Lista de keywords generadas
            url: URL del sitio
            
        Returns:
            Lista de rankings con cambios
        """
        try:
            logger.info(f"Generating rank tracking for {url}")
            
            rankings = []
            
            for kw in keywords:
                keyword = kw.get("keyword", "")
                current_position = kw.get("current_rank", random.randint(1, 50))
                
                # Simular cambio de posición (mejora o empeora)
                previous_position = current_position + random.randint(-5, 5)
                if previous_position < 1:
                    previous_position = current_position + 2
                if previous_position > 100:
                    previous_position = current_position - 2
                
                change = current_position - previous_position
                
                rankings.append({
                    "keyword": keyword,
                    "position": current_position,
                    "url": url,
                    "search_engine": "google",
                    "location": "US",
                    "device": "desktop",
                    "previous_position": previous_position,
                    "change": change
                })
            
            logger.info(f"Generated {len(rankings)} rankings for {url}")
            return rankings
            
        except Exception as e:
            logger.error(f"Error generating rankings: {e}")
            return []
