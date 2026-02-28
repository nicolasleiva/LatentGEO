"""
JWT authentication for API access.

Production path:
- Auth0 Access Token validation (RS256 + JWKS + issuer/audience checks).

Test-only compatibility:
- Internal HS256 tokens are accepted only in test contexts to keep unit tests stable.
"""

from __future__ import annotations

import json
import os
import threading
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import httpx
import jwt
from app.core.config import settings
from app.core.logger import get_logger
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer

# HTTPAuthorizationCredentials is the correct name in newer FastAPI versions
try:
    from fastapi.security import HTTPAuthorizationCredentials
except ImportError:  # pragma: no cover - compatibility fallback
    from fastapi.security import HTTPAuthCredentials as HTTPAuthorizationCredentials

logger = get_logger(__name__)

security = HTTPBearer(auto_error=False)  # Do not auto-raise 403; return explicit 401

AUTH_ERROR_HEADER = "X-Auth-Error-Code"
_ALLOW_INTERNAL_TEST_JWT_ENV = "ALLOW_INTERNAL_TEST_JWT"

_jwks_lock = threading.Lock()
_jwks_cache: dict[str, Any] = {"keys_by_kid": {}, "expires_at": 0.0}
_auth_failure_counts: Counter[str] = Counter()


@dataclass(frozen=True)
class AuthUser:
    """Authenticated user context extracted from JWT."""

    user_id: str
    email: Optional[str] = None


def get_secret_key() -> str:
    """Return internal HS256 secret (legacy/test token helper)."""
    secret = os.getenv("BACKEND_INTERNAL_JWT_SECRET") or os.getenv("SECRET_KEY")
    if not secret:
        raise ValueError("SECRET_KEY/BACKEND_INTERNAL_JWT_SECRET no configurada")
    return secret


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create internal HS256 token.

    Only used by tests and legacy tooling. API auth validation in production
    uses Auth0 RS256 tokens.
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(hours=1)

    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    return jwt.encode(to_encode, get_secret_key(), algorithm="HS256")


def create_refresh_token(data: dict) -> str:
    """Create internal refresh token (legacy/test helper)."""
    return create_access_token(data, expires_delta=timedelta(days=7))


def _normalize_issuer(value: Optional[str]) -> str:
    if not value:
        return ""
    normalized = value.strip()
    if not normalized:
        return ""
    if not normalized.startswith(("http://", "https://")):
        normalized = f"https://{normalized}"
    return normalized.rstrip("/") + "/"


def _expected_issuer() -> str:
    raw = settings.AUTH0_ISSUER_BASE_URL or settings.AUTH0_DOMAIN
    issuer = _normalize_issuer(raw)
    if not issuer:
        raise _auth_exception(
            "jwks_unavailable",
            "Auth0 issuer no configurado",
            context={},
        )
    return issuer


def _expected_audience() -> str:
    audience = (settings.AUTH0_API_AUDIENCE or "").strip()
    if not audience:
        raise _auth_exception(
            "invalid_audience",
            "Auth0 API audience no configurado",
            context={},
        )
    return audience


def _is_test_context() -> bool:
    if (settings.ENVIRONMENT or "").lower() == "test":
        return True
    if os.getenv("PYTEST_CURRENT_TEST"):
        return True
    return os.getenv(_ALLOW_INTERNAL_TEST_JWT_ENV, "").lower() == "true"


def _extract_token_context(token: str) -> dict[str, Any]:
    context: dict[str, Any] = {}
    try:
        header = jwt.get_unverified_header(token)
        context["kid"] = header.get("kid")
        context["alg"] = header.get("alg")
    except Exception:
        context["kid"] = None
        context["alg"] = None

    try:
        claims = jwt.decode(
            token,
            options={
                "verify_signature": False,
                "verify_exp": False,
                "verify_aud": False,
                "verify_iss": False,
            },
        )
    except Exception:
        claims = {}

    context["sub"] = claims.get("sub")
    context["iss"] = claims.get("iss")
    context["aud"] = claims.get("aud")
    return context


