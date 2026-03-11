"""
Middleware that decodes the bearer token once and stores auth context on request.state.
"""

from __future__ import annotations

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.auth import get_user_from_bearer_token


class AuthContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request.state.auth_user = None
        request.state.auth_error = None

        authorization = request.headers.get("Authorization", "").strip()
        if authorization.lower().startswith("bearer "):
            token = authorization[7:].strip()
            if token:
                try:
                    request.state.auth_user = get_user_from_bearer_token(token)
                except HTTPException as exc:
                    request.state.auth_error = exc

        return await call_next(request)
