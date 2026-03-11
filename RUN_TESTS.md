# Run Tests and Quality Checks

This document is the current release gate for the repository.

## 1) Install Dependencies

Backend:

```bash
python -m pip install -r backend/requirements.txt
```

Frontend:

```bash
pnpm --dir frontend install
```

## 2) Fast Validation (Recommended)

Run from repository root:

```bash
pnpm --dir frontend lint
pnpm --dir frontend run format:check
pnpm --dir frontend run type-check
pnpm --dir frontend test:ci
pnpm --dir frontend build

python -m ruff check backend/app backend/tests
python -m black --check backend
python -m isort --check-only backend
python -m mypy backend/app --ignore-missing-imports --show-error-codes
python -m bandit -r backend/app -q
python -m pip_audit -r backend/requirements.txt

pytest -q backend/tests -m "not integration and not live"
```

## 3) Security Remediation Regression Suite

Run these focused tests after changing auth/ownership/locks/hardening:

```bash
pytest -q backend/tests/test_security_remediation.py
pytest -q backend/tests/test_pdf_locking.py
pytest -q backend/tests/test_ssl_fallback_flags.py
pytest -q backend/tests/test_github_fix_inputs_api.py
pytest -q backend/tests/test_additional_remediation.py
pytest -q backend/tests/test_security_middleware.py
pytest -q backend/tests/test_rate_limit_middleware.py
pytest -q backend/tests/test_pipeline_service.py -k "now_iso or parse_agent_json_or_raw"
pytest -q backend/tests/test_audit_service.py -k "_save_audit_files or save_page_audit"
```

## 4) API Contract Sync (Backend -> Frontend)

When backend routes or schemas change:

```bash
pnpm --dir frontend run api:generate-types
pnpm --dir frontend run type-check
```

Artifacts updated:
- `frontend/lib/api-client/openapi.json`
- `frontend/lib/api-client/schema.ts`

## 5) External Smoke (Required For Strict Staging/Production Gate)

```bash
SMOKE_BASE_URL=https://your-staging-or-prod-url \
SMOKE_BEARER_TOKEN=machine-or-staging-bearer-token \
pytest -q backend/tests/test_release_smoke_external.py
```

Expected result in strict mode:
- `GET /health` = `200`
- `GET /docs` = `404` unless `SMOKE_ALLOW_OPENAPI_DOCS=1`
- `GET /api/v1/webhooks/health` = `200`
- protected endpoint checks use `SMOKE_BEARER_TOKEN`

## 6) Strict Release Certification

PowerShell wrapper:

```powershell
./scripts/release-certify.ps1 -Stage local
./scripts/release-certify.ps1 -Stage staging
```

Additional staging-only requirements:
- `OPENAPI_DOCS_ENABLED=false`
- `PDF_ALLOW_DETERMINISTIC_FALLBACK=false`
- `WEB_CONCURRENCY` set explicitly
- `PERF_AUTH_EMAIL` and `PERF_AUTH_PASSWORD`
- `LIVE_BEARER_TOKEN` or Auth0 machine credentials for live audit/PDF certification

## 7) Docker/Compose Validation (Additional)

```bash
# Bash/zsh: must fail fast if DB_PASSWORD is unset or empty
DB_PASSWORD= docker compose config

# Bash/zsh: must render config when DB_PASSWORD is defined
DB_PASSWORD=test_password docker compose config

# PowerShell: must fail fast if DB_PASSWORD is unset or empty
$env:DB_PASSWORD=''
docker compose config

# PowerShell: must render config when DB_PASSWORD is defined
$env:DB_PASSWORD='test_password'
docker compose config

# Validate runtime user in backend/worker images
docker build -f Dockerfile.backend -t latentgeo-backend .
docker run --rm latentgeo-backend id

docker build -f Dockerfile.backend.dev -t latentgeo-backend-dev .
docker run --rm latentgeo-backend-dev id
```

## 8) Notes

- Frontend unit tests use Vitest (`pnpm --dir frontend test:ci`), not Jest.
- The canonical backend requirements file is `backend/requirements.txt`.
- If Redis/PostgreSQL are unavailable locally, some startup logs may show degraded dependencies; focused tests use local fixtures and should still run.
