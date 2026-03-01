"""
Legacy one-off migration helper.

Use only when Alembic is not available in the target environment.
Requires DATABASE_URL in environment.
"""

from __future__ import annotations

import os
import sys
from contextlib import closing

import psycopg2


def _require_database_url() -> str:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is required. Refusing to run with hardcoded credentials."
        )
    return database_url


def main() -> int:
    database_url = _require_database_url()

    statement = "ALTER TABLE audits ADD COLUMN IF NOT EXISTS geo_score FLOAT DEFAULT 0"

    with closing(psycopg2.connect(database_url)) as conn:
        with conn, conn.cursor() as cur:
            cur.execute(statement)
            print("[ok] geo_score column migration statement executed")

    print("\n[ok] Migration completed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[error] migration failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
