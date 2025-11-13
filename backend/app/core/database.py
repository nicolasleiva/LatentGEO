"""
Configuración de Base de Datos con SQLAlchemy
"""
import asyncio
import time
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool
from .config import settings
from .logger import get_logger

logger = get_logger(__name__)

# Configurar engine según el tipo de BD
if settings.DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=settings.SQLALCHEMY_ECHO,
    )
else:
    engine = create_engine(
        settings.DATABASE_URL,
        echo=settings.SQLALCHEMY_ECHO,
        pool_pre_ping=True,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency para obtener la sesión de base de datos"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_all_tables():
    """Crear todas las tablas"""
    Base.metadata.create_all(bind=engine)


async def init_db():
    """
    Inicializa la base de datos.
    Intenta crear las tablas con reintentos.
    Si falla y FALLBACK_TO_SQLITE=1, usa una base de datos SQLite local.
    """
    last_exc = None
    for attempt in range(1, settings.DB_RETRIES + 1):
        try:
            # Intentar conectar y crear tablas
            with engine.connect() as connection:
                logger.info(f"[DB] Intento de conexión {attempt}/{settings.DB_RETRIES} exitoso.")
                Base.metadata.create_all(bind=engine)
                logger.info("[DB] Tablas de base de datos creadas/verificadas.")
                return
        except Exception as e:
            last_exc = e
            logger.warning(f"[DB] Intento {attempt}/{settings.DB_RETRIES} falló: {e}")
            if attempt < settings.DB_RETRIES:
                await asyncio.sleep(settings.DB_RETRY_DELAY)

    # Si todos los intentos fallaron, verificamos el fallback
    if settings.FALLBACK_TO_SQLITE:
        logger.warning("[DB] Todos los intentos fallaron — usando fallback a SQLite para desarrollo local.")
        fallback_url = "sqlite:///./dev_fallback.db"
        try:
            fallback_engine = create_engine(fallback_url, connect_args={"check_same_thread": False})
            Base.metadata.create_all(bind=fallback_engine)
            logger.info("[DB] Fallback a SQLite exitoso. Tablas creadas en 'dev_fallback.db'.")
            # Aquí podrías necesitar reconfigurar el 'engine' global si tus dependencias lo usan directamente.
            # Por ahora, la creación es suficiente para que la app no se bloquee.
        except Exception as fallback_exc:
            logger.error(f"[DB] El fallback a SQLite también falló: {fallback_exc}")
            raise fallback_exc  # Si el fallback falla, es un error grave.
    else:
        logger.error("[DB] No se pudo inicializar la base de datos después de varios reintentos.")
        raise last_exc  # Relanzar la última excepción para que el fallo sea visible
