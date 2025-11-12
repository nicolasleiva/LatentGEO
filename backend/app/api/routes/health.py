"""
API Endpoints para Health Check y Utilidades
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text

from ...core.database import get_db
from ...core.config import settings
from ...core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(
    tags=["health"],
)


@router.get("/health", response_model=dict)
async def health_check(db: Session = Depends(get_db)):
    """Health check de la aplicación"""
    try:
        # Verificar base de datos
        db_status = "down"
        try:
            db.execute(text("SELECT 1"))
            db_status = "ok"
        except Exception as e:
            logger.error(f"DB health check falló: {e}")
            db_status = "error"

        # Verificar Redis (opcional)
        redis_status = "not-configured"
        try:
            import redis

            r = redis.from_url(settings.REDIS_URL, decode_responses=True)
            r.ping()
            redis_status = "ok"
        except Exception as e:
            logger.debug(f"Redis no disponible: {e}")
            redis_status = "unavailable"

        return {
            "status": "ok" if db_status == "ok" else "degraded",
            "version": settings.APP_VERSION,
            "database": db_status,
            "redis": redis_status,
            "api_name": settings.APP_NAME,
        }
    except Exception as e:
        logger.exception(f"Health check falló: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service unavailable",
        )


@router.get("/config", response_model=dict)
async def get_config():
    """Obtener configuración pública de la aplicación"""
    return {
        "app_name": settings.APP_NAME,
        "app_version": settings.APP_VERSION,
        "debug": settings.DEBUG,
        "max_crawl_default": settings.MAX_CRAWL_DEFAULT,
        "max_audit_default": settings.MAX_AUDIT_DEFAULT,
        "default_page_size": settings.DEFAULT_PAGE_SIZE,
        "max_page_size": settings.MAX_PAGE_SIZE,
    }


@router.get("/info", response_model=dict)
async def get_info():
    """Información de la API"""
    return {
        "title": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "description": "API profesional para auditorías SEO/GEO con arquitectura modular",
        "documentation": "/docs",
        "endpoints": {
            "audits": "/audits",
            "reports": "/reports",
            "analytics": "/analytics",
            "crawler": "/crawler",
        },
    }
