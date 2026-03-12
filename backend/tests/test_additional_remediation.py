import os
import subprocess
import sys
import tempfile
from pathlib import Path

import app.core.logger as logger_module
import pytest
import start_server as start_server_module
from app.core.config import Settings, _REPO_ROOT, settings, validate_environment
from app.core.middleware import SecurityHeadersMiddleware
from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_database_module_fails_fast_when_database_url_missing(tmp_path):
    script = "import app.core.database"
    env = os.environ.copy()
    backend_path = Path(__file__).resolve().parents[1]
    # Use current sys.path to ensure 'app' module is found in subprocess
    env["PYTHONPATH"] = os.pathsep.join([str(backend_path), *sys.path])
    # Force non-test semantics so the import guard is exercised regardless of CI env.
    env["ENVIRONMENT"] = "production"
    # Ensure DATABASE_URL is missing/empty
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
    # The message might be "DATABASE_URL no configurada" OR "DATABASE_URL missing"
    # or a Pydantic validation error if it fails earlier
    assert "DATABASE_URL" in combined_output


def test_logger_init_log_dir_falls_back_to_tmp(monkeypatch):
    calls: list[str] = []
    expected_fallback = str((tempfile.gettempdir() + "/logs").replace("\\", "/"))

    def fake_makedirs(path, exist_ok=True):
        normalized_path = str(path).replace("\\", "/")
        calls.append(normalized_path)
        if normalized_path != expected_fallback:
            raise PermissionError("read-only fs")

    monkeypatch.setattr(
        logger_module.settings, "LOG_DIR", "blocked-logs", raising=False
    )
    monkeypatch.setattr(logger_module.os, "makedirs", fake_makedirs)

    selected = str(logger_module._init_log_dir()).replace("\\", "/")
    assert selected == expected_fallback
    assert calls[0].endswith("blocked-logs")
    assert calls[-1] == expected_fallback


