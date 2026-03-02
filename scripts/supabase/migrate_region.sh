#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   SOURCE_DB_URL='...' TARGET_DB_URL='...' ./scripts/supabase/migrate_region.sh

if [[ -z "${SOURCE_DB_URL:-}" || -z "${TARGET_DB_URL:-}" ]]; then
  echo "SOURCE_DB_URL and TARGET_DB_URL are required."
  exit 1
fi

DUMP_FILE="${DUMP_FILE:-supabase.dump}"

echo "[1/4] Creating backup from source..."
pg_dump \
  --format=custom \
  --no-owner \
  --no-privileges \
  "${SOURCE_DB_URL}" > "${DUMP_FILE}"

echo "[2/4] Restoring backup to target..."
pg_restore \
  --clean \
  --if-exists \
  --no-owner \
  --no-privileges \
  --dbname "${TARGET_DB_URL}" \
  "${DUMP_FILE}"

echo "[3/4] Verifying critical table counts..."
psql "${TARGET_DB_URL}" -f scripts/supabase/verify_counts.sql

echo "[4/4] Done."
echo "Next: run storage migration script and rotate runtime secrets."
