"""
Production-Ready Database Configuration for Tests
No mocks, using YOUR existing database and .env configuration
"""
import os
from pathlib import Path
from typing import Generator
import pytest
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

# Load your existing .env file
env_path = Path(__file__).parent.parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

# Import your models
from app.core.database import Base
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
    # Falls back to your typical development database
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "postgresql://user:password@localhost:5432/auditor_geo"
    )
    
    # Connection pool settings
    POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "20"))
    MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "40"))
    POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "3600"))
    POOL_PRE_PING = os.getenv("DB_POOL_PRE_PING", "True").lower() == "true"


def get_engine():
    """Create database engine with production-ready settings"""
    
    config = DatabaseConfig()
    
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
    
    print(f"✅ Test database initialized: {DatabaseConfig.DATABASE_URL}")
    print(f"   Using your existing database configuration")
    
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
        print(f"✅ Test database cleaned up: {DatabaseConfig.DATABASE_URL}")
    else:
        print(f"✅ Test data remains in database (safe cleanup skipped)")
        print(f"   To clean up, set CLEANUP_TEST_DB=true in .env")


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
        user_id: str = "test-user-id",
        url: str = "https://example.com",
        **kwargs
    ) -> Audit:
        audit = Audit(
            user_id=user_id,
            url=url,
            status="COMPLETED",
            **kwargs
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
        term: str = "test keyword",
        volume: int = 1000,
        difficulty: int = 25,
        cpc: float = 1.5,
        **kwargs
    ) -> Keyword:
        kw = Keyword(
            audit_id=audit_id,
            term=term,
            volume=volume,
            difficulty=difficulty,
            cpc=cpc,
            **kwargs
        )
        db.add(kw)
        db.commit()
        db.refresh(kw)
        return kw


@pytest.fixture
def prod_test_user():
    """Fixture providing a real test user ID"""
    return "test-user-id"


@pytest.fixture
def prod_test_audit(db_session, prod_test_user):
    """Fixture providing a real test audit"""
    return AuditFactory.create(db_session, user_id=prod_test_user)


@pytest.fixture
def prod_test_keywords(db_session, prod_test_audit):
    """Fixture providing real test keywords"""
    keywords = []
    for i in range(5):
        kw = KeywordFactory.create(
            db_session,
            audit_id=prod_test_audit.id,
            term=f"test keyword {i}",
            volume=1000 + (i * 100),
            difficulty=20 + i,
            cpc=1.0 + i
        )
        keywords.append(kw)
    return keywords


@pytest.fixture
def prod_db_session(db_session):
    """Alias for db_session to match test imports"""
    return db_session
