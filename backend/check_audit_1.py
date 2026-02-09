from sqlalchemy import create_engine, text
import os

db_url = "sqlite:///./auditor.db"
engine = create_engine(db_url)

with engine.connect() as connection:
    try:
        result = connection.execute(text("SELECT id, domain, status, report_markdown, fix_plan FROM audits WHERE id=1"))
        row = result.fetchone()
        if row:
            print(f"Audit 1: ID={row[0]}, Domain={row[1]}, Status='{row[2]}' (type: {type(row[2])})")
            print(f"Report Markdown: {'Present' if row[3] else 'None'}")
            print(f"Fix Plan: {'Present' if row[4] else 'None'}")
            print(f"Status == 'completed': {row[2] == 'completed'}")
            print(f"Status == AuditStatus.COMPLETED: {row[2] == 'completed'}")
        else:
            print("Audit 1 not found")
    except Exception as e:
        print(f"Error: {e}")