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
from .middleware.legacy_api_redirect import LegacyApiRedirectMiddleware

logger = get_logger(__name__)

# Import rate limiting
try:
    from .middleware.rate_limit import RateLimitMiddleware

    RATE_LIMIT_AVAILABLE = True
except ImportError:
    RATE_LIMIT_AVAILABLE = False
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
from .api.routes import (  # noqa: E402
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

from contextlib import asynccontextmanager  # noqa: E402


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
        logger.error(f"ERR: Environment validation failed: {e}")
        raise RuntimeError(f"Environment validation failed: {e}") from e

    try:
        await init_db()
        logger.info("OK: Conexion con Base de Datos establecida")
    except Exception as e:
        logger.critical(f"ERR: Fallo critico al inicializar la base de datos: {e}")
        raise RuntimeError(f"Database initialization failed: {e}") from e

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
    # Always send explicit origins to support credentials (cookies/auth)
    # We avoid "*" even in DEBUG because it conflicts with allow_credentials=True

    cors_origins = set(settings.CORS_ORIGINS)
    # Keep local/docker defaults only for non-production-like environments.
    if settings.DEBUG or settings.ENVIRONMENT.lower() in {"development", "dev", "local"}:
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

    rate_limit_enabled = not settings.DEBUG
    use_distributed_rate_limit = rate_limit_enabled and RATE_LIMIT_AVAILABLE
    use_fallback_rate_limit = rate_limit_enabled and not RATE_LIMIT_AVAILABLE

    configure_security_middleware(
        app,
        settings,
        enable_rate_limiting=use_fallback_rate_limit,
    )

    # Add ProxyHeaders middleware to get real IP behind Nginx/ALB
    from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

    app.add_middleware(
        ProxyHeadersMiddleware, trusted_hosts=settings.FORWARDED_ALLOW_IPS
    )

    # Add distributed Redis-backed rate limiting in production.
    if use_distributed_rate_limit:
        app.add_middleware(RateLimitMiddleware)
        logger.info("Rate limiting enabled (mode=redis-distributed)")
    elif use_fallback_rate_limit:
        logger.info("Rate limiting enabled (mode=core-fallback)")
    else:
        logger.info("Rate limiting disabled (mode=disabled-debug)")

    # Add legacy redirect middleware last so it executes first in Starlette stack order.
    if settings.DEBUG and settings.LEGACY_API_REDIRECT_ENABLED:
        app.add_middleware(LegacyApiRedirectMiddleware)
        logger.info("Legacy API redirect enabled (debug-only, /api/* -> /api/v1/*)")

    # ===== VERSIONAMIENTO (Level 3) =====
    v1 = APIRouter(prefix="/api/v1")

    # Register business routers only under /api/v1.
    api_route_modules = [
        audits,
        reports,
        analytics,
        search,
        pagespeed,
        backlinks,
        keywords,
        rank_tracking,
        llm_visibility,
        ai_content,
        content_editor,
        content_analysis,
        geo,
        hubspot,
        github,
        webhooks,
        sse,
    ]
    if score_history:
        api_route_modules.append(score_history)

    for module in api_route_modules:
        if module:
            v1.include_router(module.router)

    app.include_router(v1)

    # Global non-versioned routes
    app.include_router(health.router)
    if realtime:
        app.include_router(realtime.router)

    # Do not expose business endpoints at root paths.

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

        components = openapi_schema.setdefault("components", {})
        security_schemes = components.setdefault("securitySchemes", {})
        security_schemes.setdefault(
            "HTTPBearer",
            {"type": "http", "scheme": "bearer"},
        )

        public_operations = {
            ("post", "/api/v1/github/webhook"),
            ("post", "/api/v1/webhooks/github/incoming"),
            ("post", "/api/v1/webhooks/hubspot/incoming"),
            ("get", "/health"),
            ("get", "/health/ready"),
            ("get", "/health/live"),
        }
        http_methods = {
            "get",
            "post",
            "put",
            "patch",
            "delete",
            "options",
            "head",
            "trace",
        }
        for path, path_item in openapi_schema.get("paths", {}).items():
            for method, operation in path_item.items():
                method_lower = method.lower()
                if method_lower not in http_methods or not isinstance(operation, dict):
                    continue
                if (method_lower, path) in public_operations:
                    operation["security"] = []
                    continue
                if "security" not in operation:
                    operation["security"] = [{"HTTPBearer": []}]

        openapi_schema["security"] = [{"HTTPBearer": []}]
        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = custom_openapi
    return app


app = create_app()
