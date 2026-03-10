"""Portable backend launcher with configurable worker concurrency."""

from __future__ import annotations

import os


def _read_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def main() -> None:
    host = os.getenv("HOST", "0.0.0.0").strip() or "0.0.0.0"
    port = str(_read_int("PORT", 8000))
    cpu_count = os.cpu_count() or 1
    default_workers = max(1, min(4, cpu_count))
    workers = _read_int("WEB_CONCURRENCY", default_workers)
    log_level = os.getenv("LOG_LEVEL", "info").strip().lower() or "info"

    command = [
        "uvicorn",
        "app.main:app",
        "--host",
        host,
        "--port",
        port,
        "--log-level",
        log_level,
    ]
    if workers > 1:
        command.extend(["--workers", str(workers)])

    os.execvp(command[0], command)


if __name__ == "__main__":
    main()
