import os

import psycopg2

conn = psycopg2.connect(
    host="db", port=5432, database="auditor_db", user="auditor", password="REDACTED_PASSWORD"
)

cur = conn.cursor()

try:
    cur.execute("ALTER TABLE audits ADD COLUMN IF NOT EXISTS geo_score FLOAT DEFAULT 0")
    print("✓ geo_score column added")
except Exception as e:
    print(f"geo_score: {e}")

conn.commit()
cur.close()
conn.close()
print("\n✅ Migration completed")
