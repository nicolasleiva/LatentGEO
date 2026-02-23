from app.api.routes import audits as audits_route
from app.core.config import settings
from app.services.cache_service import cache


class FakeRedis:
    def __init__(self):
        self.store = {}

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self.store:
            return False
        self.store[key] = value
        return True

    def get(self, key):
        return self.store.get(key)

    def delete(self, key):
        self.store.pop(key, None)


def test_pdf_lock_local_fallback_when_redis_disabled(monkeypatch):
    monkeypatch.setattr(settings, "DEBUG", True, raising=False)
    monkeypatch.setattr(cache, "enabled", False, raising=False)
    monkeypatch.setattr(cache, "redis_client", None, raising=False)
    audits_route._pdf_generation_in_progress.clear()
    audits_route._pdf_generation_tokens.clear()

    acquired, token, mode = audits_route._acquire_pdf_generation_lock(101)
    assert acquired is True
    assert token
    assert mode == "local"

    acquired_second, _, mode_second = audits_route._acquire_pdf_generation_lock(101)
    assert acquired_second is False
    assert mode_second == "local"

    audits_route._release_pdf_generation_lock(101, token, mode)

    acquired_third, token_third, mode_third = audits_route._acquire_pdf_generation_lock(
        101
    )
    assert acquired_third is True
    assert token_third
    assert mode_third == "local"

    audits_route._release_pdf_generation_lock(101, token_third, mode_third)


def test_pdf_lock_redis_distributed_lock(monkeypatch):
    monkeypatch.setattr(settings, "DEBUG", False, raising=False)
    fake_redis = FakeRedis()
    monkeypatch.setattr(cache, "enabled", True, raising=False)
    monkeypatch.setattr(cache, "redis_client", fake_redis, raising=False)
    audits_route._pdf_generation_in_progress.clear()
    audits_route._pdf_generation_tokens.clear()

    acquired, token, mode = audits_route._acquire_pdf_generation_lock(202)
    assert acquired is True
    assert token
    assert mode == "redis"

    acquired_second, _, mode_second = audits_route._acquire_pdf_generation_lock(202)
    assert acquired_second is False
    assert mode_second == "redis"

    audits_route._release_pdf_generation_lock(202, token, mode)
    assert fake_redis.get(audits_route._pdf_lock_key(202)) is None


def test_pdf_lock_falls_back_to_local_when_redis_errors(monkeypatch):
    monkeypatch.setattr(settings, "DEBUG", True, raising=False)

    class BrokenRedis:
        def set(self, *args, **kwargs):
            raise RuntimeError("redis down")

    monkeypatch.setattr(cache, "enabled", True, raising=False)
    monkeypatch.setattr(cache, "redis_client", BrokenRedis(), raising=False)
    audits_route._pdf_generation_in_progress.clear()
    audits_route._pdf_generation_tokens.clear()

    acquired, token, mode = audits_route._acquire_pdf_generation_lock(303)
    assert acquired is True
    assert token
    assert mode == "local"

    audits_route._release_pdf_generation_lock(303, token, mode)


def test_pdf_lock_returns_unavailable_when_redis_disabled_in_production(monkeypatch):
    monkeypatch.setattr(settings, "DEBUG", False, raising=False)
    monkeypatch.setattr(cache, "enabled", False, raising=False)
    monkeypatch.setattr(cache, "redis_client", None, raising=False)
    audits_route._pdf_generation_in_progress.clear()
    audits_route._pdf_generation_tokens.clear()

    acquired, token, mode = audits_route._acquire_pdf_generation_lock(404)
    assert acquired is False
    assert token is None
    assert mode == "unavailable"
