# API Reference (LatentGEO)

## Base URLs
- Legacy: `http://localhost:8000/api`
- Versioned: `http://localhost:8000/api/v1`

Both prefixes expose the same protected business routes.

## Authentication
Most API routes require JWT bearer auth.

Use:

```http
Authorization: Bearer <token>
```

JWT claims expected by backend:
- `sub` (required): internal user id.
- `email` or `user_email` (optional): user email for ownership checks.

Common auth/authorization responses:
- `401`: missing, invalid, or expired token.
- `403`: cross-user access denied, or legacy ownerless connection blocked in production.

## Ownership and Legacy Policy
GitHub and HubSpot connections are user-owned (`owner_user_id`, `owner_email`).

- Production (`DEBUG=false`): ownerless legacy rows are blocked (`403`).
- Debug (`DEBUG=true`): first authenticated access auto-claims legacy ownerless rows.

## OAuth Security Contract
GitHub and HubSpot OAuth now require an authenticated user for both start and callback.

- `/auth-url` returns `{ "url": "...", "state": "..." }`.
- `state` is signed and time-limited (default 10 minutes).
- Callback rejects invalid state (`400`) or user mismatch (`401`).

Callback payload format:

```json
{
  "code": "oauth_code",
  "state": "signed_state"
}
```

## Protected vs Public Endpoints

### Public Endpoints
- `GET /health`
- `GET /health/ready`
- `GET /health/live`
- `POST /api/github/webhook` and `POST /api/v1/github/webhook` (signature-validated)
- `POST /api/webhooks/github/incoming` and `POST /api/v1/webhooks/github/incoming` (signature-validated if configured)
- `POST /api/webhooks/hubspot/incoming` and `POST /api/v1/webhooks/hubspot/incoming`
- `GET /api/webhooks/health` and `GET /api/v1/webhooks/health`

### HubSpot Endpoints (Bearer Required)
- `GET /api/hubspot/auth-url`
- `POST /api/hubspot/callback`
- `GET /api/hubspot/connections`
- `POST /api/hubspot/sync/{connection_id}`
- `GET /api/hubspot/pages/{connection_id}`
- `POST /api/hubspot/rollback/{change_id}`
- `GET /api/hubspot/recommendations/{audit_id}`
- `POST /api/hubspot/apply-recommendations`

Same set is available under `/api/v1/hubspot/*`.

### GitHub Endpoints (Bearer Required)
- `GET /api/github/auth-url`
- `GET /api/github/oauth/authorize`
- `POST /api/github/callback`
- `GET /api/github/connections`
- `POST /api/github/sync/{connection_id}`
- `GET /api/github/repos/{connection_id}`
- `GET /api/github/repositories/{connection_id}`
- `POST /api/github/analyze/{connection_id}/{repo_id}`
- `GET /api/github/prs/{repo_id}`
- `POST /api/github/audit-blogs/{connection_id}/{repo_id}`
- `POST /api/github/create-blog-fixes-pr/{connection_id}/{repo_id}`
- `POST /api/github/audit-blogs-geo/{connection_id}/{repo_id}`
- `POST /api/github/create-geo-fixes-pr/{connection_id}/{repo_id}`
- `POST /api/github/create-auto-fix-pr/{connection_id}/{repo_id}`
- `POST /api/github/create-pr`
- `GET /api/github/fix-inputs/{audit_id}`
- `POST /api/github/fix-inputs/{audit_id}`
- `POST /api/github/fix-inputs/chat/{audit_id}`

Same set is available under `/api/v1/github/*`.

## Health Semantics
`GET /health` returns:
- `200` when `status` is `healthy` or `degraded`.
- `503` only when `status` is `unhealthy`.

Typical payload:

```json
{
  "status": "degraded",
  "services": {
    "database": "connected",
    "redis": "disconnected"
  }
}
```

## Examples

### Get OAuth URL (Authenticated)
```bash
curl -s http://localhost:8000/api/github/auth-url \
  -H "Authorization: Bearer $TOKEN"
```

Response:

```json
{
  "url": "https://github.com/login/oauth/authorize?...",
  "state": "eyJhbGciOiJIUzI1NiIs..."
}
```

### OAuth Callback (Authenticated + state)
```bash
curl -s -X POST http://localhost:8000/api/github/callback \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"code":"oauth_code","state":"signed_state"}'
```

### Cross-user Access Rejected
```bash
curl -s http://localhost:8000/api/hubspot/pages/<connection_id_of_other_user> \
  -H "Authorization: Bearer $TOKEN"
```

Expected:
- `403` when connection does not belong to current user.

## HTTP Status Codes Used Frequently
- `200` OK
- `201` Created
- `400` Invalid request or invalid OAuth state
- `401` Missing/invalid credentials or OAuth state-user mismatch
- `403` Forbidden by ownership/legacy policy
- `404` Resource not found
- `409` Conflict (for active PDF generation lock)
- `422` Validation errors (for example, missing required fix inputs)
- `500` Internal server error
- `503` Unhealthy service state

## OpenAPI + Frontend Types
After backend contract changes, regenerate frontend API artifacts:

```bash
pnpm --dir frontend run api:generate-types
pnpm --dir frontend run type-check
```

Generated files:
- `frontend/lib/api-client/openapi.json`
- `frontend/lib/api-client/schema.ts`
