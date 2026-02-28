"""
Script para inicializar la base de datos de Supabase.
Crea todas las tablas definidas en los modelos SQLAlchemy.
"""

import logging
import sys
import os

# Añadir directorio padre para imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.core.database import Base, engine
# Importar todos los modelos para que Base.metadata los reconozca
from app.models import (
    Audit, Report, AuditedPage, CrawlJob, Competitor, Backlink, Keyword, 
    RankTracking, LLMVisibility, AIContentSuggestion, GeoCommerceCampaign,
    GeoArticleBatch, CitationTracking, DiscoveredQuery, CompetitorCitationAnalysis,
    ScoreHistory, GitHubConnection, GitHubRepository, GitHubPullRequest,
    GitHubWebhookEvent, HubSpotConnection, HubSpotPage, HubSpotChange
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("init_supabase_db")

def main():
    if not settings.DATABASE_URL:
        logger.error("DATABASE_URL no configurada.")
        sys.exit(1)
        
    if "supabase" not in settings.DATABASE_URL and "postgresql" not in settings.DATABASE_URL:
        logger.warning("La URL de base de datos no parece ser de PostgreSQL/Supabase.")

    logger.info(f"Conectando a base de datos: {settings.DATABASE_URL.split('@')[-1]}") # Log seguro

    try:
        # Crear tablas
        logger.info("Creando tablas en la base de datos...")
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Tablas creadas exitosamente.")
        
    except Exception as e:
        logger.error(f"❌ Error inicializando base de datos: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
