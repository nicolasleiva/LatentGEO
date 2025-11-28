"""
Configuración de la aplicación
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configuración de la aplicación"""
    
    # Base de datos
    DATABASE_URL: str = "sqlite:////app/db/auditor.db"
    SQLALCHEMY_ECHO: bool = False
    DB_RETRIES: int = 5
    DB_RETRY_DELAY: int = 2
    
    # APIs externas
    GOOGLE_API_KEY: Optional[str] = None
    GOOGLE_PAGESPEED_API_KEY: Optional[str] = None
    CSE_ID: Optional[str] = None
    
    # NVIDIA/Kimi Configuration (Primary LLM)
    NVIDIA_API_KEY: Optional[str] = None
    NV_API_KEY: Optional[str] = None
    NV_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    NV_MODEL: str = "moonshotai/kimi-k2-instruct-0905"
    NV_MAX_TOKENS: int = 4096
    
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
    APP_NAME: str = "Auditor GEO/SEO"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    debug: Optional[str] = None
    secret_key: str = "your-secret-key-change-in-production"
    cors_origins: Optional[str] = None
    CORS_ORIGINS: list = ["http://localhost:3000", "http://localhost:8000"]
    
    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()