def _record_auth_failure(
    reason: str,
    context: dict[str, Any],
    *,
    issuer_expected: Optional[str] = None,
    issuer_got: Optional[str] = None,
) -> None:
    _auth_failure_counts[reason] += 1
    logger.warning(
        "auth_rejected",
        error_code=reason,
        count=_auth_failure_counts[reason],
        sub=context.get("sub"),
        kid=context.get("kid"),
        iss=context.get("iss"),
        aud=context.get("aud"),
        issuer_expected=issuer_expected,
        issuer_got=issuer_got,
    )


def _auth_exception(
    reason: str,
    detail: str,
    *,
    context: dict[str, Any],
    issuer_expected: Optional[str] = None,
    issuer_got: Optional[str] = None,
) -> HTTPException:
    _record_auth_failure(
        reason,
        context,
        issuer_expected=issuer_expected,
        issuer_got=issuer_got,
    )
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer", AUTH_ERROR_HEADER: reason},
    )


def get_auth_failure_metrics() -> dict[str, int]:
    """Exposes in-memory auth failure counters for diagnostics/tests."""
    return dict(_auth_failure_counts)


def _fetch_jwks(issuer: str) -> dict[str, dict[str, Any]]:
    jwks_url = f"{issuer}.well-known/jwks.json"
    timeout_ms = max(1, int(settings.AUTH0_JWKS_FETCH_TIMEOUT_MS))
    timeout = timeout_ms / 1000.0

    with httpx.Client(timeout=timeout) as client:
        response = client.get(jwks_url)
        response.raise_for_status()
        payload = response.json()

    keys = payload.get("keys")
    if not isinstance(keys, list):
        raise ValueError("Invalid JWKS payload: missing keys list")

    keys_by_kid: dict[str, dict[str, Any]] = {}
    for key in keys:
        if not isinstance(key, dict):
            continue
        kid = key.get("kid")
        if not isinstance(kid, str) or not kid.strip():
            continue
        if key.get("kty") != "RSA":
            continue
        keys_by_kid[kid] = key

    if not keys_by_kid:
        raise ValueError("JWKS payload contains no usable RSA keys")

    return keys_by_kid


def _refresh_jwks_cache(issuer: str) -> dict[str, dict[str, Any]]:
    keys_by_kid = _fetch_jwks(issuer)
    ttl_seconds = max(1, int(settings.AUTH0_JWKS_CACHE_TTL_SECONDS))
    expires_at = time.time() + ttl_seconds

    with _jwks_lock:
        _jwks_cache["keys_by_kid"] = keys_by_kid
        _jwks_cache["expires_at"] = expires_at

    return keys_by_kid


def _get_jwk_for_kid(kid: str, issuer: str) -> Optional[dict[str, Any]]:
    now = time.time()
    with _jwks_lock:
        keys_by_kid = dict(_jwks_cache.get("keys_by_kid") or {})
        expires_at = float(_jwks_cache.get("expires_at") or 0.0)

    # Fast path: valid cache hit.
    if expires_at > now and kid in keys_by_kid:
        return keys_by_kid[kid]

    # 1st fetch path (expired/missing cache).
    keys_by_kid = _refresh_jwks_cache(issuer)
    if kid in keys_by_kid:
        return keys_by_kid[kid]

    # 2nd fetch path: unknown kid refresh on-demand (key rotation).
    keys_by_kid = _refresh_jwks_cache(issuer)
    return keys_by_kid.get(kid)


