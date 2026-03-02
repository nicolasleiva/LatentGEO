# Environment Setup

## 1. Archivo `.env` (raiz)
Partir de `.env.example` y completar secretos reales.

## 2. Variables criticas

### Base de datos (Supabase)
```bash
DATABASE_URL=postgresql+psycopg2://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres?sslmode=require
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=5
DB_POOL_TIMEOUT=15
DB_POOL_RECYCLE=900
DB_CONNECT_TIMEOUT_SECONDS=5
DB_POOL_PRE_PING=false
```

### Redis / Celery
```bash
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1
```

### SSE
```bash
SSE_SOURCE=redis
SSE_FALLBACK_DB_INTERVAL_SECONDS=10
SSE_HEARTBEAT_SECONDS=30
SSE_RETRY_MS=5000
```

### Frontend URLs
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
API_URL=http://backend:8000
```

## 3. Modos de ejecucion

### Estandar
```bash
docker compose up --build -d
```

### Desarrollo
```bash
docker compose -f docker-compose.dev.yml up --build
```

## 4. Supabase region migration (runbook resumido)
1. Crear proyecto destino en region cercana.
2. Congelar escrituras en origen durante ventana.
3. Backup DB:
```bash
pg_dump --format=custom --no-owner --no-privileges "$SOURCE_DB_URL" > supabase.dump
```
4. Restore DB:
```bash
pg_restore --clean --if-exists --no-owner --no-privileges --dbname "$TARGET_DB_URL" supabase.dump
```
5. Migrar bucket `audit-reports` (objetos + validacion checksum/tamano).
6. Verificar conteos: `audits`, `reports`, `audited_pages`, `competitors`.
7. Rotar secrets/URLs de runtime y CI/CD.
8. Monitorear 24h y mantener rollback listo.

## 5. SSE vs Webhooks
- SSE: realtime para dashboard.
- Webhooks: integraciones externas.

## 6. Troubleshooting rapido
- SSE con fallback alto: revisar Redis, proxy SSE frontend y `SSE_SOURCE`.
- Latencia DB alta: validar region Supabase y pooler URL.
- Saturacion conexiones: mantener `DB_POOL_SIZE=5`, `DB_MAX_OVERFLOW=5` al inicio.
