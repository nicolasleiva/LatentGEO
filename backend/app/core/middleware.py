"""
Middleware de seguridad para producción.
Incluye rate limiting, security headers, trusted hosts, y HTTPS redirect.
"""
import time
import hashlib
import re
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Callable, Dict, Optional, Tuple
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from app.core.logger import get_logger

logger = get_logger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware with sliding window counter.
    Supports different limits for different endpoints.
    """
    
    def __init__(
        self,
        app,
        default_limit: int = 100,  # requests per window
        default_window: int = 60,  # window in seconds
        endpoint_limits: Optional[Dict[str, Tuple[int, int]]] = None,
        trusted_ips: Optional[list] = None
    ):
        super().__init__(app)
        self.default_limit = default_limit
        self.default_window = default_window
        self.endpoint_limits = endpoint_limits or {}
        self.trusted_ips = trusted_ips or ["127.0.0.1", "::1"]
        
        # Rate limit storage: {client_key: [(timestamp, count)]}
        self.rate_limits: Dict[str, list] = defaultdict(list)
        self.last_cleanup = time.time()
    
    def _get_client_key(self, request: Request) -> str:
        """Get unique client identifier (IP + optional user)"""
        # Get real IP (considering proxies)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"
        
        # Hash for privacy
        return hashlib.sha256(client_ip.encode()).hexdigest()[:16]
    
    def _cleanup_old_entries(self, current_time: float):
        """Remove expired rate limit entries"""
        if current_time - self.last_cleanup < 60:  # Cleanup every minute
            return
        
        max_window = max([w for _, w in self.endpoint_limits.values()] + [self.default_window])
        cutoff = current_time - max_window
        
        for key in list(self.rate_limits.keys()):
            self.rate_limits[key] = [
                (ts, count) for ts, count in self.rate_limits[key] 
                if ts > cutoff
            ]
            if not self.rate_limits[key]:
                del self.rate_limits[key]
        
        self.last_cleanup = current_time
    
    def _get_limit_for_path(self, path: str) -> Tuple[int, int]:
        """Get rate limit and window for specific path"""
        # Check exact matches first
        if path in self.endpoint_limits:
            return self.endpoint_limits[path]
        
        # Check prefix matches
        for endpoint, limits in self.endpoint_limits.items():
            if path.startswith(endpoint):
                return limits
        
        return (self.default_limit, self.default_window)
    
    def _check_rate_limit(self, client_key: str, path: str, current_time: float) -> Tuple[bool, int, int]:
        """
        Check if request is within rate limit.
        Returns: (is_allowed, remaining, reset_time)
        """
        limit, window = self._get_limit_for_path(path)
        window_start = current_time - window
        
        # Count requests in current window
        entries = self.rate_limits[client_key]
        valid_entries = [(ts, count) for ts, count in entries if ts > window_start]
        request_count = sum(count for _, count in valid_entries)
        
        # Update entries
        self.rate_limits[client_key] = valid_entries + [(current_time, 1)]
        
        remaining = max(0, limit - request_count - 1)
        reset_time = int(window_start + window)
        
        if request_count >= limit:
            return (False, 0, reset_time)
        
        return (True, remaining, reset_time)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for health checks and SSE only
        if request.url.path in ["/health", "/api/health", "/"] or "/sse/" in request.url.path:
            return await call_next(request)
        
        # Skip for trusted IPs
        client_host = request.client.host if request.client else "unknown"
        if client_host in self.trusted_ips:
            return await call_next(request)
        
        current_time = time.time()
        self._cleanup_old_entries(current_time)
        
        client_key = self._get_client_key(request)
        
        # Use more permissive rate limit only for polling-style audit GET endpoints.
        path_for_limit = request.url.path
        is_polling_get = bool(
            request.method == "GET"
            and re.fullmatch(
                r"/api/audits/\d+(?:/(?:pages|competitors|report|fix_plan|status))?",
                request.url.path,
            )
        )
        if is_polling_get:
            path_for_limit = "/api/audits"
        elif request.method == "POST" and request.url.path.endswith("/generate-pdf"):
            path_for_limit = "/api/audits/generate-pdf"
        elif request.method == "POST" and (
            request.url.path.endswith("/run-pagespeed")
            or request.url.path.endswith("/pagespeed")
        ):
            path_for_limit = "/api/audits/run-pagespeed"
        
        is_allowed, remaining, reset_time = self._check_rate_limit(
            client_key, path_for_limit, current_time
        )
        
        if not is_allowed:
            logger.warning(f"Rate limit exceeded for client {client_key}: {request.url.path}")
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please slow down."},
                headers={
                    "X-RateLimit-Limit": str(self._get_limit_for_path(path_for_limit)[0]),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_time),
                    "Retry-After": str(reset_time - int(current_time))
                }
            )
        
        response = await call_next(request)
        
        # Add rate limit headers to response (use the same path_for_limit logic)
        limit, window = self._get_limit_for_path(path_for_limit)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_time)
        
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Add security headers to all responses.
    """
    
    def __init__(self, app, csp_enabled: bool = True, frame_ancestors: str = "'none'"):
        super().__init__(app)
        self.csp_enabled = csp_enabled
        self.frame_ancestors = frame_ancestors
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # Standard Security Headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        
        # HSTS (only in production with HTTPS)
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
        
        # Content Security Policy (CSP)
        if self.csp_enabled:
            csp_directives = [
                "default-src 'self'",
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://apis.google.com",
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
                "font-src 'self' https://fonts.gstatic.com",
                "img-src 'self' data: https: blob:",
                "connect-src 'self' https://api.github.com https://api.hubspot.com https://integrate.api.nvidia.com https://www.googleapis.com",
                f"frame-ancestors {self.frame_ancestors}",
                "form-action 'self'",
                "base-uri 'self'",
                "object-src 'none'"
            ]
            response.headers["Content-Security-Policy"] = "; ".join(csp_directives)
        
        return response


