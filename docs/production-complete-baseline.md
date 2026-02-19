# Production Complete Baseline

Date: 2026-02-19
Branch: `hardening/production-complete`

## Scope
- Baseline captured before completing the full remediation.
- Commands were executed from repository root unless noted.

## Frontend Baseline
- `pnpm --dir frontend lint`: pass (1 warning in `frontend/__tests__/app/audit-detail-navigation.test.tsx`).
- `pnpm --dir frontend run format:check`: fail (`frontend/app/[locale]/audits/[id]/page.tsx` not formatted).
- `pnpm --dir frontend run type-check`: pass.
- `pnpm --dir frontend test:ci`: pass (15 suites, 39 tests).
- `pnpm --dir frontend build`: pass.

## Backend Baseline
- `python -m ruff check backend/app backend/tests`: pass.
- `python -m black --check backend`: pass.
- `python -m isort --check-only backend`: pass.
- `python -m mypy backend/app --ignore-missing-imports --show-error-codes`: pass (notes only).
- `python -m bandit -r backend/app -q`: pass (warnings on `# nosec`, no blocking findings).
- `python -m pip_audit -r backend/requirements.txt`: pass (no known vulnerabilities).
- `pytest -q backend/tests`: pass with skips (`208 passed, 37 skipped`).

## Known Gaps At Baseline
- Frontend format gate failing.
- `frontend/tsconfig.tsbuildinfo` local artifact present.
- Root repository contained legacy/garbage versioned files.
- Strict gate did not enforce `skipped == 0`.
- `production-ready.yml` referenced `backend/tests/load_test.py` that did not exist.

