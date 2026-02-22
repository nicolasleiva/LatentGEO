import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import settings, validate_environment
import tempfile

import app.core.logger as logger_module
from app.core.middleware import SecurityHeadersMiddleware


def test_database_module_fails_fast_when_database_url_missing(tmp_path):
    repo_root = Path(__file__).resolve().parents[2]
    backend_dir = repo_root / "backend"
    script = "import app.core.database"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(backend_dir)
    env["DATABASE_URL"] = ""

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    combined_output = f"{result.stdout}\n{result.stderr}"
    assert "DATABASE_URL no configurada" in combined_output


def test_logger_init_log_dir_falls_back_to_tmp(monkeypatch):
    calls: list[str] = []
    expected_fallback = str((tempfile.gettempdir() + "/logs").replace("\\", "/"))

    def fake_makedirs(path, exist_ok=True):
        normalized_path = str(path).replace("\\", "/")
        calls.append(normalized_path)
        if normalized_path != expected_fallback:
            raise PermissionError("read-only fs")

    monkeypatch.setattr(logger_module.settings, "LOG_DIR", "blocked-logs", raising=False)
    monkeypatch.setattr(logger_module.os, "makedirs", fake_makedirs)

    selected = str(logger_module._init_log_dir()).replace("\\", "/")
    assert selected == expected_fallback
    assert calls[0].endswith("blocked-logs")
    assert calls[-1] == expected_fallback


def test_validate_environment_requires_forwarded_allow_ips_in_production(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production", raising=False)
    monkeypatch.setattr(settings, "STRICT_CONFIG", True, raising=False)
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql://u:p@db:5432/app", raising=False)
    monkeypatch.setattr(settings, "REDIS_URL", "redis://redis:6379/0", raising=False)
    monkeypatch.setattr(
        settings, "CELERY_BROKER_URL", "redis://redis:6379/0", raising=False
    )
    monkeypatch.setattr(
        settings, "CELERY_RESULT_BACKEND", "redis://redis:6379/1", raising=False
    )
    monkeypatch.setattr(settings, "secret_key", "super-secret", raising=False)
    monkeypatch.setattr(settings, "ENCRYPTION_KEY", "super-encryption", raising=False)
    monkeypatch.setattr(settings, "WEBHOOK_SECRET", "super-webhook", raising=False)
    monkeypatch.setattr(settings, "FRONTEND_URL", "https://frontend.example.com", raising=False)
    monkeypatch.setattr(settings, "DEBUG", False, raising=False)
    monkeypatch.setattr(settings, "CORS_ORIGINS", ["https://frontend.example.com"], raising=False)
    monkeypatch.setattr(settings, "TRUSTED_HOSTS", ["api.example.com"], raising=False)
    monkeypatch.setattr(settings, "FORWARDED_ALLOW_IPS", [], raising=False)

    with pytest.raises(RuntimeError) as exc_info:
        validate_environment()

    assert "FORWARDED_ALLOW_IPS is missing in production." in str(exc_info.value)


def test_csp_excludes_unsafe_eval_when_enabled():
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware, csp_enabled=True)

    @app.get("/test")
    async def test_endpoint():
        return {"ok": True}

    client = TestClient(app)
    response = client.get("/test")
    csp = response.headers.get("Content-Security-Policy", "")

    assert "script-src" in csp
    assert "'unsafe-inline'" in csp
    assert "'unsafe-eval'" not in csp
