import pytest
from app import main as main_module
from app.core.config import settings
from fastapi import FastAPI


def _rate_limit_modules(app):
    return {
        middleware.cls.__module__
        for middleware in app.user_middleware
        if middleware.cls.__name__ == "RateLimitMiddleware"
    }


def test_create_app_uses_distributed_rate_limit_when_available(monkeypatch):
    monkeypatch.setattr(settings, "DEBUG", False, raising=False)
    monkeypatch.setattr(main_module, "RATE_LIMIT_AVAILABLE", True, raising=False)

    app = main_module.create_app()
    modules = _rate_limit_modules(app)

    assert "app.middleware.rate_limit" in modules
    assert "app.core.middleware" not in modules


def test_create_app_uses_fallback_rate_limit_when_distributed_missing(monkeypatch):
    monkeypatch.setattr(settings, "DEBUG", False, raising=False)
    monkeypatch.setattr(main_module, "RATE_LIMIT_AVAILABLE", False, raising=False)

    app = main_module.create_app()
    modules = _rate_limit_modules(app)

    assert "app.middleware.rate_limit" not in modules
    assert "app.core.middleware" in modules


def test_create_app_disables_rate_limit_in_debug(monkeypatch):
    monkeypatch.setattr(settings, "DEBUG", True, raising=False)
    monkeypatch.setattr(main_module, "RATE_LIMIT_AVAILABLE", True, raising=False)

    app = main_module.create_app()
    modules = _rate_limit_modules(app)
    assert not modules


@pytest.mark.asyncio
async def test_lifespan_fails_fast_when_db_init_fails(monkeypatch):
    async def _fail_init_db():
        raise RuntimeError("db down")

    monkeypatch.setattr(main_module, "init_db", _fail_init_db, raising=False)

    from app.core import config as config_module

    monkeypatch.setattr(
        config_module, "validate_environment", lambda: True, raising=False
    )

    with pytest.raises(RuntimeError, match="Database initialization failed"):
        async with main_module.lifespan(FastAPI()):
            pass

