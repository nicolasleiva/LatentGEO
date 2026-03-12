"""
Shared rate limiting policy helpers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.request_identity import get_client_ip
from fastapi import Request

_AUDIT_READ_PATH_RE = re.compile(
    r"^/api/v1/audits/\d+"
    r"(?:/(?:overview|pages|competitors|report|fix_plan|status|progress|diagnostics))?$"
)


@dataclass(frozen=True)
class RateLimitPolicy:
    bucket: str
    limit: int
    window: int


def is_rate_limit_exempt(path: str) -> bool:
    return path in {
        "/",
        "/health",
        "/health/live",
        "/health/ready",
        "/docs",
        "/openapi.json",
    }


def resolve_rate_limit_policy(request: Request, settings) -> RateLimitPolicy:
    rate_limit_default = int(
        getattr(settings, "RATE_LIMIT_DEFAULT", getattr(settings, "default_limit", 100))
    )
    rate_limit_auth = int(
        getattr(settings, "RATE_LIMIT_AUTH", getattr(settings, "default_limit", 10))
    )
    rate_limit_heavy = int(
        getattr(settings, "RATE_LIMIT_HEAVY", getattr(settings, "default_limit", 5))
    )
    path = request.url.path
    method = request.method.upper()

    if path.startswith("/api/v1/auth"):
        return RateLimitPolicy("auth", rate_limit_auth, 60)

    if method == "POST" and path.endswith("/generate-pdf"):
        return RateLimitPolicy("pdf_generate", rate_limit_heavy, 60)

    if method == "GET" and path.endswith("/pdf-status"):
        return RateLimitPolicy("pdf_status", rate_limit_default, 60)

    if method == "POST" and (
        path.endswith("/run-pagespeed") or path.endswith("/pagespeed")
    ):
        return RateLimitPolicy("pagespeed_generate", rate_limit_heavy, 60)

    if method == "GET" and path.endswith("/pagespeed-status"):
        return RateLimitPolicy("pagespeed_status", rate_limit_default, 60)

    if method == "GET" and path.endswith("/artifacts-status"):
        return RateLimitPolicy("artifacts_status", rate_limit_default, 60)

    if path.startswith("/api/v1/webhooks"):
        return RateLimitPolicy("webhooks", 1000, 60)

    if path.startswith("/api/v1/github/webhook"):
        return RateLimitPolicy("github_webhook", 100, 60)

    if method == "GET" and _AUDIT_READ_PATH_RE.fullmatch(path):
        return RateLimitPolicy("audit_read", rate_limit_default, 60)

    return RateLimitPolicy("default", rate_limit_default, 60)


def resolve_rate_limit_identity(request: Request) -> str:
    auth_user = getattr(request.state, "auth_user", None)
    user_id = getattr(auth_user, "user_id", None)
    if isinstance(user_id, str) and user_id.strip():
        return f"user:{user_id.strip()}"

    legacy_user_id = request.headers.get("X-User-ID")
    if isinstance(legacy_user_id, str) and legacy_user_id.strip():
        return f"user:{legacy_user_id.strip()}"

    client_ip = get_client_ip(request)
    if isinstance(client_ip, str) and client_ip.strip():
        return f"ip:{client_ip.strip()}"

    return "unknown"
