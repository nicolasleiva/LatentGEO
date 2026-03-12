from app.core.auth import AuthUser
from app.core.config import settings
from app.core.middleware import RateLimitMiddleware as CoreRateLimitMiddleware
from app.middleware.rate_limit import RateLimitMiddleware as RedisRateLimitMiddleware
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware


class _InjectAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request.state.auth_user = None
        request.state.auth_error = None

        authorization = request.headers.get("Authorization", "").strip()
        if authorization.lower().startswith("bearer "):
            subject = authorization[7:].strip()
            if subject:
                request.state.auth_user = AuthUser(user_id=subject)

        return await call_next(request)


def _core_app(default_limit: int = 2) -> FastAPI:
    app = FastAPI()
    app.add_middleware(
        CoreRateLimitMiddleware,
        default_limit=default_limit,
        default_window=60,
        endpoint_limits={},
        trusted_ips=[],
    )

    @app.get("/test")
    async def test_endpoint():
        return {"ok": True}

    return app


def _redis_app(*, with_auth: bool = False) -> FastAPI:
    app = FastAPI()
    app.add_middleware(RedisRateLimitMiddleware)
    if with_auth:
        app.add_middleware(_InjectAuthMiddleware)

    @app.get("/test")
    async def test_endpoint():
        return {"ok": True}

    @app.get("/api/v1/audits/32/overview")
    async def audit_overview():
        return {"ok": True}

    @app.post("/api/v1/audits/32/generate-pdf")
    async def generate_pdf():
        return {"ok": True}

    @app.get("/api/v1/audits/32/pdf-status")
    async def pdf_status():
        return {"ok": True}

    @app.get("/api/v1/audits/32/pagespeed-status")
    async def pagespeed_status():
        return {"ok": True}

    @app.get("/api/v1/audits/32/artifacts-status")
    async def artifacts_status():
        return {"ok": True}

    return app


class _FakePipeline:
    def __init__(self, store: dict[str, int]):
        self.store = store
        self.key: str | None = None

    def incr(self, key: str):
        self.key = key
        self.store[key] = int(self.store.get(key, 0)) + 1
        return self

    def expire(self, key: str, window: int, nx: bool = True):
        self.store[f"{key}:ttl"] = window
        return self

    def execute(self):
        assert self.key is not None
        return [self.store[self.key], True]


class _FakeRedis:
    def __init__(self):
        self.store: dict[str, int] = {}

    def ping(self):
        return True

    def get(self, key: str):
        value = self.store.get(key)
        return str(value) if value is not None else None

    def ttl(self, key: str):
        return int(self.store.get(f"{key}:ttl", 60))

    def pipeline(self):
        return _FakePipeline(self.store)


class _BrokenRedis(_FakeRedis):
    def get(self, key: str):
        raise ConnectionError("redis down")


class _ReconnectableRedis(_FakeRedis):
    def __init__(self):
        super().__init__()
        self.fail_runtime = True

    def get(self, key: str):
        if self.fail_runtime:
            raise ConnectionError("redis down")
        return super().get(key)


def test_core_rate_limit_does_not_trust_x_forwarded_for():
    with TestClient(_core_app(default_limit=2)) as client:
        response_1 = client.get("/test", headers={"X-Forwarded-For": "1.1.1.1"})
        response_2 = client.get("/test", headers={"X-Forwarded-For": "2.2.2.2"})
        response_3 = client.get("/test", headers={"X-Forwarded-For": "3.3.3.3"})

    assert response_1.status_code == 200
    assert response_2.status_code == 200
    assert response_3.status_code == 429


def test_redis_rate_limit_sets_mode_header_redis(monkeypatch):
    fake_redis = _FakeRedis()
    monkeypatch.setattr(settings, "REDIS_URL", "redis://fake:6379/0", raising=False)
    monkeypatch.setattr(settings, "RATE_LIMIT_DEFAULT", 10, raising=False)
    monkeypatch.setattr(
        "app.middleware.rate_limit.redis.from_url",
        lambda *args, **kwargs: fake_redis,
    )

    with TestClient(_redis_app()) as client:
        response = client.get("/test")

    assert response.status_code == 200
    assert response.headers.get("X-RateLimit-Mode") == "redis"
    assert response.headers.get("X-RateLimit-Bucket") == "default"


