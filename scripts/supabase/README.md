# Supabase Region Migration Scripts

## 1) Database backup/restore + count verification
```bash
SOURCE_DB_URL='...' TARGET_DB_URL='...' ./scripts/supabase/migrate_region.sh
```

## 2) Storage bucket migration (`audit-reports`)
```bash
SOURCE_SUPABASE_URL='https://<source-ref>.supabase.co' \
SOURCE_SUPABASE_SERVICE_ROLE_KEY='...' \
TARGET_SUPABASE_URL='https://<target-ref>.supabase.co' \
TARGET_SUPABASE_SERVICE_ROLE_KEY='...' \
SOURCE_BUCKET='audit-reports' \
TARGET_BUCKET='audit-reports' \
python scripts/supabase/migrate_storage_bucket.py
```

Optional:
- `PREFIX='reports/'` to migrate only a folder.

## Notes
- Run during maintenance window after write freeze.
- Rotate runtime secrets only after DB + Storage verification succeeds.
