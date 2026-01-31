"""
Configuración de la aplicación
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configuración de la aplicación"""
    
    # Configuración del proyecto
    PROJECT_NAME: str = "Auditor"
    PROJECT_SLUG: str = "auditor"
    
    # Base de datos
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./auditor.db")
    SQLALCHEMY_ECHO: bool = False
    DB_RETRIES: int = 5
    DB_RETRY_DELAY: int = 2
    
    # APIs externas
    GOOGLE_API_KEY: Optional[str] = None
    GOOGLE_PAGESPEED_API_KEY: Optional[str] = None
    CSE_ID: Optional[str] = None
    
    # NVIDIA/LLM Configuration
    NVIDIA_API_KEY: Optional[str] = None
    NV_API_KEY: Optional[str] = None
    NV_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    
    # KIMI K2 Standard - Para análisis y reportes
    NV_MODEL: str = "moonshotai/kimi-k2-instruct-0905"
    NV_MODEL_ANALYSIS: str = "moonshotai/kimi-k2-instruct-0905"
    NV_API_KEY_ANALYSIS: Optional[str] = None  # Puede ser diferente
    NV_MAX_TOKENS: int = 4096
    
    # Devstral - Para modificación de código (optimizado para programación)
    NV_MODEL_CODE: str = "moonshotai/kimi-k2-instruct-0905"
    NV_API_KEY_CODE: Optional[str] = None  # Puede ser diferente
    NV_MAX_TOKENS_CODE: int = 4096
    
    # Deprecated: Usar Kimi en su lugar

    
    # Google Ads Configuration
    GOOGLE_ADS_DEVELOPER_TOKEN: str = os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN", "")
    GOOGLE_ADS_CLIENT_ID: str = os.getenv("GOOGLE_ADS_CLIENT_ID", "")
    GOOGLE_ADS_CLIENT_SECRET: str = os.getenv("GOOGLE_ADS_CLIENT_SECRET", "")
    GOOGLE_ADS_REFRESH_TOKEN: str = os.getenv("GOOGLE_ADS_REFRESH_TOKEN", "")
    GOOGLE_ADS_CUSTOMER_ID: str = os.getenv("GOOGLE_ADS_CUSTOMER_ID", "")
    GOOGLE_ADS_LOGIN_CUSTOMER_ID: str = os.getenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "")

    # HubSpot Configuration
    HUBSPOT_CLIENT_ID: Optional[str] = os.getenv("HUBSPOT_CLIENT_ID")
    HUBSPOT_CLIENT_SECRET: Optional[str] = os.getenv("HUBSPOT_CLIENT_SECRET")
    HUBSPOT_REDIRECT_URI: str = os.getenv("HUBSPOT_REDIRECT_URI", "http://localhost:3000/integrations/hubspot/callback")
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY", "CHANGE_ME_IN_PRODUCTION")

    # GitHub Configuration
    GITHUB_CLIENT_ID: Optional[str] = os.getenv("GITHUB_CLIENT_ID")
    GITHUB_CLIENT_SECRET: Optional[str] = os.getenv("GITHUB_CLIENT_SECRET")
    GITHUB_REDIRECT_URI: str = os.getenv("GITHUB_REDIRECT_URI", "http://localhost:3000/integrations/github/callback")
    GITHUB_WEBHOOK_SECRET: Optional[str] = os.getenv("GITHUB_WEBHOOK_SECRET")

    # Redis (Docker service name is 'redis')
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    
    # Celery
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER", os.getenv("REDIS_URL", "redis://redis:6379/0"))
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", os.getenv("REDIS_URL", "redis://redis:6379/1"))
    
    # Directorios
    REPORTS_DIR: str = "reports"
    REPORTS_BASE_DIR: str = "reports"
    
    # Configuración de auditoría
    MAX_CRAWL_PAGES: int = 50
    MAX_AUDIT_PAGES: int = 50
    ENABLE_PAGESPEED: bool = os.getenv("ENABLE_PAGESPEED", "True").lower() == "true"
    MAX_CRAWL_DEFAULT: int = 50
    MAX_AUDIT_DEFAULT: int = 5
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100
    
    # Configuración general
    APP_NAME: str = "Auditor"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    debug: Optional[str] = None
    secret_key: str = os.getenv("SECRET_KEY", "CHANGE_ME_IN_PRODUCTION")
    cors_origins: Optional[str] = None
    # If using .env with JSON list format like ["url1", "url2"], Pydantic handles it.
    # If using string, it might need Field with validtor or simple defaulting.
    # We will trust Pydantic to parse the .env JSON list.
    CORS_ORIGINS: list = ["http://localhost:3000", "http://localhost:8000"]
    
    # ===== PRODUCTION SECURITY SETTINGS =====
    
    # Trusted hosts (for production)
    TRUSTED_HOSTS: list = ["localhost", "127.0.0.1", "testserver", "*.your-domain.com"]
    
    # HTTPS redirect (enable in production with SSL)
    FORCE_HTTPS: bool = False
    
    # Rate limiting
    RATE_LIMIT_DEFAULT: int = 100  # requests per minute
    RATE_LIMIT_AUTH: int = 10  # auth endpoints per minute
    RATE_LIMIT_HEAVY: int = 5  # heavy operations per minute
    
    # ===== WEBHOOK SETTINGS =====
    
    # Monitoring (Level 2/3)
    SENTRY_DSN: Optional[str] = os.getenv("SENTRY_DSN")
    LOG_FORMAT: str = os.getenv("LOG_FORMAT", "json")  # "json" or "text"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    
    # ===== WEBHOOK SETTINGS =====
    DEFAULT_WEBHOOK_URL: Optional[str] = os.getenv("DEFAULT_WEBHOOK_URL")
    WEBHOOK_SECRET: str = os.getenv("WEBHOOK_SECRET", "CHANGE_ME_IN_PRODUCTION")
    
    # Frontend URL for constructing dashboard links in webhooks
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Actualizar APP_NAME con PROJECT_NAME si está configurado
        if self.PROJECT_NAME and self.PROJECT_NAME != "Auditor":
            self.APP_NAME = self.PROJECT_NAME
    
    class Config:
        env_file = ".env"
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
    
    # 1. Critical Base Variables
    if not settings.DATABASE_URL:
        errors.append("DATABASE_URL is missing!")
    
    # 2. Level 2/3 Features
    if not settings.REDIS_URL:
        warnings.append("REDIS_URL not set. Performance features (caching, real-time) will be limited.")
    
    if not settings.SENTRY_DSN:
        warnings.append("Sentry DSN not set. Error tracking is local only.")
        
    # 3. Security Check
    if settings.secret_key == "CHANGE_ME_IN_PRODUCTION" and settings.ENVIRONMENT == "production":
        errors.append("INSECURE: Change SECRET_KEY in production!")
        
    # 4. HubSpot/GitHub Integration Security
    if (settings.HUBSPOT_CLIENT_ID or settings.GITHUB_CLIENT_ID) and \
       (settings.ENCRYPTION_KEY == "CHANGE_ME_IN_PRODUCTION"):
        errors.append("INSECURE: Define real ENCRYPTION_KEY for integration tokens!")
    
    # AI Keys
    if not any([
        settings.NV_API_KEY, 
        settings.NVIDIA_API_KEY, 
        settings.NV_API_KEY_ANALYSIS, 
        settings.NV_API_KEY_CODE
    ]):
        warnings.append("No LLM API keys found (NVIDIA). AI analysis will fail.")
    else:
        logger.info("OK: NVIDIA API key configured")
    
    if settings.ENABLE_PAGESPEED and not settings.GOOGLE_PAGESPEED_API_KEY:
        warnings.append("GOOGLE_PAGESPEED_API_KEY is not set - PageSpeed analysis will be limited")
    
    # Log warnings
    for warning in warnings:
        logger.warning(f"WARN: {warning}")
    
    # Raise errors if any critical variables are missing
    if errors:
        error_message = "Missing required environment variables:\n" + "\n".join(f"  ERR: {error}" for error in errors)
        logger.error(error_message)
        # Note: We don't necessarily raise here to allow app to start even with issues, 
        # but we log them clearly.
        # raise ValueError(error_message)
    
    logger.info("OK: Environment validation complete")
    return True
