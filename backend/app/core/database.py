"""
Configuración de Base de Datos con SQLAlchemy
"""

import asyncio
import os
import re
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

from .config import settings
from .logger import get_logger

logger = get_logger(__name__)

Base = declarative_base()

_engine_instance = None
_session_factory = None
_schema_revision_verified = False

_DATABASE_PATH = Path(__file__).resolve()
_BACKEND_DIR = _DATABASE_PATH.parents[2]
_ALEMBIC_INI_PATH = _BACKEND_DIR / "alembic.ini"

_SQL_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_ALLOWED_COLUMN_SQL = {
    "VARCHAR(255)",
    "VARCHAR(500)",
    "VARCHAR(50)",
    "TEXT",
    "INTEGER",
    "BOOLEAN",
}


def _is_test_context() -> bool:
    environment = (settings.ENVIRONMENT or "").strip().lower()
    return "pytest" in sys.modules or environment in {"test", "testing"}


if not _is_test_context():
    raw_database_url = os.getenv("DATABASE_URL")
    if raw_database_url is not None and not raw_database_url.strip():
        raise RuntimeError(
            "DATABASE_URL no configurada. Definila en .env o variables de entorno."
        )
    if not (settings.DATABASE_URL or "").strip():
        raise RuntimeError(
            "DATABASE_URL no configurada. Definila en .env o variables de entorno."
        )


def _resolve_database_url(*, allow_test_placeholder: bool = False) -> str:
    database_url = (settings.DATABASE_URL or "").strip()
    if database_url:
        return database_url
    if allow_test_placeholder:
        placeholder = os.getenv("TEST_DATABASE_URL", "sqlite:///:memory:")
        logger.warning(
            "DATABASE_URL no configurada. Usando %s solo para import/test bootstrap.",
            placeholder,
        )
        return placeholder
    raise RuntimeError(
        "DATABASE_URL no configurada. Definila en .env o variables de entorno."
    )


def _build_engine(database_url: str):
    if database_url.startswith("sqlite"):
        return create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=settings.SQLALCHEMY_ECHO,
        )

    connect_timeout = max(1, int(settings.DB_CONNECT_TIMEOUT_SECONDS))
    return create_engine(
        database_url,
        echo=settings.SQLALCHEMY_ECHO,
        pool_pre_ping=bool(settings.DB_POOL_PRE_PING),
        # Pool configurable por entorno (Supabase pooler-friendly)
        pool_size=max(1, int(settings.DB_POOL_SIZE)),
        max_overflow=max(0, int(settings.DB_MAX_OVERFLOW)),
        pool_timeout=max(1, int(settings.DB_POOL_TIMEOUT)),
        pool_recycle=max(1, int(settings.DB_POOL_RECYCLE)),
        connect_args={"connect_timeout": connect_timeout},
    )


def get_engine():
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = _build_engine(
            _resolve_database_url(allow_test_placeholder=_is_test_context())
        )
    return _engine_instance


def get_session_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=get_engine(),
        )
    return _session_factory


class _EngineFacade:
    def __getattr__(self, name):
        return getattr(get_engine(), name)

    def connect(self, *args, **kwargs):
        return get_engine().connect(*args, **kwargs)

    def begin(self, *args, **kwargs):
        return get_engine().begin(*args, **kwargs)

    def dispose(self, *args, **kwargs):
        return get_engine().dispose(*args, **kwargs)

    def _run_ddl_visitor(self, *args, **kwargs):
        return get_engine()._run_ddl_visitor(*args, **kwargs)