def test_redis_rate_limit_falls_back_to_memory_when_redis_missing(monkeypatch):
    monkeypatch.setattr(settings, "REDIS_URL", None, raising=False)
    monkeypatch.setattr(settings, "RATE_LIMIT_DEFAULT", 10, raising=False)

    with TestClient(_redis_app()) as client:
        response = client.get("/test")

    assert response.status_code == 200
    assert response.headers.get("X-RateLimit-Mode") == "memory-fallback"


def test_redis_rate_limit_runtime_failure_uses_memory_and_blocks(monkeypatch):
    monkeypatch.setattr(settings, "REDIS_URL", "redis://fake:6379/0", raising=False)
    monkeypatch.setattr(settings, "RATE_LIMIT_DEFAULT", 2, raising=False)
    monkeypatch.setattr(settings, "RATE_LIMIT_HEAVY", 2, raising=False)
    monkeypatch.setattr(settings, "RATE_LIMIT_AUTH", 2, raising=False)
    monkeypatch.setattr(
        "app.middleware.rate_limit.redis.from_url",
        lambda *args, **kwargs: _BrokenRedis(),
    )

    with TestClient(_redis_app()) as client:
        response_1 = client.get("/test", headers={"X-Forwarded-For": "5.5.5.5"})
        response_2 = client.get("/test", headers={"X-Forwarded-For": "6.6.6.6"})
        response_3 = client.get("/test", headers={"X-Forwarded-For": "7.7.7.7"})

    assert response_1.status_code == 200
    assert response_1.headers.get("X-RateLimit-Mode") == "memory-fallback"
    assert response_2.status_code == 200
    assert response_3.status_code == 429
    assert response_3.headers.get("X-RateLimit-Mode") == "memory-fallback"


def test_redis_rate_limit_recovers_after_transient_runtime_failure(monkeypatch):
    fake_redis = _ReconnectableRedis()
    monkeypatch.setattr(settings, "REDIS_URL", "redis://fake:6379/0", raising=False)
    monkeypatch.setattr(settings, "RATE_LIMIT_DEFAULT", 10, raising=False)
    monkeypatch.setattr(
        settings,
        "RATE_LIMIT_REDIS_RETRY_COOLDOWN_SECONDS",
        1,
        raising=False,
    )
    monkeypatch.setattr(
        "app.middleware.rate_limit.redis.from_url",
        lambda *args, **kwargs: fake_redis,
    )

    with TestClient(_redis_app()) as client:
        response_1 = client.get("/test")
        fake_redis.fail_runtime = False
        monkeypatch.setattr("app.middleware.rate_limit.time.time", lambda: 2.0)
        client.app.middleware_stack.app.next_redis_retry_at = 1.0
        response_2 = client.get("/test")

    assert response_1.status_code == 200
    assert response_1.headers.get("X-RateLimit-Mode") == "memory-fallback"
    assert response_2.status_code == 200
    assert response_2.headers.get("X-RateLimit-Mode") == "redis"


