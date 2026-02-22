# Frontend Modernization Notes (LatentGEO)

## What changed
- Runtime upgraded to `Next.js 16` + `React 19`.
- Styling pipeline upgraded to `Tailwind CSS 4`.
- Unit/integration testing migrated from `Jest` to `Vitest`.
- Added typed API generation from FastAPI OpenAPI:
  - `frontend/lib/api-client/openapi.json`
  - `frontend/lib/api-client/schema.ts`
  - `frontend/lib/api-client/*`
- Added `TanStack Query` as server-state layer.
- Moved locale routing to a shared helper (`withLocale`) and enforced EN-first redirects.
- Replaced legacy `middleware.ts` with `proxy.ts` for Next.js 16.
- Added analytics abstraction (`AnalyticsProvider`) to avoid provider lock-in.
- Added environment normalization via `frontend/lib/env.ts`.

## New commands
From `frontend/`:

```bash
pnpm run api:generate-types
pnpm run type-check
pnpm run lint
pnpm run test:ci
pnpm run build
```

## API typed client workflow
1. Backend OpenAPI schema is generated from FastAPI app factory.
2. Script writes `openapi.json`.
3. `openapi-typescript` generates `schema.ts`.
4. `openapi-fetch` client in `lib/api-client/client.ts` is used by typed modules.

When backend contracts change, re-run:

```bash
pnpm run api:generate-types
```

## EN-first routing strategy
- Active locale: `/en`.
- Legacy locale: `/es` is redirected to `/en`.
- Internal navigation should use `withLocale(pathname, href)` from `frontend/lib/locale-routing.ts`.

## Deployment portability
- Primary strategy: OCI container build (`Dockerfile.frontend` + `next build --webpack`).
- Provider adapters remain optional (Cloudflare/Vercel).
- Avoid provider-specific logic in page/components; keep it in adapters/config.

## Migration status
- Core+marketing surfaces are updated to locale-safe navigation.
- Home and Audits now use TanStack Query with typed API wrappers.
- Legacy `frontend/lib/api.ts` is deprecated and should be phased out screen-by-screen.
