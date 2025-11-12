"""
Configuración de Base de Datos con SQLAlchemy
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool
from .config import settings

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
