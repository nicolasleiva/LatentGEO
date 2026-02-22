from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.middleware import RateLimitMiddleware as CoreRateLimitMiddleware
from app.core.config import settings
from app.middleware.rate_limit import RateLimitMiddleware as RedisRateLimitMiddleware


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


def _redis_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RedisRateLimitMiddleware)

    @app.get("/test")
    async def test_endpoint():
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


def test_core_rate_limit_does_not_trust_x_forwarded_for():
    client = TestClient(_core_app(default_limit=2))

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

    client = TestClient(_redis_app())
    response = client.get("/test")

    assert response.status_code == 200
    assert response.headers.get("X-RateLimit-Mode") == "redis"


def test_redis_rate_limit_falls_back_to_memory_when_redis_missing(monkeypatch):
    monkeypatch.setattr(settings, "REDIS_URL", None, raising=False)
    monkeypatch.setattr(settings, "RATE_LIMIT_DEFAULT", 10, raising=False)

    client = TestClient(_redis_app())
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

    client = TestClient(_redis_app())
    response_1 = client.get("/test", headers={"X-Forwarded-For": "5.5.5.5"})
    response_2 = client.get("/test", headers={"X-Forwarded-For": "6.6.6.6"})
    response_3 = client.get("/test", headers={"X-Forwarded-For": "7.7.7.7"})

    assert response_1.status_code == 200
    assert response_1.headers.get("X-RateLimit-Mode") == "memory-fallback"
    assert response_2.status_code == 200
    assert response_3.status_code == 429
    assert response_3.headers.get("X-RateLimit-Mode") == "memory-fallback"
