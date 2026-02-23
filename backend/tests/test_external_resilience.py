import asyncio
import time

import pytest

from app.core import external_resilience as resilience
from app.core.config import settings


@pytest.fixture(autouse=True)
def _reset_breakers(monkeypatch):
    resilience._breakers.clear()
    monkeypatch.setattr(settings, "CIRCUIT_BREAKER_ENABLED", True, raising=False)
    monkeypatch.setattr(settings, "CIRCUIT_BREAKER_FAIL_MAX", 2, raising=False)
    monkeypatch.setattr(
        settings, "CIRCUIT_BREAKER_RESET_TIMEOUT_SECONDS", 1, raising=False
    )
    monkeypatch.setattr(settings, "CIRCUIT_BREAKER_SUCCESS_THRESHOLD", 1, raising=False)
    monkeypatch.setattr(settings, "EXTERNAL_HTTP_TIMEOUT_SECONDS", 0.1, raising=False)
    yield
    resilience._breakers.clear()


@pytest.mark.asyncio
async def test_run_external_call_enforces_async_timeout():
    async def _slow():
        await asyncio.sleep(0.05)
        return "ok"

    with pytest.raises(resilience.ExternalServiceTimeout):
        await resilience.run_external_call(
            "timeout-async",
            _slow,
            timeout_seconds=0.01,
        )


@pytest.mark.asyncio
@pytest.mark.filterwarnings(
    "ignore:coroutine 'run_external_call.<locals>._wrapped_operation' was never awaited:RuntimeWarning"
)
async def test_circuit_breaker_opens_and_recovers():
    async def _always_fail():
        raise RuntimeError("provider down")

    with pytest.raises(resilience.ExternalRequestError):
        await resilience.run_external_call("provider-a", _always_fail)

    with pytest.raises(
        (resilience.ExternalRequestError, resilience.ExternalCircuitOpenError)
    ):
        await resilience.run_external_call("provider-a", _always_fail)

    open_state = resilience.get_circuit_breaker_states().get("provider-a", "")
    assert "open" in open_state.lower()

    await asyncio.sleep(1.1)

    async def _ok():
        return "healthy"

    assert await resilience.run_external_call("provider-a", _ok) == "healthy"
    state = resilience.get_circuit_breaker_states().get("provider-a", "")
    assert "closed" in state.lower()


def test_run_external_call_sync_enforces_timeout():
    def _slow():
        time.sleep(0.05)
        return "ok"

    with pytest.raises(resilience.ExternalServiceTimeout):
        resilience.run_external_call_sync(
            "timeout-sync",
            _slow,
            timeout_seconds=0.01,
        )
