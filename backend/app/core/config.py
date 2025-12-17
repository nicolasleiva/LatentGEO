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
    DATABASE_URL: str = "sqlite:////app/db/auditor.db"
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
    
    # KIMI K2 Thinking - Para análisis y reportes (mejor razonamiento)
    NV_MODEL: str = "moonshotai/kimi-k2-thinking"
    NV_MODEL_ANALYSIS: str = "moonshotai/kimi-k2-thinking"
    NV_API_KEY_ANALYSIS: Optional[str] = None  # Puede ser diferente
    NV_MAX_TOKENS: int = 16384
    
    # Devstral - Para modificación de código (optimizado para programación)
    NV_MODEL_CODE: str = "mistralai/devstral-2-123b-instruct-2512"
    NV_API_KEY_CODE: Optional[str] = None  # Puede ser diferente
    NV_MAX_TOKENS_CODE: int = 8192
    
    # Deprecated: Usar Kimi en su lugar
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-2.5-flash-lite"
    OPENAI_API_KEY: Optional[str] = None
    
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
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY", "your-encryption-key-must-be-32-url-safe-base64-bytes")

    # GitHub Configuration
    GITHUB_CLIENT_ID: Optional[str] = os.getenv("GITHUB_CLIENT_ID")
    GITHUB_CLIENT_SECRET: Optional[str] = os.getenv("GITHUB_CLIENT_SECRET")
    GITHUB_REDIRECT_URI: str = os.getenv("GITHUB_REDIRECT_URI", "http://localhost:3000/integrations/github/callback")
    GITHUB_WEBHOOK_SECRET: Optional[str] = os.getenv("GITHUB_WEBHOOK_SECRET")

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    
    # Directorios
    REPORTS_DIR: str = "reports"
    REPORTS_BASE_DIR: str = "reports"
    
    # Configuración de auditoría
    MAX_CRAWL_PAGES: int = 50
    MAX_AUDIT_PAGES: int = 5
    MAX_CRAWL_DEFAULT: int = 50
    MAX_AUDIT_DEFAULT: int = 5
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100
    
    # Configuración general
    APP_NAME: str = "Auditor"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    debug: Optional[str] = None
    secret_key: str = "your-secret-key-change-in-production"
    cors_origins: Optional[str] = None
    CORS_ORIGINS: list = ["http://localhost:3000", "http://localhost:8000"]
    
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
    Raises ValueError if critical variables are missing.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    errors = []
    warnings = []
    
    # Critical variables (required for core functionality)
    if not settings.DATABASE_URL:
        errors.append("DATABASE_URL is required")
    
    # HubSpot integration variables (required if using HubSpot)
    if settings.HUBSPOT_CLIENT_ID or settings.HUBSPOT_CLIENT_SECRET:
        if not settings.HUBSPOT_CLIENT_ID:
            errors.append("HUBSPOT_CLIENT_ID is required when HubSpot integration is configured")
        if not settings.HUBSPOT_CLIENT_SECRET:
            errors.append("HUBSPOT_CLIENT_SECRET is required when HubSpot integration is configured")
        if not settings.ENCRYPTION_KEY or settings.ENCRYPTION_KEY == "your-encryption-key-must-be-32-url-safe-base64-bytes":
            errors.append("ENCRYPTION_KEY must be set to a valid 32-byte URL-safe base64 key for HubSpot integration")
    
    # GitHub integration variables (required if using GitHub)
    if settings.GITHUB_CLIENT_ID or settings.GITHUB_CLIENT_SECRET:
        if not settings.GITHUB_CLIENT_ID:
            errors.append("GITHUB_CLIENT_ID is required when GitHub integration is configured")
        if not settings.GITHUB_CLIENT_SECRET:
            errors.append("GITHUB_CLIENT_SECRET is required when GitHub integration is configured")
    
    # Optional but recommended variables
    if not settings.GOOGLE_PAGESPEED_API_KEY:
        warnings.append("GOOGLE_PAGESPEED_API_KEY is not set - PageSpeed analysis will be limited")
    
    if not settings.NVIDIA_API_KEY and not settings.NV_API_KEY:
        warnings.append("NVIDIA_API_KEY/NV_API_KEY is not set - AI features may not work")
    
    if not settings.GOOGLE_API_KEY:
        warnings.append("GOOGLE_API_KEY is not set - Some search features may not work")
    
    # Log warnings
    for warning in warnings:
        logger.warning(f"⚠️  {warning}")
    
    # Raise errors if any critical variables are missing
    if errors:
        error_message = "Missing required environment variables:\n" + "\n".join(f"  ❌ {error}" for error in errors)
        logger.error(error_message)
        raise ValueError(error_message)
    
    logger.info("✅ Environment validation passed")
    return True