def test_redis_rate_limit_scopes_pdf_bucket_away_from_normal_traffic(monkeypatch):
    fake_redis = _FakeRedis()
    monkeypatch.setattr(settings, "REDIS_URL", "redis://fake:6379/0", raising=False)
    monkeypatch.setattr(settings, "RATE_LIMIT_DEFAULT", 2, raising=False)
    monkeypatch.setattr(settings, "RATE_LIMIT_HEAVY", 1, raising=False)
    monkeypatch.setattr(
        "app.middleware.rate_limit.redis.from_url",
        lambda *args, **kwargs: fake_redis,
    )

    with TestClient(_redis_app()) as client:
        overview_1 = client.get("/api/v1/audits/32/overview")
        overview_2 = client.get("/api/v1/audits/32/overview")
        generate_1 = client.post("/api/v1/audits/32/generate-pdf")
        generate_2 = client.post("/api/v1/audits/32/generate-pdf")
        status_1 = client.get("/api/v1/audits/32/pdf-status")
        pagespeed_status_1 = client.get("/api/v1/audits/32/pagespeed-status")
        artifacts_status_1 = client.get("/api/v1/audits/32/artifacts-status")

    assert overview_1.status_code == 200
    assert overview_2.status_code == 200
    assert generate_1.status_code == 200
    assert generate_1.headers.get("X-RateLimit-Bucket") == "pdf_generate"
    assert generate_2.status_code == 429
    assert generate_2.headers.get("X-RateLimit-Bucket") == "pdf_generate"
    assert status_1.status_code == 200
    assert status_1.headers.get("X-RateLimit-Bucket") == "pdf_status"
    assert pagespeed_status_1.status_code == 200
    assert pagespeed_status_1.headers.get("X-RateLimit-Bucket") == "pagespeed_status"
    assert artifacts_status_1.status_code == 200
    assert artifacts_status_1.headers.get("X-RateLimit-Bucket") == "artifacts_status"
    audit_read_keys = [
        key
        for key in fake_redis.store
        if key.startswith("rate_limit:audit_read:ip:") and not key.endswith(":ttl")
    ]
    pdf_generate_keys = [
        key
        for key in fake_redis.store
        if key.startswith("rate_limit:pdf_generate:ip:") and not key.endswith(":ttl")
    ]
    pdf_status_keys = [
        key
        for key in fake_redis.store
        if key.startswith("rate_limit:pdf_status:ip:") and not key.endswith(":ttl")
    ]
    pagespeed_status_keys = [
        key
        for key in fake_redis.store
        if key.startswith("rate_limit:pagespeed_status:ip:")
        and not key.endswith(":ttl")
    ]
    artifacts_status_keys = [
        key
        for key in fake_redis.store
        if key.startswith("rate_limit:artifacts_status:ip:")
        and not key.endswith(":ttl")
    ]
    assert len(audit_read_keys) == 1
    assert len(pdf_generate_keys) == 1
    assert len(pdf_status_keys) == 1
    assert len(pagespeed_status_keys) == 1
    assert len(artifacts_status_keys) == 1
    assert fake_redis.store[audit_read_keys[0]] == 2
    assert fake_redis.store[pdf_generate_keys[0]] == 1
    assert fake_redis.store[pdf_status_keys[0]] == 1
    assert fake_redis.store[pagespeed_status_keys[0]] == 1
    assert fake_redis.store[artifacts_status_keys[0]] == 1


def test_redis_rate_limit_scopes_authenticated_users_independently(monkeypatch):
    fake_redis = _FakeRedis()
    monkeypatch.setattr(settings, "REDIS_URL", "redis://fake:6379/0", raising=False)
    monkeypatch.setattr(settings, "RATE_LIMIT_DEFAULT", 10, raising=False)
    monkeypatch.setattr(settings, "RATE_LIMIT_HEAVY", 1, raising=False)
    monkeypatch.setattr(
        "app.middleware.rate_limit.redis.from_url",
        lambda *args, **kwargs: fake_redis,
    )

    with TestClient(_redis_app(with_auth=True)) as client:
        user_a_first = client.post(
            "/api/v1/audits/32/generate-pdf",
            headers={"Authorization": "Bearer user-a"},
        )
        user_b_first = client.post(
            "/api/v1/audits/32/generate-pdf",
            headers={"Authorization": "Bearer user-b"},
        )
        user_a_second = client.post(
            "/api/v1/audits/32/generate-pdf",
            headers={"Authorization": "Bearer user-a"},
        )

    assert user_a_first.status_code == 200
    assert user_b_first.status_code == 200
    assert user_a_second.status_code == 429
    assert fake_redis.store["rate_limit:pdf_generate:user:user-a"] == 1
    assert fake_redis.store["rate_limit:pdf_generate:user:user-b"] == 1
