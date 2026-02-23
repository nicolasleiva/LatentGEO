"""
External service resilience helpers (timeouts + circuit breaker).
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Any, Awaitable, Callable, Dict, TypeVar

import pybreaker

from .config import settings
from .logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class ExternalServiceError(RuntimeError):
    """Base error for external-provider failures."""


class ExternalServiceTimeout(ExternalServiceError):
    """External call timed out."""


class ExternalCircuitOpenError(ExternalServiceError):
    """Circuit breaker is open for this provider."""


class ExternalRequestError(ExternalServiceError):
    """External call failed for non-timeout reasons."""


_breakers: Dict[str, pybreaker.CircuitBreaker] = {}


def _normalize_service_name(service_name: str) -> str:
    normalized = (service_name or "external").strip().lower()
    return normalized or "external"


def _resolve_timeout(timeout_seconds: float | None) -> float | None:
    if timeout_seconds is None:
        timeout_seconds = settings.EXTERNAL_HTTP_TIMEOUT_SECONDS
    if timeout_seconds is None:
        return None
    resolved = float(timeout_seconds)
    return resolved if resolved > 0 else None


def get_circuit_breaker(service_name: str) -> pybreaker.CircuitBreaker | None:
    if not settings.CIRCUIT_BREAKER_ENABLED:
        return None

    key = _normalize_service_name(service_name)
    breaker = _breakers.get(key)
    if breaker is not None:
        return breaker

    breaker = pybreaker.CircuitBreaker(
        fail_max=max(1, int(settings.CIRCUIT_BREAKER_FAIL_MAX)),
        reset_timeout=max(1, int(settings.CIRCUIT_BREAKER_RESET_TIMEOUT_SECONDS)),
        success_threshold=max(1, int(settings.CIRCUIT_BREAKER_SUCCESS_THRESHOLD)),
        name=key,
    )
    _breakers[key] = breaker
    return breaker


async def run_external_call(
    service_name: str,
    operation: Callable[[], Awaitable[T]],
    *,
    timeout_seconds: float | None = None,
) -> T:
    """
    Execute an async external call with timeout + circuit breaker.
    """
    breaker = get_circuit_breaker(service_name)
    effective_timeout = _resolve_timeout(timeout_seconds)

    async def _wrapped_operation() -> T:
        if effective_timeout is None:
            return await operation()
        return await asyncio.wait_for(operation(), timeout=effective_timeout)

    try:
        if breaker is not None:
            return await breaker.call_async(_wrapped_operation)
        return await _wrapped_operation()
    except asyncio.TimeoutError as exc:
        raise ExternalServiceTimeout(
            f"{service_name} request timed out after {effective_timeout}s"
        ) from exc
    except pybreaker.CircuitBreakerError as exc:
        raise ExternalCircuitOpenError(
            f"Circuit is open for external service '{service_name}'"
        ) from exc
    except ExternalServiceError:
        raise
    except Exception as exc:
        raise ExternalRequestError(
            f"External service '{service_name}' request failed: {exc}"
        ) from exc


def run_external_call_sync(
    service_name: str,
    operation: Callable[[], T],
    *,
    timeout_seconds: float | None = None,
) -> T:
    """
    Execute a sync external call with timeout + circuit breaker.
    """
    breaker = get_circuit_breaker(service_name)
    effective_timeout = _resolve_timeout(timeout_seconds)

    def _wrapped_operation() -> T:
        if effective_timeout is None:
            return operation()
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(operation)
            return future.result(timeout=effective_timeout)

    try:
        if breaker is not None:
            return breaker.call(_wrapped_operation)
        return _wrapped_operation()
    except FuturesTimeoutError as exc:
        raise ExternalServiceTimeout(
            f"{service_name} request timed out after {effective_timeout}s"
        ) from exc
    except pybreaker.CircuitBreakerError as exc:
        raise ExternalCircuitOpenError(
            f"Circuit is open for external service '{service_name}'"
        ) from exc
    except ExternalServiceError:
        raise
    except Exception as exc:
        raise ExternalRequestError(
            f"External service '{service_name}' request failed: {exc}"
        ) from exc


def get_circuit_breaker_states() -> Dict[str, str]:
    """
    Expose breaker states for health/debug logs.
    """
    states: Dict[str, str] = {}
    for name, breaker in _breakers.items():
        try:
            states[name] = str(breaker.current_state)
        except Exception as exc:  # nosec B110
            logger.warning(f"Unable to read breaker state for {name}: {exc}")
            states[name] = "unknown"
    return states
