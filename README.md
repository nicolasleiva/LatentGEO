# LatentGEO

Full-stack platform for SEO/GEO audits with:
- Backend: FastAPI + SQLAlchemy
- Frontend: Next.js + TypeScript
- Infra: PostgreSQL + Redis (+ optional Celery worker)

## Quick Start (Docker)

```bash
docker compose up --build
```

Default local URLs:
- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`

## Local Development (Without Docker)

Backend:

```bash
python -m pip install -r backend/requirements.txt
python -m backend.main
```

Frontend:

```bash
pnpm --dir frontend install
pnpm --dir frontend dev
```

## Authentication and Security Basics

- Integration endpoints under `/api/github/*` and `/api/hubspot/*` (and `/api/v1/*`) require `Authorization: Bearer <token>`.
- GitHub/HubSpot connections are owner-scoped; cross-user access returns `403`.
- OAuth start/callback now enforce signed `state` validation.
- Public inbound webhooks remain unauthenticated but use signature validation when configured.

See `API_REFERENCE.md` for endpoint-level contract details.

## Health Endpoints

- `GET /health`: `200` for `healthy` and `degraded`, `503` for `unhealthy`.
- `GET /health/ready`: readiness probe for load balancers.
- `GET /health/live`: liveness probe.

## Release Gate

Use:
- `RUN_TESTS.md` for exact quality, security, and test commands.
- `ENVIRONMENT_SETUP.md` for environment variables and provider setup.

Most common commands:

```bash
pnpm --dir frontend lint
pnpm --dir frontend run type-check
pnpm --dir frontend test:ci
python -m ruff check backend/app backend/tests
pytest -q backend/tests -m "not integration and not live"
```

## API Contract Regeneration

When backend schemas/routes change:

```bash
pnpm --dir frontend run api:generate-types
pnpm --dir frontend run type-check
```

Generated files:
- `frontend/lib/api-client/openapi.json`
- `frontend/lib/api-client/schema.ts`

## Project Guides

- `START_HERE.md`
- `ENVIRONMENT_SETUP.md`
- `RUN_TESTS.md`
- `API_REFERENCE.md`
