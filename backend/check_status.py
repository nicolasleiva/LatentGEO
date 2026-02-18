import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from app.core.database import SessionLocal
from app.models import Audit


def check_status():
    db = SessionLocal()
    try:
        audit = db.query(Audit).order_by(Audit.id.desc()).first()
        if audit:
            print(f"Audit ID: {audit.id}")
            print(f"URL: {audit.url}")
            print(f"Status: {audit.status}")
            print(f"Progress: {audit.progress}")
            print(f"Error: {audit.error_message}")
            if audit.target_audit:
                print(
                    f"Audited Pages: {audit.target_audit.get('audited_pages_count', 0)}"
                )
        else:
            print("No audits found.")
    finally:
        db.close()


if __name__ == "__main__":
    check_status()
