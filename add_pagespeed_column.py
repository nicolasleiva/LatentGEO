#!/usr/bin/env python3
"""Agregar columna pagespeed_data a la tabla audits"""
import sqlite3

db_path = "backend/auditor.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    cursor.execute("ALTER TABLE audits ADD COLUMN pagespeed_data JSON")
    conn.commit()
    print("[OK] Columna pagespeed_data agregada exitosamente")
except sqlite3.OperationalError as e:
    if "duplicate column" in str(e):
        print("[OK] Columna pagespeed_data ya existe")
    else:
        print(f"[X] Error: {e}")

conn.close()
