"""
Middleware that decodes the bearer token once and stores auth context on request.state.
"""

from __future__ import annotations

from app.core.auth import get_user_from_bearer_token
from app.core.config import _is_development_like_environment, settings
from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware


class AuthContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request.state.auth_user = None
        request.state.auth_error = None
        request.state.legacy_user_id = None

        authorization = request.headers.get("Authorization", "").strip()
        if authorization.lower().startswith("bearer "):
            token = authorization[7:].strip()
            if token:
                try:
                    request.state.auth_user = get_user_from_bearer_token(token)
                except HTTPException as exc:
                    request.state.auth_error = exc
        elif settings.DEBUG or (
            bool(settings.ENVIRONMENT)
            and _is_development_like_environment(settings.ENVIRONMENT)
        ):
            legacy_user_id = request.headers.get("X-User-ID", "").strip()
            if legacy_user_id:
                # Test/internal fallback only. Production rate-limit identity must
                # come from validated bearer auth, not a client-supplied header.
                request.state.legacy_user_id = legacy_user_id

        return await call_next(request)
