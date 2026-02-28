# Auth0 Dashboard Setup (Auth0-Only + Supabase DB)

This project now uses:
- Auth0 for login/signup (Email/Password + Google)
- Auth0 Access Token for all backend API calls
- Supabase only as database/storage (not as frontend auth provider)

Use this checklist to finish the external dashboard setup.

## 1) Configure Auth0 API (required for backend tokens)

1. Go to `Auth0 Dashboard -> Applications -> APIs -> Create API`.
2. Set:
   - `Name`: `auditor-geo-api` (or your preferred name)
   - `Identifier`: must match `.env` `AUTH0_API_AUDIENCE`
   - `Signing Algorithm`: `RS256`
3. In `Permissions`, create at least:
   - `read:app`
4. (Recommended) Enable RBAC and "Add Permissions in the Access Token".

## 2) Configure Auth0 Application (Regular Web App)

1. Go to `Applications -> Your App -> Settings`.
2. Ensure app type is `Regular Web Application`.
3. Set these URLs (dev example):
   - `Allowed Callback URLs`:
     - `http://localhost:3000/auth/callback`
   - `Allowed Logout URLs`:
     - `http://localhost:3000`
   - `Allowed Web Origins`:
     - `http://localhost:3000`
   - `Allowed Origins (CORS)`:
     - `http://localhost:3000`
4. Save changes.

## 3) Enable login methods

### Email/Password
1. Go to `Authentication -> Database`.
2. Enable `Username-Password-Authentication` for this application.
3. For production:
   - Require email verification.
   - Configure password policy.

### Google
1. Go to `Authentication -> Social -> Google`.
2. Enable Google connection and attach it to your application.
3. Verify Google OAuth credentials in Auth0 are valid.

## 4) Verify env variables in local `.env`

Required:
- `AUTH0_DOMAIN`
- `AUTH0_CLIENT_ID`
- `AUTH0_CLIENT_SECRET`
- `AUTH0_SECRET`
- `APP_BASE_URL`
- `AUTH0_ISSUER_BASE_URL`
- `AUTH0_API_AUDIENCE`
- `AUTH0_API_SCOPES` (default: `read:app`)
- `NEXT_PUBLIC_AUTH0_API_AUDIENCE`
- `NEXT_PUBLIC_AUTH0_API_SCOPES`
- `AUTH0_LOGIN_SCOPES` (default: `openid profile email`)

Optional hardening:
- `AUTH0_EXPECTED_CLIENT_ID`
- `AUTH0_JWKS_CACHE_TTL_SECONDS`
- `AUTH0_JWKS_FETCH_TIMEOUT_MS`

## 5) Runtime checks (after docker up)

1. Legacy sign-in route redirects:
   - `GET http://localhost:3000/signin` -> `302` to `/auth/login`
2. Auth route works:
   - `GET http://localhost:3000/auth/login` -> redirects to Auth0 `/authorize`
3. Backend protected API without token:
   - `GET http://localhost:8000/api/audits` -> `401` with `X-Auth-Error-Code: missing_token`
4. After authenticating in browser:
   - Protected pages load.
   - API calls no longer return `401`.
   - SSE endpoint works with active session.

## 6) If you get 401, map by reason

Backend now returns `X-Auth-Error-Code`:
- `missing_token`: frontend did not send bearer token
- `invalid_audience`: API Identifier mismatch (`AUTH0_API_AUDIENCE`)
- `invalid_issuer`: issuer mismatch (`AUTH0_ISSUER_BASE_URL`)
- `expired_token`: token expired
- `invalid_signature`: bad token signature / malformed token
- `jwks_unavailable`: Auth0 JWKS unavailable or unknown `kid`
- `invalid_client`: `AUTH0_EXPECTED_CLIENT_ID` mismatch
- `missing_sub`: token missing subject

## 7) Production notes

- Use an HTTPS API identifier in production (example: `https://api.yourdomain.com`).
- Keep real credentials only in root `.env` (never in repo templates).
- Prefer a dedicated Supabase project per environment (`dev`, `staging`, `prod`, `ci`).
