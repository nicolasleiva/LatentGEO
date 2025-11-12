"""
FastAPI Main Application
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.utils import get_openapi
import os

from .core.config import settings
from .core.database import create_all_tables
from .core.logger import get_logger

# Importar rutas
from .api.routes import audits, reports, analytics, health

from contextlib import asynccontextmanager


logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Context manager for the lifespan of the application."""
    logger.info(f"========================================")
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}...")
    logger.info(f"Debug mode: {settings.DEBUG}")
    logger.info(
        f"Database: {settings.DATABASE_URL.split('@')[-1].split('/')[0] if '@' in settings.DATABASE_URL else settings.DATABASE_URL}"
    )
    logger.info(f"API Documentation: http://localhost:8000/docs")
    logger.info(f"========================================")
    yield
    logger.info(f"========================================")
    logger.info(f"Shutting down {settings.APP_NAME}...")
    logger.info(f"========================================")


def create_app() -> FastAPI:
    """Factory para crear la aplicación FastAPI"""
    from starlette.middleware.gzip import GZipMiddleware as GZip

    app = FastAPI(
        title=settings.APP_NAME,
        description="Plataforma profesional de auditoría SEO/GEO con API modular y dashboard",
        version=settings.APP_VERSION,
        debug=settings.DEBUG,
        lifespan=lifespan,
        redirect_slashes=True,
    )

    # Crear tablas de base de datos
    create_all_tables()
    logger.info("Tablas de base de datos creadas/verificadas")

    # ===== MIDDLEWARE =====

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # GZIP
    # app.add_middleware(GZip, minimum_size=1000)

    logger.info(f"Middleware configurado")

    # ===== RUTAS =====

    # Health y utilidades
    app.include_router(health.router)

    # Auditorías
    app.include_router(audits.router, tags=["audits"])

    # Reportes
    app.include_router(reports.router)

    # Analytics
    app.include_router(analytics.router)

    logger.info("Rutas registradas")

    # ===== DOCUMENTACIÓN PERSONALIZADA =====

    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema

        openapi_schema = get_openapi(
            title=settings.APP_NAME,
            version=settings.APP_VERSION,
            description="API modular profesional para auditorías SEO/GEO",
            routes=app.routes,
        )

        openapi_schema["info"]["x-logo"] = {
            "url": "https://fastapi.tiangolo.com/img/logo-margin/logo-teal.png"
        }

        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = custom_openapi

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=settings.DEBUG)
