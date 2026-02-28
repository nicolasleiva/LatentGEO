"""
Configuración de la aplicación
"""

import json
import os
from typing import Any, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings


def _parse_string_list(value: Any) -> list[str]:
    """Normaliza listas desde list, JSON string, CSV o valor único."""
    if value is None:
        return []

    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]

    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return []

        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]

        return [item.strip() for item in raw.split(",") if item.strip()]

    normalized = str(value).strip()
    return [normalized] if normalized else []


class Settings(BaseSettings):
    """Configuración de la aplicación"""

    # Configuración del proyecto
    PROJECT_NAME: str = "Auditor"
    PROJECT_SLUG: str = "auditor"

    # Base de datos
    DATABASE_URL: Optional[str] = os.getenv("DATABASE_URL")
    SQLALCHEMY_ECHO: bool = False
    DB_RETRIES: int = 5
    DB_RETRY_DELAY: int = 2
    DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "5"))
    DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "5"))
    DB_POOL_TIMEOUT: int = int(os.getenv("DB_POOL_TIMEOUT", "15"))
    DB_POOL_RECYCLE: int = int(os.getenv("DB_POOL_RECYCLE", "900"))
    DB_CONNECT_TIMEOUT_SECONDS: int = int(
        os.getenv("DB_CONNECT_TIMEOUT_SECONDS", "5")
    )

    # APIs externas
    GOOGLE_API_KEY: Optional[str] = None
    GOOGLE_PAGESPEED_API_KEY: Optional[str] = None
    CSE_ID: Optional[str] = None
    SERPER_API_KEY: Optional[str] = None
    EXTERNAL_HTTP_TIMEOUT_SECONDS: float = float(
        os.getenv("EXTERNAL_HTTP_TIMEOUT_SECONDS", "30")
    )

    # NVIDIA/LLM Configuration
    NVIDIA_API_KEY: Optional[str] = None
    NV_API_KEY: Optional[str] = None
    NV_BASE_URL: str = "https://integrate.api.nvidia.com/v1"

    # KIMI K2 Standard - Para análisis y reportes
    NV_MODEL: str = "moonshotai/kimi-k2.5"
    NV_MODEL_ANALYSIS: str = "moonshotai/kimi-k2.5"
    NV_API_KEY_ANALYSIS: Optional[str] = None  # Puede ser diferente
    NV_MAX_TOKENS: int = 16384
    AGENT1_LLM_TIMEOUT_SECONDS: float = float(
        os.getenv("AGENT1_LLM_TIMEOUT_SECONDS", "120")
    )
    AGENT1_RELAXED_QUERY_FILTER: bool = (
        os.getenv("AGENT1_RELAXED_QUERY_FILTER", "False").lower() == "true"
    )
    AGENT1_QUERY_DIAGNOSTICS: bool = (
        os.getenv("AGENT1_QUERY_DIAGNOSTICS", "False").lower() == "true"
    )
    NV_MAX_CONTEXT_TOKENS: int = int(os.getenv("NV_MAX_CONTEXT_TOKENS", "262144"))
    NV_CONTEXT_SAFETY_RATIO: float = float(os.getenv("NV_CONTEXT_SAFETY_RATIO", "0.7"))
    NVIDIA_TIMEOUT_SECONDS: float = float(os.getenv("NVIDIA_TIMEOUT_SECONDS", "300"))
    NV_KIMI_SEARCH_ENABLED: bool = (
        os.getenv("NV_KIMI_SEARCH_ENABLED", "False").lower() == "true"
    )
    NV_KIMI_SEARCH_MODEL: str = os.getenv(
        "NV_KIMI_SEARCH_MODEL", "moonshotai/kimi-k2.5"
    )
    NV_KIMI_SEARCH_TIMEOUT: int = int(os.getenv("NV_KIMI_SEARCH_TIMEOUT", "60"))
    NV_KIMI_SEARCH_PROVIDER: str = os.getenv("NV_KIMI_SEARCH_PROVIDER", "kimi").lower()
    GEO_ARTICLE_AUDIT_ONLY: bool = (
        os.getenv("GEO_ARTICLE_AUDIT_ONLY", "False").lower() == "true"
    )
    GEO_ARTICLE_REQUIRE_QA: bool = (
        os.getenv("GEO_ARTICLE_REQUIRE_QA", "True").lower() == "true"
    )
    GEO_ARTICLE_REQUIRE_INTERNAL_CITATION: bool = (
        os.getenv("GEO_ARTICLE_REQUIRE_INTERNAL_CITATION", "True").lower() == "true"
    )
    GEO_ARTICLE_REQUIRE_EXTERNAL_CITATION: bool = (
        os.getenv("GEO_ARTICLE_REQUIRE_EXTERNAL_CITATION", "True").lower() == "true"
    )
    GEO_ARTICLE_REQUIRE_AUTHORITY_ARTICLES: bool = (
        os.getenv("GEO_ARTICLE_REQUIRE_AUTHORITY_ARTICLES", "True").lower() == "true"
    )
    GEO_ARTICLE_REQUIRE_TOPIC_MATCH: bool = (
        os.getenv("GEO_ARTICLE_REQUIRE_TOPIC_MATCH", "True").lower() == "true"
    )
    GEO_ARTICLE_MIN_QA_PAIRS: int = int(os.getenv("GEO_ARTICLE_MIN_QA_PAIRS", "3"))
    GEO_ARTICLE_ALLOWED_EXTERNAL_SOURCES: int = int(
        os.getenv("GEO_ARTICLE_ALLOWED_EXTERNAL_SOURCES", "8")
    )
    GEO_ARTICLE_REPAIR_INVALID_CITATIONS: bool = (
        os.getenv("GEO_ARTICLE_REPAIR_INVALID_CITATIONS", "True").lower() == "true"
    )
    GEO_ARTICLE_EXTRA_SEARCH_QUERIES: int = int(
        os.getenv("GEO_ARTICLE_EXTRA_SEARCH_QUERIES", "3")
    )
    GEO_ARTICLE_EXTRA_SEARCH_TOP_K: int = int(
        os.getenv("GEO_ARTICLE_EXTRA_SEARCH_TOP_K", "10")
    )

    # Devstral - Para modificación de código (optimizado para programación)
    NV_MODEL_CODE: str = "moonshotai/kimi-k2-instruct-0905"
    NV_API_KEY_CODE: Optional[str] = None  # Puede ser diferente
    NV_MAX_TOKENS_CODE: int = 8192
    CODE_LLM_TIMEOUT_SECONDS: float = float(
        os.getenv("CODE_LLM_TIMEOUT_SECONDS", "120")
    )

    # Google Ads Configuration
    GOOGLE_ADS_DEVELOPER_TOKEN: str = os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN", "")
    GOOGLE_ADS_CLIENT_ID: str = os.getenv("GOOGLE_ADS_CLIENT_ID", "")
    GOOGLE_ADS_CLIENT_SECRET: str = os.getenv("GOOGLE_ADS_CLIENT_SECRET", "")
    GOOGLE_ADS_REFRESH_TOKEN: str = os.getenv("GOOGLE_ADS_REFRESH_TOKEN", "")
    GOOGLE_ADS_CUSTOMER_ID: str = os.getenv("GOOGLE_ADS_CUSTOMER_ID", "")
    GOOGLE_ADS_LOGIN_CUSTOMER_ID: str = os.getenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "")
    GOOGLE_ADS_TIMEOUT_SECONDS: float = float(
        os.getenv("GOOGLE_ADS_TIMEOUT_SECONDS", "30")
    )

    # HubSpot Configuration
    HUBSPOT_CLIENT_ID: Optional[str] = os.getenv("HUBSPOT_CLIENT_ID")
    HUBSPOT_CLIENT_SECRET: Optional[str] = os.getenv("HUBSPOT_CLIENT_SECRET")
    HUBSPOT_REDIRECT_URI: Optional[str] = os.getenv("HUBSPOT_REDIRECT_URI")
    HUBSPOT_API_TIMEOUT_SECONDS: float = float(
        os.getenv("HUBSPOT_API_TIMEOUT_SECONDS", "30")
    )
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY", "CHANGE_ME_IN_PRODUCTION")

    # GitHub Configuration
    GITHUB_CLIENT_ID: Optional[str] = os.getenv("GITHUB_CLIENT_ID")
    GITHUB_CLIENT_SECRET: Optional[str] = os.getenv("GITHUB_CLIENT_SECRET")
    GITHUB_REDIRECT_URI: Optional[str] = os.getenv("GITHUB_REDIRECT_URI")
    GITHUB_WEBHOOK_SECRET: Optional[str] = os.getenv("GITHUB_WEBHOOK_SECRET")
    GITHUB_API_TIMEOUT_SECONDS: float = float(
        os.getenv("GITHUB_API_TIMEOUT_SECONDS", "30")
    )

    # Redis (Docker service name is 'redis')
    REDIS_URL: Optional[str] = os.getenv("REDIS_URL")

    # Celery
    CELERY_BROKER_URL: Optional[str] = os.getenv("CELERY_BROKER_URL") or os.getenv(
        "CELERY_BROKER"
    )
    CELERY_RESULT_BACKEND: Optional[str] = os.getenv(
        "CELERY_RESULT_BACKEND"
    ) or os.getenv("CELERY_BACKEND")

    # Directorios
    REPORTS_DIR: str = "reports"
    REPORTS_BASE_DIR: str = "reports"
    AUDIT_LOCAL_ARTIFACTS_ENABLED: bool = (
        os.getenv("AUDIT_LOCAL_ARTIFACTS_ENABLED", "False").lower() == "true"
    )

    # Configuración de auditoría
    MAX_CRAWL_PAGES: int = int(os.getenv("MAX_CRAWL_PAGES", "50"))
    MAX_AUDIT_PAGES: int = int(os.getenv("MAX_AUDIT_PAGES", "50"))
    ENABLE_PAGESPEED: bool = os.getenv("ENABLE_PAGESPEED", "True").lower() == "true"
    ALLOW_INSECURE_SSL_FALLBACK: bool = (
        os.getenv("ALLOW_INSECURE_SSL_FALLBACK", "False").lower() == "true"
    )
    PDF_LOCK_TTL_SECONDS: int = int(os.getenv("PDF_LOCK_TTL_SECONDS", "900"))
    MAX_CRAWL_DEFAULT: int = 50
    RESPECT_ROBOTS: bool = os.getenv("RESPECT_ROBOTS", "False").lower() == "true"
    MAX_AUDIT_DEFAULT: int = 5
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    # SSE / streaming
    SSE_MAX_DURATION: int = int(os.getenv("SSE_MAX_DURATION", "3600"))

    # LLM output limits (report generation)
    NV_MAX_TOKENS_REPORT: int = int(os.getenv("NV_MAX_TOKENS_REPORT", "8192"))
    REPORT_LENGTH_STRICT: bool = (
        os.getenv("REPORT_LENGTH_STRICT", "False").lower() == "true"
    )
    REPORT_MIN_WORDS: int = int(os.getenv("REPORT_MIN_WORDS", "8000"))
    REPORT_MIN_SECTION_WORDS: int = int(os.getenv("REPORT_MIN_SECTION_WORDS", "400"))
    REPORT_MIN_EXEC_SUMMARY_WORDS: int = int(
        os.getenv("REPORT_MIN_EXEC_SUMMARY_WORDS", "800")
    )

    # Configuración general
    APP_NAME: str = "Auditor"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    debug: Optional[str] = None
    secret_key: str = os.getenv("SECRET_KEY", "CHANGE_ME_IN_PRODUCTION")
    OAUTH_STATE_SECRET: Optional[str] = os.getenv("OAUTH_STATE_SECRET")
    OAUTH_STATE_TTL_SECONDS: int = int(os.getenv("OAUTH_STATE_TTL_SECONDS", "600"))
    AUTH0_DOMAIN: Optional[str] = os.getenv("AUTH0_DOMAIN")
    AUTH0_ISSUER_BASE_URL: Optional[str] = os.getenv("AUTH0_ISSUER_BASE_URL")
    AUTH0_API_AUDIENCE: Optional[str] = os.getenv("AUTH0_API_AUDIENCE")
    AUTH0_API_SCOPES: str = os.getenv("AUTH0_API_SCOPES", "read:app")
    AUTH0_EXPECTED_CLIENT_ID: Optional[str] = os.getenv("AUTH0_EXPECTED_CLIENT_ID")
    AUTH0_JWKS_CACHE_TTL_SECONDS: int = int(
        os.getenv("AUTH0_JWKS_CACHE_TTL_SECONDS", "21600")
    )
    AUTH0_JWKS_FETCH_TIMEOUT_MS: int = int(
        os.getenv("AUTH0_JWKS_FETCH_TIMEOUT_MS", "2000")
    )
    cors_origins: Optional[str] = None
    CORS_ORIGINS: list[str] = []

    # ===== PRODUCTION SECURITY SETTINGS =====
    TRUSTED_HOSTS: list[str] = []
    FORWARDED_ALLOW_IPS: list[str] = []
    LOG_DIR: str = os.getenv("LOG_DIR", "logs")
    PIPELINE_JSON_PARSE_MAX_CHARS: int = int(
        os.getenv("PIPELINE_JSON_PARSE_MAX_CHARS") or "200000"
    )
    WEBHOOK_TIMEOUT_SECONDS: float = float(os.getenv("WEBHOOK_TIMEOUT_SECONDS", "30"))
    SERPER_TIMEOUT_SECONDS: float = float(os.getenv("SERPER_TIMEOUT_SECONDS", "15"))
    PAGESPEED_TIMEOUT_SECONDS: float = float(
        os.getenv("PAGESPEED_TIMEOUT_SECONDS", "180")
    )

    # External resilience
    CIRCUIT_BREAKER_ENABLED: bool = (
        os.getenv("CIRCUIT_BREAKER_ENABLED", "True").lower() == "true"
    )
    CIRCUIT_BREAKER_FAIL_MAX: int = int(os.getenv("CIRCUIT_BREAKER_FAIL_MAX", "5"))
    CIRCUIT_BREAKER_RESET_TIMEOUT_SECONDS: int = int(
        os.getenv("CIRCUIT_BREAKER_RESET_TIMEOUT_SECONDS", "60")
    )
    CIRCUIT_BREAKER_SUCCESS_THRESHOLD: int = int(
        os.getenv("CIRCUIT_BREAKER_SUCCESS_THRESHOLD", "2")
    )

    # HTTPS redirect (enable in production with SSL)
    FORCE_HTTPS: bool = False

    # Rate limiting
    RATE_LIMIT_DEFAULT: int = 100  # requests per minute
    RATE_LIMIT_AUTH: int = 10  # auth endpoints per minute
    RATE_LIMIT_HEAVY: int = 5  # heavy operations per minute

    # ===== SUPABASE INTEGRATION =====
    SUPABASE_URL: Optional[str] = os.getenv("SUPABASE_URL")
    SUPABASE_KEY: Optional[str] = os.getenv("SUPABASE_KEY")  # Anon/Public key
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    SUPABASE_JWT_SECRET: Optional[str] = os.getenv("SUPABASE_JWT_SECRET")
    SUPABASE_STORAGE_BUCKET: str = os.getenv("SUPABASE_STORAGE_BUCKET", "audit-reports")
    SUPABASE_TIMEOUT_SECONDS: float = float(
        os.getenv("SUPABASE_TIMEOUT_SECONDS", "30")
    )

    # ===== WEBHOOK SETTINGS =====
    SENTRY_DSN: Optional[str] = os.getenv("SENTRY_DSN")
    LOG_FORMAT: str = os.getenv("LOG_FORMAT", "json")  # "json" or "text"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    STRICT_CONFIG: bool = os.getenv("STRICT_CONFIG", "False").lower() == "true"

    DEFAULT_WEBHOOK_URL: Optional[str] = os.getenv("DEFAULT_WEBHOOK_URL")
    WEBHOOK_SECRET: str = os.getenv("WEBHOOK_SECRET", "CHANGE_ME_IN_PRODUCTION")

    # Frontend URL for constructing dashboard links in webhooks
    FRONTEND_URL: Optional[str] = os.getenv("FRONTEND_URL")

    @field_validator(
        "CORS_ORIGINS", "TRUSTED_HOSTS", "FORWARDED_ALLOW_IPS", mode="before"
    )
    @classmethod
    def _normalize_list_fields(cls, value: Any) -> list[str]:
        return _parse_string_list(value)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Actualizar APP_NAME con PROJECT_NAME si está configurado
        if self.PROJECT_NAME and self.PROJECT_NAME != "Auditor":
            self.APP_NAME = self.PROJECT_NAME

        # Reutilizar la key de PageSpeed para integraciones legacy de Google
        if not self.GOOGLE_API_KEY and self.GOOGLE_PAGESPEED_API_KEY:
            self.GOOGLE_API_KEY = self.GOOGLE_PAGESPEED_API_KEY

        # Defaults for local/dev only
        if self.ENVIRONMENT != "production":
            if not self.CORS_ORIGINS:
                self.CORS_ORIGINS = [
                    "http://localhost:3000",
                    "http://localhost:8000",
                    "http://127.0.0.1:3000",
                    "http://host.docker.internal:3000",
                ]
            if not self.TRUSTED_HOSTS:
                self.TRUSTED_HOSTS = [
                    "localhost",
                    "127.0.0.1",
                    "testserver",
                    "*.your-domain.com",
                ]
            if not self.FORWARDED_ALLOW_IPS:
                self.FORWARDED_ALLOW_IPS = ["127.0.0.1", "::1"]
            if not self.FRONTEND_URL:
                self.FRONTEND_URL = "http://localhost:3000"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()


