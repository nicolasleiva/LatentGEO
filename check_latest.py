import sqlite3
conn = sqlite3.connect('backend/auditor.db')
c = conn.cursor()
c.execute('SELECT id, status, pagespeed_data IS NOT NULL, LENGTH(pagespeed_data) FROM audits ORDER BY id DESC LIMIT 1')
r = c.fetchone()
if r:
    print(f"Ultima auditoria: ID={r[0]}, Status={r[1]}, Has PageSpeed={r[2]}, Size={r[3]}")
else:
    print("No hay auditorias")
