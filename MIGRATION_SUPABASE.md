# Supabase Region Migration Runbook

Objetivo: mover DB + Storage a una region cercana, con cutover controlado y rollback.

## Pre-check
- Crear proyecto destino en region objetivo.
- Confirmar acceso a DB origen/destino y claves de Storage.
- Preparar ventana con freeze de escrituras.

## Backup / Restore DB

```bash
pg_dump --format=custom --no-owner --no-privileges "$SOURCE_DB_URL" > supabase.dump
pg_restore --clean --if-exists --no-owner --no-privileges --dbname "$TARGET_DB_URL" supabase.dump
```

## Verificacion de tablas criticas

```sql
SELECT 'audits' AS table_name, count(*) FROM audits
UNION ALL
SELECT 'reports', count(*) FROM reports
UNION ALL
SELECT 'audited_pages', count(*) FROM audited_pages
UNION ALL
SELECT 'competitors', count(*) FROM competitors;
```

## Storage (`audit-reports`)
- Copiar objetos del bucket origen al destino.
- Validar por objeto: path, tamano y checksum.

## Rotacion de variables
Actualizar en runtime, CI y secretos:
- `DATABASE_URL`
- `SUPABASE_URL`
- `SUPABASE_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_JWT_SECRET`

## Cutover
1. Deploy en staging y validar SSE/reportes/webhooks.
2. Activar variables del proyecto destino en produccion.
3. Redeploy.
4. Monitorear 24h (latencia, error rate, reconexiones SSE, fallback polling).

## Rollback
1. Restaurar variables del proyecto Supabase anterior.
2. Redeploy inmediato.
3. Mantener evidencia de divergencia para reconciliacion posterior.

## Compose soportado
- `docker-compose.yml` (estandar)
- `docker-compose.dev.yml` (desarrollo)
