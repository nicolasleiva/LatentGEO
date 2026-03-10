# LatentGEO

Plataforma full-stack para auditorias SEO/GEO.

## Stack
- Backend: FastAPI + SQLAlchemy + Celery
- Frontend: Next.js (App Router)
- Realtime: SSE (FastAPI oficial) con Redis-first + fallback DB
- Infra: Supabase Postgres + Supabase Storage + Redis

## Modos Docker (canonicos)
Solo hay 2 modos soportados:

1. `docker-compose.yml` (estandar)
- Backend/worker sin mounts de codigo
- Frontend en modo produccion
- `API_URL` server-side del frontend: `http://backend:8000`
- `NEXT_PUBLIC_*` para browser local: `http://localhost:8000`

2. `docker-compose.dev.yml` (desarrollo)
- Hot reload backend/frontend
- Mounts de codigo

## Arranque rapido

### Estandar
```bash
docker compose up --build -d
```

### Desarrollo
```bash
docker compose -f docker-compose.dev.yml up --build
```

URLs locales:
- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`
- Docs: `http://localhost:8000/docs`

## Realtime: SSE vs Webhooks
- `SSE`: progreso en vivo para la UI (dashboard de auditoria).
- `webhooks`: integraciones externas entrantes/salientes.

No son excluyentes. SSE resuelve UX en tiempo real; webhooks resuelven automatizaciones externas.

## Variables clave nuevas
Backend:
- `SSE_SOURCE=redis|db` (default `redis`)
- `SSE_FALLBACK_DB_INTERVAL_SECONDS=10`
- `SSE_HEARTBEAT_SECONDS=30`
- `SSE_RETRY_MS=5000`
- `DB_POOL_PRE_PING=false` (recomendado con pooler de Supabase)

Frontend/Compose:
- `API_URL=http://backend:8000` (server-side en contenedor)
- `NEXT_PUBLIC_API_URL=http://localhost:8000`

## Documentacion relacionada
- `QUICK_START.md`
- `START_HERE.md`
- `ENVIRONMENT_SETUP.md`
- `MIGRATION_SUPABASE.md`
- `docker-commands.txt`
