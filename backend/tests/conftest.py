"""
Configuración de Pytest y fixtures
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from typing import Generator

import sys
import os

# Add project root to path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from backend.app.main import app
from backend.app.core.database import get_db, Base
from backend.app.core.config import settings


@pytest.fixture(scope="function", autouse=True)
def setup_test_db():
    """
    Fixture para crear y destruir la base de datos de test.
    """
    TEST_DATABASE_URL = "sqlite:///./test.db"
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})

    # Eliminar la base de datos de test si existe de una ejecución anterior
    if os.path.exists("./test.db"):
        os.remove("./test.db")

    Base.metadata.create_all(bind=engine)
    yield engine
    # Limpieza después de que terminen todos los tests
    Base.metadata.drop_all(bind=engine)  # Asegurar que todas las tablas se eliminen
    engine.dispose()  # Cerrar todas las conexiones
    if os.path.exists("./test.db"):
        os.remove("./test.db")


@pytest.fixture(scope="function")
def db_session(setup_test_db) -> Generator:
    """
    Fixture para obtener una sesión de base de datos de test.
    """
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
