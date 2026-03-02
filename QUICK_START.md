# Quick Start

## 1) Prerrequisitos
- Docker + Docker Compose plugin
- Archivo `.env` en la raiz (usar `.env.example` como base)

## 2) Levantar en modo estandar
```bash
docker compose up --build -d
```

Verificar:
```bash
docker compose ps
curl http://localhost:8000/health
```

## 3) Levantar en modo desarrollo (hot reload)
```bash
docker compose -f docker-compose.dev.yml up --build
```

## 4) URLs
- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`
- API Docs: `http://localhost:8000/docs`

## 5) Realtime esperado
- La UI consume `GET /api/v1/sse/audits/{audit_id}/progress` (via proxy Next.js).
- SSE usa Redis como fuente principal.
- Si Redis no entrega eventos, hay fallback a DB controlado.
- Si SSE falla, el frontend tiene fallback a polling.

## 6) Troubleshooting SSE rapido
1. Validar Redis:
```bash
docker compose logs -f redis
```
2. Validar backend SSE:
```bash
docker compose logs -f backend
```
3. Confirmar variables:
- `SSE_SOURCE=redis`
- `SSE_FALLBACK_DB_INTERVAL_SECONDS=10`
- `SSE_HEARTBEAT_SECONDS=30`
- `SSE_RETRY_MS=5000`

## 7) SSE vs Webhooks
- SSE: actualizacion en tiempo real del dashboard.
- Webhooks: integraciones externas (`/api/v1/webhooks/*`).