def _decode_internal_test_token(token: str, context: dict[str, Any]) -> Dict[str, Any]:
    try:
        return jwt.decode(
            token,
            get_secret_key(),
            algorithms=["HS256"],
        )
    except jwt.ExpiredSignatureError as exc:
        raise _auth_exception(
            "expired_token",
            "Token expirado",
            context=context,
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise _auth_exception(
            "invalid_signature",
            "Token inválido",
            context=context,
        ) from exc


def _decode_auth0_access_token(token: str, context: dict[str, Any]) -> Dict[str, Any]:
    expected_issuer = _expected_issuer()
    expected_audience = _expected_audience()

    got_issuer = _normalize_issuer(context.get("iss"))
    if got_issuer != expected_issuer:
        raise _auth_exception(
            "invalid_issuer",
            "Issuer inválido",
            context=context,
            issuer_expected=expected_issuer,
            issuer_got=got_issuer or None,
        )

    kid = context.get("kid")
    if not isinstance(kid, str) or not kid.strip():
        raise _auth_exception(
            "invalid_signature",
            "Token inválido: faltante kid",
            context=context,
        )

    try:
        jwk = _get_jwk_for_kid(kid, expected_issuer)
    except httpx.HTTPError as exc:
        raise _auth_exception(
            "jwks_unavailable",
            "No se pudo obtener JWKS de Auth0",
            context=context,
        ) from exc
    except Exception as exc:
        raise _auth_exception(
            "jwks_unavailable",
            "Error validando JWKS de Auth0",
            context=context,
        ) from exc

    if not jwk:
        raise _auth_exception(
            "jwks_unavailable",
            "No se encontró clave JWKS para kid",
            context=context,
        )

    try:
        public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk))
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=expected_audience,
            issuer=expected_issuer,
            options={"require": ["exp", "sub", "iss", "aud"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise _auth_exception(
            "expired_token",
            "Token expirado",
            context=context,
        ) from exc
    except jwt.InvalidAudienceError as exc:
        raise _auth_exception(
            "invalid_audience",
            "Audience inválida",
            context=context,
        ) from exc
    except jwt.InvalidIssuerError as exc:
        raise _auth_exception(
            "invalid_issuer",
            "Issuer inválido",
            context=context,
            issuer_expected=expected_issuer,
            issuer_got=got_issuer or None,
        ) from exc
    except jwt.InvalidSignatureError as exc:
        raise _auth_exception(
            "invalid_signature",
            "Firma inválida",
            context=context,
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise _auth_exception(
            "invalid_signature",
            "Token inválido",
            context=context,
        ) from exc

    expected_client_id = (settings.AUTH0_EXPECTED_CLIENT_ID or "").strip()
    if expected_client_id:
        client_id = payload.get("azp") or payload.get("client_id")
        if client_id != expected_client_id:
            raise _auth_exception(
                "invalid_client",
                "Client ID no autorizado",
                context=context,
            )

    return payload


def _decode_token_payload(token: str) -> Dict[str, Any]:
    """
    Decode and validate JWT payload.

    Production:
    - validates Auth0 RS256 access token.

    Tests:
    - allows internal HS256 token to preserve unit-test flows.
    """
    context = _extract_token_context(token)

    if _is_test_context() and context.get("alg") == "HS256":
        return _decode_internal_test_token(token, context)

    return _decode_auth0_access_token(token, context)


def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """Validate Bearer token and return `sub`."""
    if credentials is None:
        raise _auth_exception(
            "missing_token",
            "Token no proporcionado",
            context={},
        )

    payload = _decode_token_payload(credentials.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise _auth_exception(
            "missing_sub",
            "Token inválido: sin sub",
            context=_extract_token_context(credentials.credentials),
        )
    return str(user_id)


def get_user_from_bearer_token(token: str) -> AuthUser:
    """Build AuthUser from a raw Bearer token string."""
    payload = _decode_token_payload(token)
    user_id = payload.get("sub")
    if not user_id:
        raise _auth_exception(
            "missing_sub",
            "Token inválido: faltante sub",
            context=_extract_token_context(token),
        )

    email = payload.get("email") or payload.get("user_email")
    if isinstance(email, str):
        email = email.strip().lower() or None
    else:
        email = None

    return AuthUser(user_id=str(user_id), email=email)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> AuthUser:
    """Dependency that returns the current authenticated user context."""
    if credentials is None:
        raise _auth_exception(
            "missing_token",
            "Token no proporcionado",
            context={},
        )

    return get_user_from_bearer_token(credentials.credentials)
