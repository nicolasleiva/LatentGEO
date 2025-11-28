"""
Configuración de Base de Datos con SQLAlchemy
"""
import asyncio
import time
from sqlalchemy import create_engine, text, inspect
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
    """
    last_exc = None
    for attempt in range(1, settings.DB_RETRIES + 1):
        try:
            logger.info(f"[DB] Intentando conectar a la base de datos (intento {attempt}/{settings.DB_RETRIES})...")
            # Intentar conectar y crear tablas
            with engine.connect() as connection:
                logger.info(f"[DB] Conexión a la base de datos exitosa.")
                Base.metadata.create_all(bind=engine)
                logger.info("[DB] Tablas de base de datos creadas/verificadas correctamente.")
                
                # --- MIGRATION CHECK ---
                # Verificar si la columna 'source' existe en la tabla 'audits'
                inspector = inspect(engine)
                if "audits" in inspector.get_table_names():
                    columns = [c["name"] for c in inspector.get_columns("audits")]
                    if "source" not in columns:
                        logger.info("[DB] Migrando: Agregando columna 'source' a tabla 'audits'...")
                        try:
                            # SQLite vs Postgres syntax might differ slightly for ADD COLUMN, but usually standard
                            # For SQLite, it's ADD COLUMN. For Postgres too.
                            connection.execute(text("ALTER TABLE audits ADD COLUMN source VARCHAR(50) DEFAULT 'web'"))
                            connection.commit()
                            logger.info("[DB] Columna 'source' agregada exitosamente.")
                        except Exception as e:
                            logger.error(f"[DB] Error agregando columna 'source': {e}")
                
                return
        except Exception as e:
            last_exc = e
            logger.warning(f"[DB] Intento {attempt}/{settings.DB_RETRIES} falló: {e}")
            if attempt < settings.DB_RETRIES:
                await asyncio.sleep(settings.DB_RETRY_DELAY)

    logger.error("[DB] No se pudo inicializar la base de datos después de varios reintentos.")
    raise last_exc  # Relanzar la última excepción para que el fallo sea visible
