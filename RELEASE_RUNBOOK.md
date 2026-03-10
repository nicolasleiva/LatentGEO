# Release Runbook

This repository uses a strict staging-first release gate.

## Required secrets and runtime config

- `DATABASE_URL`
- `REDIS_URL`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`
- `SECRET_KEY`
- `ENCRYPTION_KEY`
- `WEBHOOK_SECRET`
- `AUTH0_DOMAIN`
- `AUTH0_CLIENT_ID`
- `AUTH0_CLIENT_SECRET`
- `AUTH0_SECRET`
- `AUTH0_API_AUDIENCE`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `NEXT_PUBLIC_API_URL`
- `API_URL`
- `WEB_CONCURRENCY`
- `OPENAPI_DOCS_ENABLED=false`
- `PDF_ALLOW_DETERMINISTIC_FALLBACK=false`
- `SMOKE_BASE_URL`
- `SMOKE_BEARER_TOKEN`
- `PERF_AUTH_EMAIL`
- `PERF_AUTH_PASSWORD`

For live staging certification also provide:

- `LIVE_BASE_URL`
- `LIVE_TARGET_URL`
- `PROD_TEST_URL`
- `PROD_TEST_USER_ID`
- `PROD_TEST_KEYWORDS`
- `LIVE_BEARER_TOKEN` or Auth0 machine credentials

## Local baseline

```powershell
docker compose up -d --build redis backend frontend worker
pnpm --dir frontend type-check
pnpm --dir frontend lint
pnpm --dir frontend test:ci
$env:STRICT_BUILD='1'; pnpm --dir frontend build
$env:DATABASE_URL='sqlite:///:memory:'
$env:CELERY_BROKER_URL='memory://'
$env:CELERY_RESULT_BACKEND='cache+memory://'
pytest -q
```

Automated wrapper:

```powershell
./scripts/release-certify.ps1 -Stage local
```

## Staging certification

```powershell
./scripts/release-certify.ps1 -Stage staging
```

What it runs:

- frontend baseline: `type-check`, `lint`, `test:ci`, `build`
- backend baseline: `pytest -q`
- external smoke: `pytest -q backend/tests/test_release_smoke_external.py`
- Lighthouse auth sweep: `pnpm --dir frontend quality:web:full`
- GEO perf browser run: `pnpm --dir frontend perf:e2e`
- authenticated browser smoke: `pnpm --dir frontend release:smoke:e2e`
- live audit/PDF certification: `pytest -q backend/tests/test_live_plataforma5_agent1_pdf.py -s`

## Health endpoints

- Frontend root: `GET /`
- Backend health: `GET /health`
- Backend ready: `GET /health/ready`
- Backend live: `GET /health/live`
- Webhooks health: `GET /api/v1/webhooks/health`

## Rollback

Docker local:

```powershell
docker compose down
docker compose up -d redis backend frontend worker
```

AWS staging:

- redeploy the previous backend/frontend image tags
- force new deployment on backend and frontend ECS services
- rerun external smoke and authenticated browser smoke before re-opening traffic

## Production gate

Do not promote to production until staging passes with:

- no frontend/backend baseline failures
- no `thresholdFail` in `quality:web:full`
- no 5xx in external smoke or browser smoke
- successful live PDF generation without deterministic fallback
