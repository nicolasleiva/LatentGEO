import psycopg2
import os

conn = psycopg2.connect(
    host="localhost",
    port=5432,
    database="auditor_db",
    user="auditor",
    password="REDACTED_PASSWORD"
)

cur = conn.cursor()

try:
    cur.execute("ALTER TABLE audits ADD COLUMN IF NOT EXISTS language VARCHAR(10) DEFAULT 'es'")
    print("✓ language column added")
except Exception as e:
    print(f"language: {e}")

try:
    cur.execute("ALTER TABLE audits ADD COLUMN IF NOT EXISTS competitors JSON")
    print("✓ competitors column added")
except Exception as e:
    print(f"competitors: {e}")

try:
    cur.execute("ALTER TABLE audits ADD COLUMN IF NOT EXISTS market VARCHAR(50)")
    print("✓ market column added")
except Exception as e:
    print(f"market: {e}")

conn.commit()
cur.close()
conn.close()
print("\n✅ Migration completed")
