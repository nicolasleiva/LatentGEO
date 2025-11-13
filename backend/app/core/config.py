"""
Configuración global de la aplicación
"""
import os
from dotenv import load_dotenv
from typing import Optional


load_dotenv()


class Settings:
    """Settings principales de la aplicación"""

    # FastAPI
    APP_NAME: str = "GEO Audit Platform"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "True") == "True"

    # API Keys
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    GOOGLE_API_KEY: Optional[str] = os.getenv("GOOGLE_API_KEY")
    CSE_ID: Optional[str] = os.getenv("CSE_ID")

    # Base de Datos
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./auditor.db")
    SQLALCHEMY_ECHO: bool = DEBUG
    DB_RETRIES: int = int(os.getenv("DB_RETRIES", "5"))
    DB_RETRY_DELAY: int = int(os.getenv("DB_RETRY_DELAY", "2"))
    FALLBACK_TO_SQLITE: bool = os.getenv("FALLBACK_TO_SQLITE", "False") == "True"


    # Redis (para caché y cola de tareas)
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Celery (para tareas asincrónicas)
    CELERY_BROKER: str = os.getenv("CELERY_BROKER", "redis://localhost:6379/0")
    CELERY_BACKEND: str = os.getenv("CELERY_BACKEND", "redis://localhost:6379/1")

    # CORS
    CORS_ORIGINS: list = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
    ]

    # Crawling
    MAX_CRAWL_DEFAULT: int = 50
    MAX_AUDIT_DEFAULT: int = 5
    CRAWL_TIMEOUT: int = 30

    # Archivos
    REPORTS_BASE_DIR: str = os.path.join(os.getcwd(), "reports")
    UPLOADS_DIR: str = os.path.join(os.getcwd(), "uploads")

    # Paginación
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    # Seguridad
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30


settings = Settings()

# Crear directorios si no existen
os.makedirs(settings.REPORTS_BASE_DIR, exist_ok=True)
os.makedirs(settings.UPLOADS_DIR, exist_ok=True)
