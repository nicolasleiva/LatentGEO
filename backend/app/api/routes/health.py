"""
Health Check Endpoint - Para load balancers y monitoring
"""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

from ...core.database import get_db
from ...core.logger import get_logger
from ...services.cache_service import cache

logger = get_logger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
@router.get("/api/health", include_in_schema=False)
async def health_check(db: Session = Depends(get_db)):
    """
    Health check endpoint para load balancers.
    Retorna 200 si todos los servicios están operativos.
    """
    health_status = {"status": "healthy", "services": {}}

    # Check database
    try:
        db.execute(text("SELECT 1"))
        health_status["services"]["database"] = "connected"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        health_status["services"]["database"] = "disconnected"
        health_status["status"] = "unhealthy"

    # Check Redis
    try:
        if cache.enabled:
            cache.redis_client.ping()
            health_status["services"]["redis"] = "connected"
        else:
            health_status["services"]["redis"] = "disabled"
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        health_status["services"]["redis"] = "disconnected"
        if health_status["status"] == "healthy":
            health_status["status"] = "degraded"

    status_code = 503 if health_status["status"] == "unhealthy" else 200
    return JSONResponse(status_code=status_code, content=health_status)


@router.get("/health/ready")
@router.get("/api/health/ready", include_in_schema=False)
async def readiness_check(db: Session = Depends(get_db)):
    """
    Readiness check - verifica si la app puede recibir tráfico.
    """
    try:
        db.execute(text("SELECT 1"))
        return JSONResponse(status_code=200, content={"status": "ready"})
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return JSONResponse(
            status_code=503, content={"status": "not_ready", "error": str(e)}
        )


@router.get("/health/live")
@router.get("/api/health/live", include_in_schema=False)
async def liveness_check():
    """
    Liveness check - verifica si la app está viva (no colgada).
    """
    return {"status": "alive"}