def test_validate_environment_requires_forwarded_allow_ips_in_production(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production", raising=False)
    monkeypatch.setattr(settings, "STRICT_CONFIG", True, raising=False)
    monkeypatch.setattr(
        settings, "DATABASE_URL", "postgresql://u:p@db:5432/app", raising=False
    )
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
    monkeypatch.setattr(
        settings, "FRONTEND_URL", "https://frontend.example.com", raising=False
    )
    monkeypatch.setattr(settings, "DEBUG", False, raising=False)
    monkeypatch.setattr(
        settings, "CORS_ORIGINS", ["https://frontend.example.com"], raising=False
    )
    monkeypatch.setattr(settings, "TRUSTED_HOSTS", ["api.example.com"], raising=False)
    monkeypatch.setattr(settings, "FORWARDED_ALLOW_IPS", [], raising=False)

    with pytest.raises(RuntimeError) as exc_info:
        validate_environment()

    assert "FORWARDED_ALLOW_IPS is missing in production." in str(exc_info.value)


def test_validate_environment_rejects_docker_bridge_cidr_in_production(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production", raising=False)
    monkeypatch.setattr(settings, "STRICT_CONFIG", True, raising=False)
    monkeypatch.setattr(
        settings,
        "DATABASE_URL",
        "postgresql://db.supabase.co:5432/app",
        raising=False,
    )
    monkeypatch.setattr(
        settings, "SUPABASE_URL", "https://example.supabase.co", raising=False
    )
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
    monkeypatch.setattr(
        settings, "FRONTEND_URL", "https://frontend.example.com", raising=False
    )
    monkeypatch.setattr(settings, "DEBUG", False, raising=False)
    monkeypatch.setattr(
        settings, "CORS_ORIGINS", ["https://frontend.example.com"], raising=False
    )
    monkeypatch.setattr(settings, "TRUSTED_HOSTS", ["api.example.com"], raising=False)
    monkeypatch.setattr(
        settings, "FORWARDED_ALLOW_IPS", ["172.18.0.0/16"], raising=False
    )
    monkeypatch.setattr(settings, "AUTH0_API_AUDIENCE", "https://api.example.com")
    monkeypatch.setattr(
        settings,
        "AUTH0_ISSUER_BASE_URL",
        "https://tenant.us.auth0.com/",
        raising=False,
    )
    monkeypatch.setattr(settings, "AUDIT_LOCAL_ARTIFACTS_ENABLED", True, raising=False)

    with pytest.raises(RuntimeError) as exc_info:
        validate_environment()

    assert (
        "FORWARDED_ALLOW_IPS cannot trust Docker bridge CIDR 172.18.0.0/16 in production."
        in str(exc_info.value)
    )


def test_settings_treat_docker_local_as_development_like_defaults():
    docker_local_settings = Settings(
        _env_file=None,
        ENVIRONMENT="docker-local",
        CORS_ORIGINS=[],
        TRUSTED_HOSTS=[],
        FORWARDED_ALLOW_IPS=[],
        FRONTEND_URL=None,
    )

    assert docker_local_settings.CORS_ORIGINS
    assert docker_local_settings.TRUSTED_HOSTS
    assert docker_local_settings.FORWARDED_ALLOW_IPS == ["127.0.0.1", "::1"]
    assert docker_local_settings.FRONTEND_URL == "http://localhost:3000"


def test_validate_environment_enforces_release_strict_pdf_flag(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "staging", raising=False)
    monkeypatch.setattr(settings, "STRICT_CONFIG", False, raising=False)
    monkeypatch.setattr(settings, "AUDIT_LOCAL_ARTIFACTS_ENABLED", True, raising=False)
    monkeypatch.setattr(
        settings,
        "DATABASE_URL",
        "postgresql://db.supabase.co:5432/app",
        raising=False,
    )
    monkeypatch.setattr(settings, "AUTH0_API_AUDIENCE", "https://api.example.com")
    monkeypatch.setattr(
        settings,
        "AUTH0_ISSUER_BASE_URL",
        "https://tenant.us.auth0.com/",
        raising=False,
    )
    monkeypatch.setattr(settings, "OPENAPI_DOCS_ENABLED", False, raising=False)
    monkeypatch.setattr(
        settings, "PDF_ALLOW_DETERMINISTIC_FALLBACK", True, raising=False
    )

    with pytest.raises(RuntimeError) as exc_info:
        validate_environment()

    assert (
        "PDF_ALLOW_DETERMINISTIC_FALLBACK must be false in strict/prod release mode."
        in str(exc_info.value)
    )


def test_start_server_injects_backend_dir_into_pythonpath(monkeypatch):
    backend_dir = str(Path(start_server_module.__file__).resolve().parent)
    monkeypatch.delenv("PYTHONPATH", raising=False)

    start_server_module._ensure_backend_on_pythonpath()

    pythonpath = os.environ["PYTHONPATH"].split(os.pathsep)
    assert pythonpath[0] == backend_dir


def test_start_server_uses_current_python_interpreter(monkeypatch):
    monkeypatch.delenv("WEB_CONCURRENCY", raising=False)
    monkeypatch.delenv("HOST", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.delenv("LOG_LEVEL", raising=False)

    command = start_server_module._build_command()

    assert command[:3] == [sys.executable, "-m", "uvicorn"]
    assert "--workers" not in command


def test_start_server_honors_explicit_web_concurrency(monkeypatch):
    monkeypatch.setenv("WEB_CONCURRENCY", "3")

    command = start_server_module._build_command()

    assert command[-2:] == ["--workers", "3"]


def test_settings_resolve_repo_root_env_file():
    env_files = settings.model_config.get("env_file", ())
    normalized = {str(Path(item).resolve()) for item in env_files}

    assert str((_REPO_ROOT / ".env").resolve()) in normalized


def test_csp_excludes_unsafe_eval_when_enabled():
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware, csp_enabled=True)

    @app.get("/test")
    async def test_endpoint():
        return {"ok": True}

    with TestClient(app) as client:
        response = client.get("/test")
    csp = response.headers.get("Content-Security-Policy", "")

    assert "script-src" in csp
    assert "'unsafe-inline'" in csp
    assert "'unsafe-eval'" not in csp
