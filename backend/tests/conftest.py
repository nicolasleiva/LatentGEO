"""
Configuración de Pytest y fixtures
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from typing import Generator

import sys
import os

RUN_INTEGRATION_TESTS = os.getenv("RUN_INTEGRATION_TESTS") == "1"

# Add the backend directory to sys.path
# In Docker, this is /app. Locally, it's the backend folder.
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir) # This should be 'backend' local or '/app' in Docker
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Now imports should work relatively to project_root
try:
    from app.main import app
    from app.core.database import get_db, Base
    from app.core.config import settings
except ImportError as e:
    print(f"Failed to import from app.main: {e}")
    # Fallback for different environments if necessary
    try:
        from backend.app.main import app
        from backend.app.core.database import get_db, Base
        from backend.app.core.config import settings
    except ImportError:
        raise e


@pytest.fixture(scope="function", autouse=True)
def setup_test_db():
    """
    Fixture para crear y destruir la base de datos de test.
    """
    if RUN_INTEGRATION_TESTS:
        # In integration mode we avoid in-memory DB (real DB only)
        yield None
        return

    # Usar base de datos en memoria para evitar bloqueos de archivo en Windows
    TEST_DATABASE_URL = "sqlite:///:memory:"
    engine = create_engine(
        TEST_DATABASE_URL, 
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )

    Base.metadata.create_all(bind=engine)
    yield engine
    # Limpieza después de que terminen todos los tests
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(setup_test_db) -> Generator:
    """
    Fixture para obtener una sesión de base de datos de test.
    """
    if RUN_INTEGRATION_TESTS:
        pytest.skip("db_session disabled in integration mode")

    engine = setup_test_db
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def client(db_session) -> Generator:
    """
    Fixture para obtener un TestClient de FastAPI con la base de datos de test.
    """

    def override_get_db():
        try:
            yield db_session
        finally:
            db_session.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as c:
        yield c
