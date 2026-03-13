"""
Rate Limiting Middleware - Protección contra abuse
"""

import time
from collections import defaultdict
from typing import Dict, Tuple

import redis
from app.core.rate_limit_policy import (
    is_rate_limit_exempt,
    resolve_rate_limit_identity,
    resolve_rate_limit_policy,
)
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
        self.redis_retry_cooldown = max(
            1, int(getattr(settings, "RATE_LIMIT_REDIS_RETRY_COOLDOWN_SECONDS", 30))
        )
        self.next_redis_retry_at = 0.0

        if settings.REDIS_URL:
            self._connect_redis()
        else:
            logger.warning(
                "Rate Limiter: REDIS_URL not configured. Falling back to in-memory strategy."
            )

    def _connect_redis(self) -> None:
        try:
            self.redis_client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=settings.RATE_LIMIT_REDIS_SOCKET_TIMEOUT_SECONDS,
                socket_timeout=settings.RATE_LIMIT_REDIS_SOCKET_TIMEOUT_SECONDS,
            )
            self.redis_client.ping()
            self.use_redis = True
            self.next_redis_retry_at = 0.0
            logger.info("Rate Limiter: Using Redis-based strategy")
        except Exception as e:
            self.use_redis = False
            self.redis_client = None
            self.next_redis_retry_at = time.time() + self.redis_retry_cooldown
            logger.warning(
                f"Rate Limiter: Redis unavailable ({e}). Falling back to in-memory strategy."
            )

    def _maybe_restore_redis(self) -> None:
        if not settings.REDIS_URL or self.use_redis:
            return
        if time.time() < self.next_redis_retry_at:
            return
        self._connect_redis()

    def _check_redis_limit(
        self, bucket: str, identity: str, max_requests: int, window: int
    ) -> Tuple[bool, int, int]:
        """Check rate limit using Redis INCR and EXPIRE"""
        redis_key = f"rate_limit:{bucket}:{identity}"
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
        if is_rate_limit_exempt(request.url.path):
            return await call_next(request)

        policy = resolve_rate_limit_policy(request, settings)
        request_path = request.url.path
        max_requests = policy.limit
        window = policy.window
        identity = resolve_rate_limit_identity(request)
        redis_key = f"{policy.bucket}:{identity}"
        rate_limit_mode = "memory-fallback"

        self._maybe_restore_redis()

        if self.use_redis:
            try:
                allowed, count, reset_after = self._check_redis_limit(
                    policy.bucket,
                    identity,
                    max_requests,
                    window,
                )
                rate_limit_mode = "redis"
            except Exception as e:
                logger.warning(
                    f"Rate limiter Redis runtime failure ({e}). Falling back to memory strategy."
                )
                self.use_redis = False
                self.redis_client = None
                self.next_redis_retry_at = time.time() + self.redis_retry_cooldown
                allowed, count, reset_after = self._check_memory_limit(
                    redis_key, max_requests, window
                )
                rate_limit_mode = "memory-fallback"
        else:
            allowed, count, reset_after = self._check_memory_limit(
                redis_key, max_requests, window
            )
            rate_limit_mode = "memory-fallback"

        if not allowed:
            logger.warning(f"Rate limit exceeded: {identity} on {request_path}")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Rate limit exceeded",
                    "detail": f"Max {max_requests} requests per {window}s.",
                    "retry_after": reset_after,
                },
                headers={
                    "Retry-After": str(max(0, reset_after)),
                    "X-RateLimit-Mode": rate_limit_mode,
                    "X-RateLimit-Limit": str(max_requests),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(time.time() + max(0, reset_after))),
                    "X-RateLimit-Bucket": policy.bucket,
                },
            )

        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(max_requests)
        response.headers["X-RateLimit-Remaining"] = str(max(0, max_requests - count))
        response.headers["X-RateLimit-Reset"] = str(
            int(time.time() + max(0, reset_after))
        )
        response.headers["X-RateLimit-Mode"] = rate_limit_mode
        response.headers["X-RateLimit-Bucket"] = policy.bucket

        return response
