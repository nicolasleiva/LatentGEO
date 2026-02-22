"""
FastAPI Main Application - Production Ready (Level 2/3)
"""

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from .core.config import settings
from .core.database import init_db
from .core.logger import get_logger
from .core.middleware import configure_security_middleware

# Import rate limiting
try:
    from .middleware.rate_limit import RateLimitMiddleware

    RATE_LIMIT_AVAILABLE = True
except ImportError:
    RATE_LIMIT_AVAILABLE = False
    logger = get_logger(__name__)
    logger.warning("Rate limiting middleware not available")

# Initialize Monitoring (Level 2/3)
if settings.SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration

        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            integrations=[FastApiIntegration()],
            traces_sample_rate=1.0,
            profiles_sample_rate=1.0,
            environment=settings.ENVIRONMENT,
        )
    except ImportError:
        pass

# Import routes - the __init__.py handles missing dependencies gracefully
from .api.routes import (
    ai_content,
    analytics,
    audits,
    backlinks,
    content_analysis,
    content_editor,
    geo,
    github,
    health,
    hubspot,
    keywords,
    llm_visibility,
    pagespeed,
    rank_tracking,
    realtime,
    reports,
    search,
    sse,
    webhooks,
)

try:
    from .routes import score_history
except Exception:
    score_history = None

from contextlib import asynccontextmanager

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Control de ciclo de vida de la aplicación."""
    logger.info("=" * 40)
    logger.info(f"STARTUP: {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info("=" * 40)

    from .core.config import validate_environment

    try:
        validate_environment()
        logger.info("OK: Validacion de entorno exitosa")
    except Exception as e:
        logger.error(f"WARN: Advertencia de validacion: {e}")

    try:
        await init_db()
        logger.info("OK: Conexion con Base de Datos establecida")
    except Exception as e:
        logger.critical(f"ERR: Fallo critico al inicializar la base de datos: {e}")

    logger.info(f"INFO: Modo Debug: {settings.DEBUG}")
    logger.info("INFO: Documentacion: http://localhost:8000/docs")

    yield

    logger.info("=" * 40)
    logger.info(f"🛑 Apagando {settings.APP_NAME}...")
    logger.info("=" * 40)


def create_app() -> FastAPI:
    """Factory para crear la aplicación FastAPI - Level 3"""

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        debug=settings.DEBUG,
        lifespan=lifespan,
    )

    # ===== MIDDLEWARE =====
    # ===== MIDDLEWARE =====
    # Always send explicit origins to support credentials (cookies/auth)
    # We avoid "*" even in DEBUG because it conflicts with allow_credentials=True

    # Ensure localhost and defaults are included
    cors_origins = set(settings.CORS_ORIGINS)
    cors_origins.add("http://frontend:3000")
    cors_origins.add("http://localhost:3000")
    cors_origins.add("http://localhost:8000")
    cors_origins.add("http://127.0.0.1:3000")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    configure_security_middleware(
        app,
        settings,
        enable_rate_limiting=(not settings.DEBUG and not RATE_LIMIT_AVAILABLE),
    )

    # Add ProxyHeaders middleware to get real IP behind Nginx/ALB
    from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

    app.add_middleware(
        ProxyHeadersMiddleware, trusted_hosts=settings.FORWARDED_ALLOW_IPS
    )

    # Add rate limiting (production)
    if RATE_LIMIT_AVAILABLE and not settings.DEBUG:
        app.add_middleware(RateLimitMiddleware)
        logger.info("Rate limiting enabled")

    # ===== VERSIONAMIENTO (Level 3) =====
    v1 = APIRouter(prefix="/api/v1")

    v1.include_router(audits.router)
    v1.include_router(reports.router)
    v1.include_router(analytics.router)
    if search:
        v1.include_router(search.router)
    if pagespeed:
        v1.include_router(pagespeed.router)
    if backlinks:
        v1.include_router(backlinks.router)
    if keywords:
        v1.include_router(keywords.router)
    if rank_tracking:
        v1.include_router(rank_tracking.router)
    if llm_visibility:
        v1.include_router(llm_visibility.router)
    if ai_content:
        v1.include_router(ai_content.router)
    if content_editor:
        v1.include_router(content_editor.router)
    if content_analysis:
        v1.include_router(content_analysis.router)
    if geo:
        v1.include_router(geo.router)
    if hubspot:
        v1.include_router(hubspot.router)
    if github:
        v1.include_router(github.router)
    if webhooks:
        v1.include_router(webhooks.router)
    if sse:
        v1.include_router(sse.router)

    app.include_router(v1)

    # Legacy Support /api & Global Routes
    app.include_router(audits.router, prefix="/api")
    app.include_router(reports.router, prefix="/api")
    app.include_router(analytics.router, prefix="/api")
    if search:
        app.include_router(search.router, prefix="/api")
    if pagespeed:
        app.include_router(pagespeed.router, prefix="/api")
    if backlinks:
        app.include_router(backlinks.router, prefix="/api")
    if keywords:
        app.include_router(keywords.router, prefix="/api")
    if rank_tracking:
        app.include_router(rank_tracking.router, prefix="/api")
    if llm_visibility:
        app.include_router(llm_visibility.router, prefix="/api")
    if ai_content:
        app.include_router(ai_content.router, prefix="/api")
    if content_editor:
        app.include_router(content_editor.router, prefix="/api")
    if content_analysis:
        app.include_router(content_analysis.router, prefix="/api")
    if geo:
        app.include_router(geo.router, prefix="/api")
    if hubspot:
        app.include_router(hubspot.router, prefix="/api")
    if github:
        app.include_router(github.router, prefix="/api")
    if webhooks:
        app.include_router(webhooks.router, prefix="/api")
    if sse:
        app.include_router(sse.router, prefix="/api")
    app.include_router(health.router)
    if score_history:
        app.include_router(score_history.router)
    if realtime:
        app.include_router(realtime.router)

    if search:
        app.include_router(search.router)  # AI Chat search often at root

    # ===== OPENAPI CUSTOMIZATION =====
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        openapi_schema = get_openapi(
            title="🎯 " + settings.APP_NAME,
            version=settings.APP_VERSION,
            summary="Plataforma de Auditoría SEO & GEO de Próxima Generación",
            description="API modular profesional para auditoría de posicionamiento en motores tradicionales y generativos.",
            routes=app.routes,
            contact={"name": "Soporte Auditor GEO", "email": "dev@auditorgeo.com"},
        )
        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = custom_openapi
    return app


app = create_app()
