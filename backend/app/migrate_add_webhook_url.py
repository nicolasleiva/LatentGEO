"""
Script de migración para agregar columna webhook_url
"""

from app.core.config import settings
from sqlalchemy import create_engine, text


def migrate():
    engine = create_engine(settings.DATABASE_URL)

    with engine.connect() as conn:
        # Agregar columna webhook_url
        try:
            conn.execute(text("ALTER TABLE audits ADD COLUMN webhook_url VARCHAR(500)"))
            print("✓ Columna 'webhook_url' agregada")
        except Exception as e:
            print(f"⚠ Columna 'webhook_url' ya existe o error: {e}")

        conn.commit()
        print("\n✅ Migración completada")


if __name__ == "__main__":
    migrate()
