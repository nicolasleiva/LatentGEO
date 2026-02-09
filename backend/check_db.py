from sqlalchemy import create_engine, text
import os

db_url = "sqlite:///./auditor.db"
engine = create_engine(db_url)

with engine.connect() as connection:
    try:
        result = connection.execute(text("SELECT id, domain FROM audits"))
        rows = result.fetchall()
        print(f"Found {len(rows)} audits:")
        for row in rows:
            print(f"ID: {row[0]}, Domain: {row[1]}")
    except Exception as e:
        print(f"Error: {e}")
