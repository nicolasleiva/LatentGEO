"""
Rate Limiting Middleware - Protección contra abuse
"""
import time
from collections import defaultdict
from typing import Dict, Tuple

import redis
from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from ..core.config import settings
from ..core.logger import get_logger

logger = get_logger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Production-ready Rate Limiter using Redis.
    Falls back to in-memory if Redis is unavailable.
    """

    def __init__(self, app):
        super().__init__(app)
        self.use_redis = False
        self.redis_client = None
        self.memory_requests: Dict[str, list] = defaultdict(list)
        self.last_cleanup = time.time()
        self.cleanup_interval = 60

        try:
            # Connect to Redis
            self.redis_client = redis.from_url(
                settings.REDIS_URL, decode_responses=True
            )
            self.redis_client.ping()
            self.use_redis = True
            logger.info("Rate Limiter: Using Redis-based strategy")
        except Exception as e:
            logger.warning(
                f"Rate Limiter: Redis unavailable ({e}). Falling back to in-memory strategy."
            )

    def _get_rate_limit(self, path: str) -> Tuple[int, int]:
        if path.startswith("/auth"):
            return (settings.RATE_LIMIT_AUTH, 60)
        elif "/pagespeed" in path or "/generate-pdf" in path:
            return (settings.RATE_LIMIT_HEAVY, 60)
        return (settings.RATE_LIMIT_DEFAULT, 60)

    def _get_client_key(self, request: Request) -> str:
        user_id = request.headers.get("X-User-ID")
        if user_id:
            return f"user:{user_id}"

        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
        else:
            ip = request.client.host if request.client else "unknown"
        return f"ip:{ip}"

    def _check_redis_limit(
        self, key: str, max_requests: int, window: int
    ) -> Tuple[bool, int, int]:
        """Check rate limit using Redis INCR and EXPIRE"""
        try:
            redis_key = f"rate_limit:{key}"
            current_count = self.redis_client.get(redis_key)

            if current_count and int(current_count) >= max_requests:
                ttl = self.redis_client.ttl(redis_key)
                return False, int(current_count), ttl

            # Increment and set TTL if new
            pipe = self.redis_client.pipeline()
            pipe.incr(redis_key)
            pipe.expire(redis_key, window, nx=True)
            results = pipe.execute()

            new_count = results[0]
            ttl = self.redis_client.ttl(redis_key)
            return True, new_count, ttl
        except Exception as e:
            logger.error(f"Redis rate limit error: {e}")
            return True, 1, window  # Allow on Redis failure

    def _check_memory_limit(
        self, key: str, max_requests: int, window: int
    ) -> Tuple[bool, int, int]:
        """Fallback in-memory rate limiting"""
        now = time.time()

        # Cleanup old entries
        if now - self.last_cleanup > self.cleanup_interval:
            for k in list(self.memory_requests.keys()):
                self.memory_requests[k] = [
                    ts for ts in self.memory_requests[k] if now - ts < window
                ]
                if not self.memory_requests[k]:
                    del self.memory_requests[k]
            self.last_cleanup = now

        # Get active requests in window
        self.memory_requests[key] = [
            ts for ts in self.memory_requests[key] if now - ts < window
        ]
        current_count = len(self.memory_requests[key])

        if current_count >= max_requests:
            remaining_time = int(window - (now - self.memory_requests[key][0]))
            return False, current_count, max(0, remaining_time)

        self.memory_requests[key].append(now)
        return True, current_count + 1, window

    async def dispatch(self, request: Request, call_next):
        # Skip rate limit for health, docs, and metrics
        if request.url.path in ["/health", "/docs", "/openapi.json"]:
            return await call_next(request)

        max_requests, window = self._get_rate_limit(request.url.path)
        client_key = self._get_client_key(request)

        if self.use_redis:
            allowed, count, reset_after = self._check_redis_limit(
                client_key, max_requests, window
            )
        else:
            allowed, count, reset_after = self._check_memory_limit(
                client_key, max_requests, window
            )

        if not allowed:
            logger.warning(f"Rate limit exceeded: {client_key} on {request.url.path}")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Rate limit exceeded",
                    "detail": f"Max {max_requests} requests per {window}s.",
                    "retry_after": reset_after,
                },
                headers={"Retry-After": str(reset_after)},
            )

        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(max_requests)
        response.headers["X-RateLimit-Remaining"] = str(max(0, max_requests - count))
        response.headers["X-RateLimit-Reset"] = str(int(time.time() + reset_after))

        return response
