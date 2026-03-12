"""
Async runtime helpers for Celery worker processes.
"""

from __future__ import annotations

import asyncio
import os
import threading
from typing import Any

from celery.signals import worker_process_shutdown

from app.core.logger import get_logger

logger = get_logger(__name__)


class _WorkerAsyncRuntime:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._pid: int | None = None

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        current_pid = os.getpid()
        with self._lock:
            if self._loop is None or self._loop.is_closed() or self._pid != current_pid:
                if self._loop is not None and not self._loop.is_closed():
                    self._close_loop_locked()
                self._loop = asyncio.new_event_loop()
                self._pid = current_pid
                asyncio.set_event_loop(self._loop)
            return self._loop

    def run(self, awaitable: Any) -> Any:
        loop = self._ensure_loop()
        return loop.run_until_complete(awaitable)

    def close(self) -> None:
        with self._lock:
            self._close_loop_locked()

    def _close_loop_locked(self) -> None:
        loop = self._loop
        if loop is None:
            self._pid = None
            return

        try:
            if not loop.is_closed():
                pending = [task for task in asyncio.all_tasks(loop) if not task.done()]
                for task in pending:
                    task.cancel()
                if pending:
                    loop.run_until_complete(
                        asyncio.gather(*pending, return_exceptions=True)
                    )
                loop.run_until_complete(loop.shutdown_asyncgens())
                if hasattr(loop, "shutdown_default_executor"):
                    loop.run_until_complete(loop.shutdown_default_executor())
        except RuntimeError as exc:
            logger.debug("Async runtime shutdown skipped: %s", exc)
        finally:
            try:
                asyncio.set_event_loop(None)
            except Exception:
                pass
            if not loop.is_closed():
                loop.close()
            self._loop = None
            self._pid = None


_worker_async_runtime = _WorkerAsyncRuntime()


def run_worker_coroutine(awaitable: Any) -> Any:
    return _worker_async_runtime.run(awaitable)


@worker_process_shutdown.connect
def _shutdown_worker_async_runtime(**_: Any) -> None:
    _worker_async_runtime.close()