def validate_environment():
    """
    Validates required environment variables and logs warnings for missing optional ones.
    """
    import logging

    logger = logging.getLogger(__name__)

    warnings = []
    errors = []

    is_production = settings.ENVIRONMENT.lower() == "production"
    is_non_dev = settings.ENVIRONMENT.lower() not in {
        "development",
        "dev",
        "local",
        "test",
    }
    strict = (
        settings.STRICT_CONFIG
        or is_production
        or not settings.AUDIT_LOCAL_ARTIFACTS_ENABLED
    )

    def require(value, name):
        if not value:
            errors.append(f"{name} is missing!")

    def require_non_default(value, default, name):
        if value == default:
            errors.append(f"INSECURE: Change {name} in production!")

    def require_not_localhost(value, name):
        if value and ("localhost" in value or "127.0.0.1" in value):
            errors.append(f"{name} must not point to localhost in production.")

    # 1. Critical Base Variables
    require(settings.DATABASE_URL, "DATABASE_URL")
    if is_production and settings.DATABASE_URL and "sqlite" in settings.DATABASE_URL:
        errors.append("DATABASE_URL cannot be sqlite in production.")
    if is_non_dev and settings.DATABASE_URL and "supabase" not in settings.DATABASE_URL:
        errors.append("DATABASE_URL must point to Supabase in non-dev environments.")
    if (
        not settings.AUDIT_LOCAL_ARTIFACTS_ENABLED
        and settings.DATABASE_URL
        and "supabase" not in settings.DATABASE_URL.lower()
    ):
        errors.append(
            "DATABASE_URL must point to Supabase when AUDIT_LOCAL_ARTIFACTS_ENABLED=false."
        )
    if not settings.AUDIT_LOCAL_ARTIFACTS_ENABLED:
        require(settings.SUPABASE_URL, "SUPABASE_URL")
        require(settings.SUPABASE_SERVICE_ROLE_KEY, "SUPABASE_SERVICE_ROLE_KEY")
        require(settings.SUPABASE_STORAGE_BUCKET, "SUPABASE_STORAGE_BUCKET")

    # 2. Redis/Celery
    if not settings.REDIS_URL:
        warnings.append(
            "REDIS_URL not set. Performance features (caching, real-time) will be limited."
        )
    if not settings.CELERY_BROKER_URL:
        warnings.append("CELERY_BROKER_URL not set. Celery tasks may fail.")
    if not settings.CELERY_RESULT_BACKEND:
        warnings.append(
            "CELERY_RESULT_BACKEND not set. Celery results may not be stored."
        )

    if strict:
        require(settings.REDIS_URL, "REDIS_URL")
        require(settings.CELERY_BROKER_URL, "CELERY_BROKER_URL")
        require(settings.CELERY_RESULT_BACKEND, "CELERY_RESULT_BACKEND")

    # 3. Monitoring
    if not settings.SENTRY_DSN:
        warnings.append("Sentry DSN not set. Error tracking is local only.")

    # 4. Security Check
    if is_production:
        require_non_default(
            settings.secret_key, "CHANGE_ME_IN_PRODUCTION", "SECRET_KEY"
        )
        require_non_default(
            settings.ENCRYPTION_KEY, "CHANGE_ME_IN_PRODUCTION", "ENCRYPTION_KEY"
        )
        require_non_default(
            settings.WEBHOOK_SECRET, "CHANGE_ME_IN_PRODUCTION", "WEBHOOK_SECRET"
        )
        require(settings.FRONTEND_URL, "FRONTEND_URL")
        require_not_localhost(settings.FRONTEND_URL, "FRONTEND_URL")
        if settings.DEBUG:
            errors.append("DEBUG must be False in production.")
        if not settings.CORS_ORIGINS:
            errors.append("CORS_ORIGINS is missing in production.")
        if not settings.TRUSTED_HOSTS:
            errors.append("TRUSTED_HOSTS is missing in production.")
        if not settings.FORWARDED_ALLOW_IPS:
            errors.append("FORWARDED_ALLOW_IPS is missing in production.")
        if "*" in settings.FORWARDED_ALLOW_IPS:
            errors.append(
                "FORWARDED_ALLOW_IPS cannot include '*' in production. Set explicit proxy IPs/CIDRs."
            )

    # 5. HubSpot/GitHub Integration Security
    if (settings.HUBSPOT_CLIENT_ID or settings.GITHUB_CLIENT_ID) and (
        settings.ENCRYPTION_KEY == "CHANGE_ME_IN_PRODUCTION"
    ):
        errors.append("INSECURE: Define real ENCRYPTION_KEY for integration tokens!")

    # 6. Auth0 API token validation requirements outside development-like environments
    if is_non_dev:
        require(settings.AUTH0_API_AUDIENCE, "AUTH0_API_AUDIENCE")
        if not (settings.AUTH0_ISSUER_BASE_URL or settings.AUTH0_DOMAIN):
            errors.append("AUTH0_ISSUER_BASE_URL or AUTH0_DOMAIN is missing!")

    if strict:
        require(settings.AUTH0_API_AUDIENCE, "AUTH0_API_AUDIENCE")
        if not (settings.AUTH0_ISSUER_BASE_URL or settings.AUTH0_DOMAIN):
            errors.append("AUTH0_ISSUER_BASE_URL or AUTH0_DOMAIN is missing!")
        if settings.AUTH0_JWKS_FETCH_TIMEOUT_MS <= 0:
            errors.append("AUTH0_JWKS_FETCH_TIMEOUT_MS must be > 0.")
        if settings.AUTH0_JWKS_CACHE_TTL_SECONDS <= 0:
            errors.append("AUTH0_JWKS_CACHE_TTL_SECONDS must be > 0.")
        if settings.DB_POOL_SIZE <= 0:
            errors.append("DB_POOL_SIZE must be > 0.")
        if settings.DB_MAX_OVERFLOW < 0:
            errors.append("DB_MAX_OVERFLOW must be >= 0.")
        if settings.DB_POOL_TIMEOUT <= 0:
            errors.append("DB_POOL_TIMEOUT must be > 0.")
        if settings.DB_POOL_RECYCLE <= 0:
            errors.append("DB_POOL_RECYCLE must be > 0.")
        if settings.DB_CONNECT_TIMEOUT_SECONDS <= 0:
            errors.append("DB_CONNECT_TIMEOUT_SECONDS must be > 0.")

    # AI Keys
    if not any(
        [
            settings.NV_API_KEY,
            settings.NVIDIA_API_KEY,
            settings.NV_API_KEY_ANALYSIS,
            settings.NV_API_KEY_CODE,
        ]
    ):
        warnings.append("No LLM API keys found (NVIDIA). AI analysis will fail.")
    else:
        logger.info("OK: NVIDIA API key configured")

    if settings.NV_KIMI_SEARCH_ENABLED and not any(
        [settings.NV_API_KEY, settings.NVIDIA_API_KEY, settings.NV_API_KEY_ANALYSIS]
    ):
        warnings.append(
            "NV_KIMI_SEARCH_ENABLED=true but no NVIDIA API key is configured. Search endpoints will fail."
        )

    if settings.ENABLE_PAGESPEED and not settings.GOOGLE_PAGESPEED_API_KEY:
        warnings.append(
            "GOOGLE_PAGESPEED_API_KEY is not set - PageSpeed analysis will be limited"
        )

    # Log warnings
    for warning in warnings:
        logger.warning(f"WARN: {warning}")

    # Raise errors if any critical variables are missing
    if errors:
        error_message = "Missing or insecure environment variables:\n" + "\n".join(
            f"  ERR: {error}" for error in errors
        )
        logger.error(error_message)
        if strict:
            raise RuntimeError(error_message)

    logger.info("OK: Environment validation complete")
    return True
