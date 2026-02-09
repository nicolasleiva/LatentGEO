
from app.core.database import SessionLocal
from app.models import Audit
import json

db = SessionLocal()
audit = db.query(Audit).filter(Audit.id == 1).first()
if audit:
    print(f"Audit ID: {audit.id}")
    print(f"URL: {audit.url}")
    print(f"PageSpeed Data Presence: {'Yes' if audit.pagespeed_data else 'No'}")
    if audit.pagespeed_data:
        print(f"PageSpeed Data Keys: {list(audit.pagespeed_data.keys())}")
    
    print(f"Keywords count: {len(audit.keywords)}")
    print(f"Backlinks count: {len(audit.backlinks)}")
    print(f"Rank tracking count: {len(audit.rank_trackings)}")
    print(f"LLM Visibility count: {len(audit.llm_visibilities)}")
else:
    print("Audit 1 not found in DB")
db.close()
