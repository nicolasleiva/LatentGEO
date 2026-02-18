"""
Punto de entrada principal para el backend.

Para ejecutar:
- Asegúrate de estar en el directorio raíz del proyecto.
- Ejecuta como un módulo: `python -m backend.main`
"""
import os
from contextlib import asynccontextmanager

import uvicorn
from app.core.config import settings
from app.core.logger import get_logger
from app.main import app as fastapi_app
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("========================================")
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}...")
    logger.info(f"Debug mode: {settings.DEBUG}")
    logger.info(f"Database URL: {settings.DATABASE_URL}")
    logger.info(f"API Documentation: http://localhost:8000/docs")
    logger.info("========================================")
    yield
    # Shutdown
    logger.info("========================================")
    logger.info(f"Shutting down {settings.APP_NAME}...")
    logger.info("========================================")


fastapi_app.router.lifespan_context = lifespan

if __name__ == "__main__":
    # Configuración por defecto
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    reload = os.getenv("DEBUG", "True") == "True"

    uvicorn.run(
        "main:fastapi_app", host=host, port=port, reload=reload, log_level="info"
    )
