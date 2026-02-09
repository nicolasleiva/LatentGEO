from app.db.session import SessionLocal
from app.models import Audit, AuditedPage
import json

db = SessionLocal()
audit = db.query(Audit).filter(Audit.url.like('%farmalife.com.ar%')).order_by(Audit.id.desc()).first()

if audit:
    print(f"Audit ID: {audit.id}")
    print(f"URL: {audit.url}")
    print(f"Status: {audit.status}")
    print(f"GEO Score: {audit.geo_score}")
    print(f"Total Pages in DB: {len(audit.pages)}")
    print(f"Critical Issues: {audit.critical_issues}")
    print(f"High Issues: {audit.high_issues}")
    print(f"Medium Issues: {audit.medium_issues}")
    
    # Check if target_audit has data
    if audit.target_audit:
        ta_data = audit.target_audit if isinstance(audit.target_audit, dict) else json.loads(audit.target_audit)
        print(f"Target Audit Data keys: {list(ta_data.keys())}")
    else:
        print("Target Audit Data is EMPTY")
        
    # Check if pagespeed_data has data
    if audit.pagespeed_data:
        ps_data = audit.pagespeed_data if isinstance(audit.pagespeed_data, dict) else json.loads(audit.pagespeed_data)
        print(f"PageSpeed Data keys: {list(ps_data.keys())}")
    else:
        print("PageSpeed Data is EMPTY")
        
    # Check some pages
    pages = db.query(AuditedPage).filter(AuditedPage.audit_id == audit.id).limit(5).all()
    print(f"Sample pages ({len(pages)}):")
    for p in pages:
        print(f"  - {p.url}: score={p.overall_score}")
else:
    print("Audit not found")

db.close()
