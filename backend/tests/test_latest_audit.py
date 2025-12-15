import sqlite3
import json

conn = sqlite3.connect('backend/auditor.db')
c = conn.cursor()
c.execute('SELECT id, status, pagespeed_data FROM audits ORDER BY id DESC LIMIT 1')
r = c.fetchone()

if r:
    audit_id, status, ps_data = r
    print(f"Audit ID: {audit_id}")
    print(f"Status: {status}")
    
    if ps_data:
        data = json.loads(ps_data)
        print(f"PageSpeed: YES")
        print(f"Keys: {list(data.keys())}")
        if 'mobile' in data:
            print(f"Mobile Performance: {data['mobile'].get('performance_score')}")
    else:
        print("PageSpeed: NO")
else:
    print("No audits found")
