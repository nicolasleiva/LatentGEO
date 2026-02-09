"""
Production-Ready Database Configuration for Tests
No mocks, using YOUR existing database and .env configuration
"""
import os
from pathlib import Path
from typing import Generator, List
from urllib.parse import urlparse, urlunparse

import pytest
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

# Load your existing .env file
env_path = Path(__file__).parent.parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

RUN_INTEGRATION_TESTS = os.getenv("RUN_INTEGRATION_TESTS") == "1"


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if RUN_INTEGRATION_TESTS and not value:
        raise RuntimeError(f"{name} is required when RUN_INTEGRATION_TESTS=1")
    return value or ""


def _parse_csv_env(name: str) -> List[str]:
    raw = os.getenv(name, "")
    values = [item.strip() for item in raw.split(",") if item.strip()]
    if RUN_INTEGRATION_TESTS and not values:
        raise RuntimeError(f"{name} is required when RUN_INTEGRATION_TESTS=1 (comma-separated list).")
    return values


def _redact_url(url: str) -> str:
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        if parsed.password:
            netloc = f"{parsed.username}:****@{parsed.hostname}"
            if parsed.port:
                netloc += f":{parsed.port}"
            return urlunparse((parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
        return url
    except Exception:
        return "<redacted>"


# Production test inputs (required when RUN_INTEGRATION_TESTS=1)
PROD_TEST_URL = _require_env("PROD_TEST_URL")
PROD_TEST_USER_ID = _require_env("PROD_TEST_USER_ID")
PROD_TEST_KEYWORDS = _parse_csv_env("PROD_TEST_KEYWORDS")

# Import your models
from app.core.database import Base, ensure_performance_indexes
from app.models import (
    Audit,
    Report,
    Keyword,
    Backlink,
    RankTracking,
)


class DatabaseConfig:
    """Database configuration - uses YOUR existing .env"""

    # Use your existing DATABASE_URL from .env
    DATABASE_URL = _require_env("DATABASE_URL")

    # Connection pool settings
    POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "20"))
    MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "40"))
    POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "3600"))
    POOL_PRE_PING = os.getenv("DB_POOL_PRE_PING", "True").lower() == "true"


def get_engine():
    """Create database engine with production-ready settings"""

    config = DatabaseConfig()
    if not config.DATABASE_URL:
        raise RuntimeError("DATABASE_URL is required for production tests")

    # Use SQLite for in-memory tests only if explicitly set
    if "sqlite:///:memory:" in config.DATABASE_URL:
        engine = create_engine(
            config.DATABASE_URL,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    else:
        # PostgreSQL with proper connection pooling
        engine = create_engine(
            config.DATABASE_URL,
            pool_size=config.POOL_SIZE,
            max_overflow=config.MAX_OVERFLOW,
            pool_recycle=config.POOL_RECYCLE,
            pool_pre_ping=config.POOL_PRE_PING,
            echo=os.getenv("SQL_ECHO", "false").lower() == "true",
        )

    return engine


def setup_test_database():
    """
    Prepare your existing database for tests.
    This uses your EXISTING database from .env
    """
    engine = get_engine()

    # Create all tables (if they don't exist)
    # WARNING: This does NOT drop existing data
    Base.metadata.create_all(bind=engine)
    ensure_performance_indexes(engine)

    redacted_url = _redact_url(DatabaseConfig.DATABASE_URL)
    print(f"✅ Test database initialized: {redacted_url}")
    print("   Using your existing database configuration")

    return engine


def cleanup_test_database():
    """
    Clean up test data (optional).
    This is safe - only cleans up data created by tests.
    """
    engine = get_engine()

    # Only drop tables if explicitly enabled
    if os.getenv("CLEANUP_TEST_DB", "False").lower() == "true":
        Base.metadata.drop_all(bind=engine)
        print("✅ Test database cleaned up")
    else:
        print("✅ Test data remains in database (safe cleanup skipped)")
        print("   To clean up, set CLEANUP_TEST_DB=true in .env")


@pytest.fixture(scope="session")
def db_engine():
    """Session-scoped database engine"""
    engine = setup_test_database()
    yield engine
    cleanup_test_database()


@pytest.fixture(scope="function")
def db_session(db_engine) -> Generator[Session, None, None]:
    """Function-scoped database session for each test"""
    connection = db_engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection)()

    yield session

    # Rollback transaction to ensure test isolation
    session.close()
    transaction.rollback()
    connection.close()


# Real test data factories
class AuditFactory:
    """Factory for creating real test audits"""

    @staticmethod
    def create(
        db: Session,
        user_id: str = "",
        url: str = "",
        **kwargs,
    ) -> Audit:
        audit = Audit(
            user_id=user_id or PROD_TEST_USER_ID,
            url=url or PROD_TEST_URL,
            status="COMPLETED",
            **kwargs,
        )
        db.add(audit)
        db.commit()
        db.refresh(audit)
        return audit


class KeywordFactory:
    """Factory for creating real test keywords"""

    @staticmethod
    def create(
        db: Session,
        audit_id: int,
        term: str = "",
        volume: int = 1000,
        difficulty: int = 25,
        cpc: float = 1.5,
        **kwargs,
    ) -> Keyword:
        kw = Keyword(
            audit_id=audit_id,
            term=term or (PROD_TEST_KEYWORDS[0] if PROD_TEST_KEYWORDS else ""),
            volume=volume,
            difficulty=difficulty,
            cpc=cpc,
            **kwargs,
        )
        db.add(kw)
        db.commit()
        db.refresh(kw)
        return kw


@pytest.fixture
def prod_test_user():
    """Fixture providing a real test user ID"""
    return PROD_TEST_USER_ID


@pytest.fixture
def prod_test_audit(db_session, prod_test_user):
    """Fixture providing a real test audit"""
    return AuditFactory.create(db_session, user_id=prod_test_user)


@pytest.fixture
def prod_test_keywords(db_session, prod_test_audit):
    """Fixture providing real test keywords"""
    keywords = []
    for term in PROD_TEST_KEYWORDS:
        kw = KeywordFactory.create(
            db_session,
            audit_id=prod_test_audit.id,
            term=term,
            volume=1000,
            difficulty=20,
            cpc=1.0,
        )
        keywords.append(kw)
    return keywords


@pytest.fixture
def prod_db_session(db_session):
    """Alias for db_session to match test imports"""
    return db_session
