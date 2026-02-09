
import os
import sys

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from app.core.database import SessionLocal, engine
from sqlalchemy import text

def check_db():
    try:
        # Try to connect
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print(f"Database connection: OK ({result.fetchone()})")
            
        db = SessionLocal()
        from app.models import Audit
        audit_count = db.query(Audit).count()
        print(f"Total audits in DB: {audit_count}")
        db.close()
    except Exception as e:
        print(f"Database connection: FAILED - {e}")

if __name__ == "__main__":
    check_db()
