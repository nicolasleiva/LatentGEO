"""
Configuración de Base de Datos con SQLAlchemy
"""

import asyncio
import re

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

from .config import settings
from .logger import get_logger

logger = get_logger(__name__)

# Fail fast with clear message for local/manual runs.
if not settings.DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL no configurada. Definila en .env o variables de entorno."
    )

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
        # Production Pool Configuration
        pool_size=10,  # Conexiones mantenidas abiertas
        max_overflow=20,  # Conexiones adicionales bajo demanda
        pool_timeout=30,  # Segundos antes de timeout
        pool_recycle=1800,  # Reciclar conexiones cada 30min
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

_SQL_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_ALLOWED_COLUMN_SQL = {
    "VARCHAR(255)",
    "VARCHAR(500)",
    "VARCHAR(50)",
    "TEXT",
    "INTEGER",
    "BOOLEAN",
}


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


def _ensure_column_exists(connection, table: str, column: str, column_sql: str) -> None:
    if not _SQL_IDENTIFIER_RE.fullmatch(table):
        raise ValueError(f"Unsafe table identifier: {table}")
    if not _SQL_IDENTIFIER_RE.fullmatch(column):
        raise ValueError(f"Unsafe column identifier: {column}")
    normalized_column_sql = (column_sql or "").strip().upper()
    if normalized_column_sql not in _ALLOWED_COLUMN_SQL:
        raise ValueError(f"Unsafe column definition: {column_sql}")

    inspector = inspect(connection)
    if table not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns(table)}
    if column in columns:
        return

    logger.info(f"[DB] Migrando: agregando columna '{column}' en '{table}'...")
    connection.execute(
        text(f"ALTER TABLE {table} ADD COLUMN {column} {normalized_column_sql}")
    )
    connection.commit()
    logger.info(f"[DB] Columna '{column}' agregada en '{table}'.")


def ensure_connection_owner_columns(connection) -> None:
    """Ensure ownership columns/indexes for integration connections."""
    columns_to_ensure = [
        ("github_connections", "owner_user_id", "VARCHAR(255)"),
        ("github_connections", "owner_email", "VARCHAR(255)"),
        ("hubspot_connections", "owner_user_id", "VARCHAR(255)"),
        ("hubspot_connections", "owner_email", "VARCHAR(255)"),
    ]

    for table, column, column_sql in columns_to_ensure:
        try:
            _ensure_column_exists(connection, table, column, column_sql)
        except Exception as exc:
            logger.warning(
                f"[DB] No se pudo asegurar columna '{column}' en '{table}': {exc}"
            )

    index_sql = [
        "CREATE INDEX IF NOT EXISTS idx_github_connections_owner_user_id ON github_connections (owner_user_id)",
        "CREATE INDEX IF NOT EXISTS idx_github_connections_owner_email ON github_connections (owner_email)",
        "CREATE INDEX IF NOT EXISTS idx_hubspot_connections_owner_user_id ON hubspot_connections (owner_user_id)",
        "CREATE INDEX IF NOT EXISTS idx_hubspot_connections_owner_email ON hubspot_connections (owner_email)",
    ]

    for sql in index_sql:
        try:
            connection.execute(text(sql))
            connection.commit()
        except Exception as exc:
            logger.warning(f"[DB] No se pudo crear índice de ownership: {exc}")


