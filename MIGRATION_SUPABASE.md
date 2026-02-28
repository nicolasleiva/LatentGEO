# Supabase Production Runbook (Auth0-only + Supabase DB/Storage)

Este documento describe la configuracion operativa vigente:

- Autenticacion: Auth0-only (frontend y API).
- Base de datos: Supabase Postgres.
- Almacenamiento de artefactos/PDF: Supabase Storage.
- Secretos reales: solo en `.env` local/servidor (nunca en archivos versionados).

## 1. Variables obligatorias en `.env`

```bash
# Supabase DB (recomendado para Docker/WSL: pooler IPv4 en 5432)
DATABASE_URL=postgresql+psycopg2://postgres.<project-ref>:<url-encoded-password>@aws-0-<region>.pooler.supabase.com:5432/postgres?sslmode=require
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=5
DB_POOL_TIMEOUT=15
DB_POOL_RECYCLE=900
DB_CONNECT_TIMEOUT_SECONDS=5

# Supabase Storage
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<service-role-secret>
SUPABASE_STORAGE_BUCKET=audit-reports
AUDIT_LOCAL_ARTIFACTS_ENABLED=false

# Runtime production
ENVIRONMENT=production
DEBUG=False
FORWARDED_ALLOW_IPS=["127.0.0.1","172.18.0.0/16"]
```

Notas:

- Evitar `db.<project-ref>.supabase.co` en contenedor si tu runtime no resuelve IPv6.
- No usar fallback local para PDFs ni artefactos en modo produccion.

## 2. Auth0 contract

El backend solo acepta Access Tokens de Auth0 para API:

- `aud == AUTH0_API_AUDIENCE`
- `scope` minimo esperado: `read:app`
- `iss` valido (tenant Auth0)

Variables principales:

```bash
AUTH0_DOMAIN=<tenant>.auth0.com
AUTH0_ISSUER_BASE_URL=https://<tenant>.auth0.com/
AUTH0_API_AUDIENCE=<api-identifier>
AUTH0_API_SCOPES=read:app
NEXT_PUBLIC_AUTH0_API_AUDIENCE=<api-identifier>
NEXT_PUBLIC_AUTH0_API_SCOPES=read:app
```

## 3. Healthchecks y disponibilidad

- Liveness: `GET /health/live` (sin dependencia dura de DB).
- Readiness: `GET /health/ready` (DB y Redis).
- Compatibilidad: `GET /health` se mantiene.

Para contenedores, usar liveness en healthcheck para evitar reinicios por microcortes de DB.

## 4. PDF y Storage

Flujo esperado:

1. `POST /api/audits/{id}/generate-pdf` genera reporte y guarda `reports.file_path` como `supabase://...`.
2. `GET /api/audits/{id}/download-pdf` devuelve `302` a signed URL de Supabase.
3. Si DB no esta disponible, endpoints devuelven `503` con `error_code=db_unavailable`.

## 5. Docker release

`docker-compose.release.yml` queda orientado a Supabase-only:

- `db` local queda opcional (profile `legacy-local-db`).
- Backend y worker usan `DATABASE_URL` de Supabase.
- Worker con limites para estabilidad de conexiones:
  - `--concurrency=2`
  - `--prefetch-multiplier=1`
  - `--max-tasks-per-child=20`

## 6. Smoke checklist

1. `GET /health/live` -> `200`.
2. `GET /health/ready` -> `200`.
3. Login Auth0 y acceso a rutas privadas.
4. Crear auditoria, completar job y validar registros en Supabase DB.
5. Generar PDF y descargar via signed URL (`302`).
6. Confirmar que no se crean artefactos persistentes locales para nuevas auditorias.
