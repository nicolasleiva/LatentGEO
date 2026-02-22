"""
Signed OAuth state helpers.
"""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import jwt
from fastapi import HTTPException, status

from .auth import AuthUser
from .config import settings


def _normalize_email(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    return normalized or None


def _get_oauth_state_secret() -> str:
    secret = settings.OAUTH_STATE_SECRET or settings.secret_key
    if not secret:
        raise RuntimeError("OAUTH_STATE_SECRET/SECRET_KEY no configurada")
    return secret


def build_oauth_state(provider: str, user: AuthUser) -> str:
    """Create signed OAuth state bound to provider + authenticated user."""
    now = datetime.now(timezone.utc)
    ttl_seconds = max(60, int(settings.OAUTH_STATE_TTL_SECONDS or 600))
    payload = {
        "provider": provider.strip().lower(),
        "sub": user.user_id,
        "email": _normalize_email(user.email),
        "nonce": secrets.token_urlsafe(12),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl_seconds)).timestamp()),
    }
    return jwt.encode(payload, _get_oauth_state_secret(), algorithm="HS256")


def validate_oauth_state(state: str, provider: str, user: AuthUser) -> Dict[str, Any]:
    """
    Validate signed OAuth state and enforce it matches the authenticated user.
    """
    if not state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing OAuth state",
        )

    try:
        payload = jwt.decode(
            state,
            _get_oauth_state_secret(),
            algorithms=["HS256"],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OAuth state expired",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OAuth state",
        )

    expected_provider = provider.strip().lower()
    state_provider = str(payload.get("provider") or "").strip().lower()
    if not state_provider or state_provider != expected_provider:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OAuth state provider mismatch",
        )

    state_sub = str(payload.get("sub") or "").strip()
    if not state_sub or state_sub != user.user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="OAuth state user mismatch",
        )

    state_email = _normalize_email(payload.get("email"))
    user_email = _normalize_email(user.email)
    if state_email and user_email and state_email != user_email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="OAuth state email mismatch",
        )

    return payload
