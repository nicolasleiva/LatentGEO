# Web Quality Full Sweep

This project includes an authenticated full-route Lighthouse sweep for frontend quality gates.

## Command

```bash
pnpm --dir frontend run quality:web:full
```

## Required environment variables

- `PERF_BASE_URL`: frontend base URL to audit (example: `https://app.example.com`)
- `PERF_AUDIT_ID`: valid audit id used for dynamic routes
- `PERF_AUTH_EMAIL`: test account email
- `PERF_AUTH_PASSWORD`: test account password
- `NEXT_PUBLIC_AUTH0_API_AUDIENCE`: required audience for frontend token helper
- `NEXT_PUBLIC_AUTH0_API_SCOPES`: required scopes for frontend token helper

## Optional variables

- `LH_CHROME_PORT`: Chrome DevTools port for Lighthouse (default `9222`)

## Outputs

Artifacts are generated under `artifacts/lighthouse-full-auth/`:

- route-level HTML and JSON Lighthouse reports
- `lighthouse-full-summary-<timestamp>.json`
- `lighthouse-full-summary-<timestamp>.csv`
- `lighthouse-full-aggregate-<timestamp>.json`

## Gate thresholds

- `public`: `performance>=90`, `accessibility>=95`, `bestPractices>=95`, `seo>=95`
- `internal-auth`: `performance>=85`, `accessibility>=95`, `bestPractices>=95` (`seo` is informative)
