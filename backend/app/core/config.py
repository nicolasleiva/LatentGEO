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
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-2.5-flash-lite"
    OPENAI_API_KEY: Optional[str] = None
    NVIDIA_API_KEY: Optional[str] = None
    api_key: Optional[str] = None
    nv_api_key: Optional[str] = None
    base_url: Optional[str] = None
    
    # Google Ads Configuration
    GOOGLE_ADS_DEVELOPER_TOKEN: str = os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN", "")
    GOOGLE_ADS_CLIENT_ID: str = os.getenv("GOOGLE_ADS_CLIENT_ID", "")
    GOOGLE_ADS_CLIENT_SECRET: str = os.getenv("GOOGLE_ADS_CLIENT_SECRET", "")
    GOOGLE_ADS_REFRESH_TOKEN: str = os.getenv("GOOGLE_ADS_REFRESH_TOKEN", "")
    GOOGLE_ADS_CUSTOMER_ID: str = os.getenv("GOOGLE_ADS_CUSTOMER_ID", "")
    GOOGLE_ADS_LOGIN_CUSTOMER_ID: str = os.getenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "")

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