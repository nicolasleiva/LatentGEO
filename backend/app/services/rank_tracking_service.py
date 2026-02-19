"""
Servicio para rank tracking.
Genera datos de posicionamiento basados en keywords.
"""

import logging
from typing import Any, Dict, List

from app.core.config import settings

logger = logging.getLogger(__name__)


class RankTrackingService:
    """Servicio para generar datos de rank tracking."""

    @staticmethod
    def generate_rankings_from_keywords(
        keywords: List[Dict[str, Any]], url: str
    ) -> List[Dict[str, Any]]:
        """
        Genera datos de rank tracking basados en keywords.

        Args:
            keywords: Lista de keywords generadas
            url: URL del sitio

        Returns:
            Lista de rankings con cambios
        """
        if settings.ENVIRONMENT == "production" or settings.STRICT_CONFIG:
            raise RuntimeError(
                "RankTrackingService is a stub in production. Use RankTrackerService."
            )
        try:
            logger.info(f"Generating rank tracking for {url}")

            # No inventar más datos de ejemplo para evitar confusión con datos reales
            rankings = []

            logger.info(f"Generated {len(rankings)} rankings for {url}")
            return rankings

        except Exception as e:
            logger.error(f"Error generating rankings: {e}")
            return []
