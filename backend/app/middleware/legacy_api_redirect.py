"""Legacy API redirect middleware for local/debug compatibility only."""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response


class LegacyApiRedirectMiddleware(BaseHTTPMiddleware):
    """
    Redirects legacy /api/* paths to /api/v1/* with HTTP 307.

    Notes:
    - Active only when explicitly enabled from app setup.
    - Excludes /api/v1/* and /api/sse/*.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        if path.startswith("/api/v1/") or path == "/api/v1":
            return await call_next(request)

        if path.startswith("/api/sse/") or path == "/api/sse":
            return await call_next(request)

        if path.startswith("/api/"):
            suffix = path[len("/api/") :]
            target_path = f"/api/v1/{suffix}"
        elif path == "/api":
            target_path = "/api/v1"
        else:
            return await call_next(request)

        redirect_url = target_path
        if request.url.query:
            redirect_url = f"{target_path}?{request.url.query}"

        return RedirectResponse(url=redirect_url, status_code=307)
