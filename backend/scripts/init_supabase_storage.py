"""
Script para inicializar recursos de Supabase (Buckets)
Se ejecuta manualmente o al inicio del contenedor.
"""

import logging
import sys
import os

# Añadir directorio padre para imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.services.supabase_service import SupabaseService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("init_supabase")

def main():
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        logger.error("Faltan credenciales de Supabase en .env")
        sys.exit(1)

    logger.info("Iniciando configuración de Supabase Storage...")
    
    bucket_name = settings.SUPABASE_STORAGE_BUCKET
    try:
        # Intentar crear bucket privado para reportes
        SupabaseService.ensure_bucket_exists(bucket_name, public=False)
        logger.info("✅ Bucket de almacenamiento configurado correctamente.")
    except Exception as e:
        logger.error(f"❌ Fallo configurando bucket: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