def ensure_performance_indexes(engine_ref=None) -> None:
    """Crea índices críticos si no existen (seguro para re-ejecutar)."""
    engine_to_use = engine_ref or engine
    inspector = inspect(engine_to_use)
    table_names = set(inspector.get_table_names())
    if not table_names:
        return

    existing = {
        table: {idx["name"] for idx in inspector.get_indexes(table)}
        for table in table_names
    }

    indexes = [
        ("idx_audits_user_created", "audits", ["user_email", "created_at DESC"]),
        ("idx_audits_user_status", "audits", ["user_email", "status"]),
        ("idx_audited_pages_audit", "audited_pages", ["audit_id"]),
        ("idx_competitors_audit", "competitors", ["audit_id"]),
        ("idx_reports_audit_type", "reports", ["audit_id", "report_type"]),
        ("idx_keywords_audit", "keywords", ["audit_id"]),
        ("idx_backlinks_audit", "backlinks", ["audit_id"]),
        ("idx_rank_tracking_audit", "rank_trackings", ["audit_id"]),
        ("idx_llm_visibility_audit", "llm_visibilities", ["audit_id"]),
        (
            "idx_score_history_domain_date",
            "score_history",
            ["domain", "recorded_at DESC"],
        ),
        (
            "idx_geo_commerce_campaigns_audit",
            "geo_commerce_campaigns",
            ["audit_id", "created_at DESC"],
        ),
        (
            "idx_geo_article_batches_audit",
            "geo_article_batches",
            ["audit_id", "created_at DESC"],
        ),
        ("idx_github_connections_owner_user_id", "github_connections", ["owner_user_id"]),
        ("idx_github_connections_owner_email", "github_connections", ["owner_email"]),
        (
            "idx_hubspot_connections_owner_user_id",
            "hubspot_connections",
            ["owner_user_id"],
        ),
        ("idx_hubspot_connections_owner_email", "hubspot_connections", ["owner_email"]),
    ]

    dialect = engine_to_use.dialect.name

    def normalize_cols(cols):
        if dialect == "sqlite":
            return [c.replace(" DESC", "") for c in cols]
        return cols

    with engine_to_use.begin() as conn:
        for idx_name, table, columns in indexes:
            if table not in table_names:
                continue
            if idx_name in existing.get(table, set()):
                continue
            cols = normalize_cols(columns)
            sql = (
                f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table} ({', '.join(cols)})"
            )
            conn.execute(text(sql))


async def init_db():
    """
    Inicializa la base de datos.
    Intenta crear las tablas con reintentos.
    """
    last_exc = None
    for attempt in range(1, settings.DB_RETRIES + 1):
        try:
            logger.info(
                f"[DB] Intentando conectar a la base de datos (intento {attempt}/{settings.DB_RETRIES})..."
            )
            # Intentar conectar y crear tablas
            with engine.connect() as connection:
                logger.info("[DB] Conexión a la base de datos exitosa.")
                Base.metadata.create_all(bind=engine)
                logger.info(
                    "[DB] Tablas de base de datos creadas/verificadas correctamente."
                )

                # --- MIGRATION CHECK ---
                # Verificar si la columna 'source' existe en la tabla 'audits'
                inspector = inspect(engine)
                if "audits" in inspector.get_table_names():
                    columns = [c["name"] for c in inspector.get_columns("audits")]
                    if "source" not in columns:
                        logger.info(
                            "[DB] Migrando: Agregando columna 'source' a tabla 'audits'..."
                        )
                        try:
                            # SQLite vs Postgres syntax might differ slightly for ADD COLUMN, but usually standard
                            # For SQLite, it's ADD COLUMN. For Postgres too.
                            connection.execute(
                                text(
                                    "ALTER TABLE audits ADD COLUMN source VARCHAR(50) DEFAULT 'web'"
                                )
                            )
                            connection.commit()
                            logger.info("[DB] Columna 'source' agregada exitosamente.")
                        except Exception as e:
                            logger.error(f"[DB] Error agregando columna 'source': {e}")

                # Ensure ownership columns in integration tables.
                try:
                    ensure_connection_owner_columns(connection)
                except Exception as e:
                    logger.warning(
                        f"[DB] No se pudieron asegurar columnas owner_* en conexiones: {e}"
                    )

                # Crear índices de performance si faltan
                try:
                    ensure_performance_indexes(engine)
                    logger.info("[DB] Índices de performance verificados/creados.")
                except Exception as e:
                    logger.warning(
                        f"[DB] No se pudieron crear índices de performance: {e}"
                    )

                return
        except Exception as e:
            last_exc = e
            logger.warning(f"[DB] Intento {attempt}/{settings.DB_RETRIES} falló: {e}")
            if attempt < settings.DB_RETRIES:
                await asyncio.sleep(settings.DB_RETRY_DELAY)

    logger.error(
        "[DB] No se pudo inicializar la base de datos después de varios reintentos."
    )
    raise last_exc  # Relanzar la última excepción para que el fallo sea visible
