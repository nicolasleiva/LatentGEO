from app.core.database import SessionLocal
from app.models import Audit
import os

db = SessionLocal()
audits = db.query(Audit).order_by(Audit.id.desc()).all()

print(f"Total audits: {len(audits)}")
for a in audits:
    print(f"ID: {a.id} | URL: {a.url} | Status: {a.status} | Pages: {a.total_pages} | Critical: {a.critical_issues}")

db.close()
