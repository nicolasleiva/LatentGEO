"""Portable backend launcher with configurable worker concurrency."""

from __future__ import annotations

import ipaddress
import os
import re
import sys
from pathlib import Path

_DEFAULT_HOST = "0.0.0.0"
_VALID_LOG_LEVELS = {"critical", "error", "warning", "info", "debug", "trace"}
_HOSTNAME_PATTERN = re.compile(r"^(?=.{1,253}$)(?!-)[A-Za-z0-9.-]+(?<!-)$")


def _read_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _read_host(default: str = _DEFAULT_HOST) -> str:
    raw = os.getenv("HOST", "").strip()
    if not raw:
        return default

    try:
        ipaddress.ip_address(raw)
        return raw
    except ValueError:
        pass

    if raw == "localhost" or _HOSTNAME_PATTERN.fullmatch(raw):
        return raw

    return default


def _read_log_level(default: str = "info") -> str:
    raw = os.getenv("LOG_LEVEL", "").strip().lower()
    if not raw:
        return default
    return raw if raw in _VALID_LOG_LEVELS else default


def _ensure_backend_on_pythonpath() -> None:
    backend_dir = str(Path(__file__).resolve().parent)
    current = os.getenv("PYTHONPATH", "")
    entries = [entry for entry in current.split(os.pathsep) if entry]

    if backend_dir in entries:
        return

    os.environ["PYTHONPATH"] = os.pathsep.join([backend_dir, *entries])


def _build_command() -> list[str]:
    host = _read_host()
    port = str(_read_int("PORT", 8000))
    workers = _read_int("WEB_CONCURRENCY", 1)
    log_level = _read_log_level()

    command = [
        sys.executable,
        "-m",
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

    return command


def main() -> None:
    _ensure_backend_on_pythonpath()
    command = _build_command()
    os.execvp(command[0], command)


if __name__ == "__main__":
    main()
