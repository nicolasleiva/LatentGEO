"""
Script de migración para agregar campos de chat (language, competitors, market)
"""
from sqlalchemy import create_engine, text
from app.core.config import settings

def migrate():
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.connect() as conn:
        # Agregar columna language
        try:
            conn.execute(text("ALTER TABLE audits ADD COLUMN language VARCHAR(10) DEFAULT 'es'"))
            print("✓ Columna 'language' agregada")
        except Exception as e:
            print(f"⚠ Columna 'language' ya existe o error: {e}")
        
        # Agregar columna competitors
        try:
            conn.execute(text("ALTER TABLE audits ADD COLUMN competitors JSON"))
            print("✓ Columna 'competitors' agregada")
        except Exception as e:
            print(f"⚠ Columna 'competitors' ya existe o error: {e}")
        
        # Agregar columna market
        try:
            conn.execute(text("ALTER TABLE audits ADD COLUMN market VARCHAR(50)"))
            print("✓ Columna 'market' agregada")
        except Exception as e:
            print(f"⚠ Columna 'market' ya existe o error: {e}")
        
        conn.commit()
        print("\n✅ Migración completada")

if __name__ == "__main__":
    migrate()
