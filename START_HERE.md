# Start Here

## Objetivo
Guia de navegacion rapida para operar el proyecto con la arquitectura actual.

## Orden recomendado
1. `README.md` (vision general)
2. `QUICK_START.md` (arranque rapido)
3. `ENVIRONMENT_SETUP.md` (variables y configuracion)
4. `MIGRATION_SUPABASE.md` (cutover de region)

## Compose soportados
- `docker-compose.yml` -> modo estandar
- `docker-compose.dev.yml` -> modo desarrollo

No usar archivos compose deprecados.

## Componentes clave
- Backend API: `backend/app/main.py`
- SSE: `backend/app/api/routes/sse.py`
- Publicacion de progreso: `backend/app/services/audit_service.py`
- SSE proxy frontend: `frontend/app/api/sse/audits/[auditId]/progress/route.ts`
- Hook frontend SSE + fallback: `frontend/hooks/useAuditSSE.ts`
- Webhooks: `backend/app/api/routes/webhooks.py`

## Modelo realtime
- `SSE`: estado live de auditorias para UI.
- `Webhooks`: notificaciones para terceros.

## Validaciones basicas
```bash
docker compose config
docker compose -f docker-compose.dev.yml config
```

```bash
pytest -q backend/tests/test_sse_auth_contract.py
```