class RequestValidationMiddleware(BaseHTTPMiddleware):
    """
    Validate incoming requests for security issues.
    """
    
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB
    MAX_URL_LENGTH = 2048
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Check URL length
        if len(str(request.url)) > self.MAX_URL_LENGTH:
            return JSONResponse(
                status_code=414,
                content={"detail": "URI too long"}
            )
        
        # Check content length
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.MAX_CONTENT_LENGTH:
            return JSONResponse(
                status_code=413,
                content={"detail": "Request entity too large"}
            )
        
        # Block suspicious patterns in URL
        suspicious_patterns = [
            "../",  # Path traversal
            "..\\",  # Windows path traversal
            "<script",  # XSS attempt
            "javascript:",  # XSS attempt
            "vbscript:",  # XSS attempt
            "data:text/html",  # XSS attempt
        ]
        
        from urllib.parse import unquote
        url_decoded = unquote(str(request.url)).lower()
        
        for pattern in suspicious_patterns:
            if pattern in url_decoded:
                logger.warning(f"Blocked suspicious request: {request.url}")
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Invalid request"}
                )
        
        return await call_next(request)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Log incoming requests for security auditing.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        # Get client IP
        forwarded = request.headers.get("X-Forwarded-For")
        client_ip = forwarded.split(",")[0].strip() if forwarded else (
            request.client.host if request.client else "unknown"
        )
        
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Log request (skip health checks)
        if request.url.path not in ["/health", "/api/health"]:
            logger.info(
                f"{request.method} {request.url.path} "
                f"- {response.status_code} "
                f"- {client_ip} "
                f"- {duration:.3f}s"
            )
        
        # Add timing header
        response.headers["X-Response-Time"] = f"{duration:.3f}s"
        
        return response


def configure_security_middleware(app, settings, enable_rate_limiting: bool = True):
    """
    Configure all security middleware for the application.
    
    Args:
        app: FastAPI application instance
        settings: Application settings
    """
    from starlette.middleware.gzip import GZipMiddleware
    
    # Define endpoint-specific rate limits
    endpoint_limits = {
        # Auth endpoints - stricter limits to prevent brute force
        "/api/auth": (10, 60),  # 10 requests per minute
        
        # Audit creation - moderate limits (POST only)
        "/api/audits": (600, 60),  # 600 requests per minute (10 per second) for polling
        
        # Heavy operations - stricter limits
        "/api/audits/generate-pdf": (10, 60),  # 10 per minute
        "/api/audits/run-pagespeed": (10, 60),  # 10 per minute
        
        # Search endpoints - moderate limits
        "/api/search": (30, 60),  # 30 per minute
        
        # Webhooks - unlimited (internal use)
        "/api/webhooks": (1000, 60),  # Essentially unlimited
        
        # GitHub webhooks - high limit
        "/api/github/webhook": (100, 60),  # 100 per minute
    }
    
    # Get trusted hosts from settings or default
    trusted_hosts = getattr(settings, 'TRUSTED_HOSTS', ["*"])
    if not settings.DEBUG:
        # In production, be more restrictive
        trusted_hosts = getattr(settings, 'TRUSTED_HOSTS', [
            "localhost",
            "127.0.0.1",
            "*.your-domain.com"  # Replace with actual domain
        ])
    
    # Add middleware in reverse order (last added = first executed)
    
    # 1. GZip compression
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    
    # 2. Request logging (for security auditing)
    app.add_middleware(RequestLoggingMiddleware)
    
    # 3. Security headers
    app.add_middleware(
        SecurityHeadersMiddleware,
        csp_enabled=not settings.DEBUG,
        frame_ancestors="'none'"
    )
    
    # 4. Request validation
    app.add_middleware(RequestValidationMiddleware)
    
    # 5. Rate limiting
    if enable_rate_limiting:
        app.add_middleware(
            RateLimitMiddleware,
            default_limit=100,
            default_window=60,
            endpoint_limits=endpoint_limits,
            trusted_ips=["127.0.0.1", "::1"],
        )
    
    # 6. Trusted hosts (in production)
    if not settings.DEBUG and "*" not in trusted_hosts:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=trusted_hosts
        )
    
    # 7. HTTPS redirect (in production)
    if not settings.DEBUG and getattr(settings, 'FORCE_HTTPS', False):
        app.add_middleware(HTTPSRedirectMiddleware)
    
    logger.info("Security middleware configured successfully")
    return app
