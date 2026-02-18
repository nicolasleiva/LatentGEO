import json
import os

from app.core.database import SessionLocal
from app.models import Audit, AuditedPage

db = SessionLocal()
# Search for audit 1 specifically
audit = db.query(Audit).filter(Audit.id == 1).first()

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
        try:
            ta_data = (
                audit.target_audit
                if isinstance(audit.target_audit, dict)
                else json.loads(audit.target_audit)
            )
            print(f"Target Audit Data keys: {list(ta_data.keys())}")
            print(
                f"Target Audit audited_pages_count: {ta_data.get('audited_pages_count')}"
            )
        except:
            print("Target Audit Data is NOT valid JSON or dict")
    else:
        print("Target Audit Data is EMPTY")

    # Check if pagespeed_data has data
    if audit.pagespeed_data:
        try:
            ps_data = (
                audit.pagespeed_data
                if isinstance(audit.pagespeed_data, dict)
                else json.loads(audit.pagespeed_data)
            )
            print(f"PageSpeed Data keys: {list(ps_data.keys())}")
        except:
            print("PageSpeed Data is NOT valid JSON or dict")
    else:
        print("PageSpeed Data is EMPTY")

    # Check some pages
    pages = db.query(AuditedPage).filter(AuditedPage.audit_id == audit.id).all()
    print(f"Total pages for this audit in DB: {len(pages)}")
    print(f"Sample pages (first 5):")
    for p in pages[:5]:
        print(f"  - {p.url}: score={p.overall_score}, critical={p.critical_issues}")
else:
    print("No audits found in DB")

db.close()
