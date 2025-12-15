import psycopg2
conn = psycopg2.connect(host='db', port=5432, database='auditor_db', user='auditor', password='auditor_password')
cur = conn.cursor()
cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='audits' AND column_name='geo_score'")
result = cur.fetchone()
cur.close()
conn.close()
if result:
    print(f"✓ Column: {result[0]}, Type: {result[1]}")
else:
    print("✗ Column not found")