class _SessionLocalFacade:
    def __call__(self, *args, **kwargs):
        return get_session_factory()(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(get_session_factory(), name)


engine = _EngineFacade()
SessionLocal = _SessionLocalFacade()


def get_db():
    """Dependency para obtener la sesión de base de datos"""
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()


def create_all_tables():
    """Crear todas las tablas"""
    Base.metadata.create_all(bind=get_engine())


def _build_alembic_config(database_url: str | None = None):
    from alembic.config import Config

    alembic_config = Config(str(_ALEMBIC_INI_PATH))

    def _escape_alembic_percent(value: str) -> str:
        return value.replace("%", "%%")

    if database_url:
        alembic_config.set_main_option(
            "sqlalchemy.url", _escape_alembic_percent(database_url)
        )
    else:
        alembic_config.set_main_option(
            "sqlalchemy.url",
            _escape_alembic_percent(
                _resolve_database_url(allow_test_placeholder=_is_test_context())
            ),
        )
    return alembic_config


def get_required_database_revision() -> str:
    from alembic.script import ScriptDirectory

    alembic_config = _build_alembic_config()
    script = ScriptDirectory.from_config(alembic_config)
    heads = list(script.get_heads())
    if len(heads) != 1:
        raise RuntimeError(
            "Alembic must have exactly one head revision configured. "
            f"Current heads: {heads}"
        )
    return heads[0]


def get_known_database_revisions() -> set[str]:
    from alembic.script import ScriptDirectory

    alembic_config = _build_alembic_config()
    script = ScriptDirectory.from_config(alembic_config)
    return {revision.revision for revision in script.walk_revisions()}


def get_current_database_revision(connection=None) -> str | None:
    from alembic.runtime.migration import MigrationContext

    if connection is not None:
        return MigrationContext.configure(connection).get_current_revision()

    with get_engine().connect() as conn:
        return MigrationContext.configure(conn).get_current_revision()


def run_migrations_to_head(database_url: str | None = None) -> str:
    from alembic import command

    alembic_config = _build_alembic_config(database_url)
    engine_ref = _build_engine(
        database_url or _resolve_database_url(allow_test_placeholder=_is_test_context())
    )
    known_revisions = get_known_database_revisions()

    try:
        with engine_ref.begin() as connection:
            current_revision = get_current_database_revision(connection)
            inspector = inspect(connection)
            if (
                current_revision
                and current_revision not in known_revisions
                and "alembic_version" in inspector.get_table_names()
            ):
                logger.warning(
                    "Legacy Alembic revision %s is not part of the official runtime chain. "
                    "Resetting alembic_version so the reconciliation migration can run.",
                    current_revision,
                )
                connection.execute(text("DELETE FROM alembic_version"))

        command.upgrade(alembic_config, "head")
    finally:
        engine_ref.dispose()

    return get_required_database_revision()


def ensure_database_revision(engine_ref=None, *, force: bool = False) -> str:
    global _schema_revision_verified

    if _is_test_context():
        return "test-schema"
    if _schema_revision_verified and not force:
        return get_required_database_revision()

    engine_to_use = engine_ref or get_engine()
    required_revision = get_required_database_revision()

    with engine_to_use.connect() as connection:
        current_revision = get_current_database_revision(connection)

    if current_revision != required_revision:
        current_display = current_revision or "unversioned"
        raise RuntimeError(
            "Database schema revision mismatch. "
            f"Current revision: {current_display}. "
            f"Required revision: {required_revision}. "
            "Run `alembic upgrade head` before starting backend or worker."
        )

    _schema_revision_verified = True
    return required_revision


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
    engine_to_use = engine_ref or get_engine()
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
        (
            "idx_github_connections_owner_user_id",
            "github_connections",
            ["owner_user_id"],
        ),
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
            engine_ref = get_engine()
            logger.info(
                f"[DB] Intentando conectar a la base de datos (intento {attempt}/{settings.DB_RETRIES})..."
            )
            # Validar conectividad y revision de esquema
            with engine_ref.connect() as connection:
                logger.info("[DB] Conexión a la base de datos exitosa.")
                connection.execute(text("SELECT 1"))

            if _is_test_context():
                Base.metadata.create_all(bind=engine_ref)
                ensure_performance_indexes(engine_ref)
                logger.info(
                    "[DB] Esquema de test inicializado con SQLAlchemy metadata."
                )
            else:
                revision = ensure_database_revision(engine_ref, force=True)
                logger.info("[DB] Esquema verificado en revision %s.", revision)

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
