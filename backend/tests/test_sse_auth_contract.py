import asyncio
import json

import pytest
from app.api.routes import sse as sse_route
from app.core.auth import create_access_token
from fastapi import FastAPI
from fastapi.testclient import TestClient


class _DummyStatus:
    value = "processing"


class _DummyAudit:
    id = 123
    status = _DummyStatus()
    progress = 10
    error_message = None
    geo_score = None
    total_pages = 1


class _DummySession:
    def close(self):
        return None


class _DummyRequest:
    def __init__(self, disconnect_after_calls: int = 10):
        self.disconnect_after_calls = disconnect_after_calls
        self.calls = 0

    async def is_disconnected(self) -> bool:
        self.calls += 1
        return self.calls > self.disconnect_after_calls


class _FakePubSub:
    def subscribe(self, *_args, **_kwargs):
        return None

    def get_message(self, *_args, **_kwargs):
        return None

    def unsubscribe(self, *_args, **_kwargs):
        return None

    def close(self):
        return None


class _FakeRedisClient:
    def pubsub(self):
        return _FakePubSub()


class _NeverDisconnectRequest:
    async def is_disconnected(self) -> bool:
        return False


def _decode_sse_chunk(chunk: bytes) -> tuple[dict, int | None]:
    if isinstance(chunk, bytes):
        raw = chunk.decode("utf-8")
    else:
        raw = str(chunk)

    data_lines: list[str] = []
    retry_value: int | None = None
    for line in raw.splitlines():
        if line.startswith("data: "):
            data_lines.append(line.replace("data: ", "", 1))
        if line.startswith("retry: "):
            retry_value = int(line.replace("retry: ", "", 1))

    payload = json.loads("\n".join(data_lines)) if data_lines else {}
    return payload, retry_value


def _build_sse_test_app(monkeypatch) -> FastAPI:
    import app.core.database as database_module

    async def _fake_stream(*_args, **_kwargs):
        event = sse_route.ServerSentEvent(
            raw_data='{"status":"processing","progress":10}',
            retry=5000,
        )
        yield sse_route._serialize_sse_event(event)

    monkeypatch.setattr(
        sse_route.AuditService,
        "get_audit",
        lambda _db, _audit_id: _DummyAudit(),
    )
    monkeypatch.setattr(sse_route, "ensure_audit_access", lambda audit, _user: audit)
    monkeypatch.setattr(sse_route, "audit_progress_stream", _fake_stream)
    monkeypatch.setattr(
        database_module, "SessionLocal", lambda: _DummySession(), raising=False
    )

    app = FastAPI()
    app.include_router(sse_route.router)
    return app


def test_sse_rejects_query_token_without_authorization(monkeypatch):
    monkeypatch.setenv(
        "BACKEND_INTERNAL_JWT_SECRET", "test-sse-secret-with-minimum-32-bytes"
    )
    app = _build_sse_test_app(monkeypatch)
    token = create_access_token({"sub": "test-user", "email": "test@example.com"})

    with TestClient(app) as client:
        response = client.get(f"/sse/audits/123/progress?token={token}")

    assert response.status_code == 401
    assert response.json()["detail"] == "Token no proporcionado"


def test_sse_accepts_authorization_header(monkeypatch):
    monkeypatch.setenv(
        "BACKEND_INTERNAL_JWT_SECRET", "test-sse-secret-with-minimum-32-bytes"
    )
    app = _build_sse_test_app(monkeypatch)
    token = create_access_token({"sub": "test-user", "email": "test@example.com"})

    with TestClient(app) as client:
        response = client.get(
            "/sse/audits/123/progress",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "data:" in response.text


@pytest.mark.asyncio
async def test_sse_event_includes_retry(monkeypatch):
    monkeypatch.setattr(sse_route.settings, "SSE_RETRY_MS", 4321, raising=False)
    monkeypatch.setattr(sse_route.settings, "SSE_SOURCE", "db", raising=False)
    monkeypatch.setattr(sse_route.settings, "SSE_MAX_DURATION", 60, raising=False)

    initial_payload = {
        "audit_id": 123,
        "progress": 100,
        "status": "completed",
        "error_message": None,
        "geo_score": 88.5,
        "total_pages": 12,
    }
    request = _DummyRequest(disconnect_after_calls=0)

    generator = sse_route.audit_progress_stream(
        audit_id=123,
        current_user=None,
        request=request,
        initial_payload=initial_payload,
    )
    event_chunk = await anext(generator)
    payload, retry_value = _decode_sse_chunk(event_chunk)
    await generator.aclose()

    assert payload["status"] == "completed"
    assert retry_value == 4321


@pytest.mark.asyncio
async def test_sse_closes_when_client_disconnects(monkeypatch):
    monkeypatch.setattr(sse_route.settings, "SSE_RETRY_MS", 5000, raising=False)
    monkeypatch.setattr(sse_route.settings, "SSE_SOURCE", "db", raising=False)
    monkeypatch.setattr(sse_route.settings, "SSE_MAX_DURATION", 60, raising=False)

    initial_payload = {
        "audit_id": 123,
        "progress": 15,
        "status": "running",
        "error_message": None,
        "geo_score": None,
        "total_pages": 1,
    }
    request = _DummyRequest(disconnect_after_calls=0)

    generator = sse_route.audit_progress_stream(
        audit_id=123,
        current_user=None,
        request=request,
        initial_payload=initial_payload,
    )
    first_chunk = await anext(generator)
    payload, _ = _decode_sse_chunk(first_chunk)
    assert payload["status"] == "running"

    with pytest.raises(StopAsyncIteration):
        await anext(generator)


@pytest.mark.asyncio
async def test_sse_fallback_db_without_redis_events(monkeypatch):
    monkeypatch.setattr(sse_route.settings, "SSE_RETRY_MS", 5000, raising=False)
    monkeypatch.setattr(sse_route.settings, "SSE_SOURCE", "redis", raising=False)
    monkeypatch.setattr(
        sse_route.settings, "SSE_FALLBACK_DB_INTERVAL_SECONDS", 1, raising=False
    )
    monkeypatch.setattr(sse_route.settings, "SSE_MAX_DURATION", 60, raising=False)

    monkeypatch.setattr(sse_route.cache, "enabled", False, raising=False)
    monkeypatch.setattr(sse_route.cache, "redis_client", None, raising=False)

    payloads = [
        {
            "audit_id": 123,
            "progress": 10,
            "status": "running",
            "error_message": None,
            "geo_score": None,
            "total_pages": 1,
        },
        {
            "audit_id": 123,
            "progress": 100,
            "status": "completed",
            "error_message": None,
            "geo_score": 91.2,
            "total_pages": 4,
        },
    ]

    def _fake_load(_audit_id, _current_user):
        return payloads.pop(0)

    monkeypatch.setattr(sse_route, "_load_owned_audit_payload", _fake_load)
    request = _DummyRequest(disconnect_after_calls=10)

    generator = sse_route.audit_progress_stream(
        audit_id=123,
        current_user=object(),
        request=request,
        initial_payload=None,
    )
    first_chunk = await anext(generator)
    second_chunk = await anext(generator)
    first_payload, _ = _decode_sse_chunk(first_chunk)
    second_payload, _ = _decode_sse_chunk(second_chunk)

    assert first_payload["status"] == "running"
    assert second_payload["status"] == "completed"

    with pytest.raises(StopAsyncIteration):
        await anext(generator)


@pytest.mark.asyncio
async def test_sse_redis_mode_still_rechecks_db_when_no_events_arrive(monkeypatch):
    monkeypatch.setattr(sse_route.settings, "SSE_RETRY_MS", 5000, raising=False)
    monkeypatch.setattr(sse_route.settings, "SSE_SOURCE", "redis", raising=False)
    monkeypatch.setattr(
        sse_route.settings, "SSE_FALLBACK_DB_INTERVAL_SECONDS", 1, raising=False
    )
    monkeypatch.setattr(sse_route.settings, "SSE_MAX_DURATION", 60, raising=False)

    monkeypatch.setattr(sse_route.cache, "enabled", True, raising=False)
    monkeypatch.setattr(
        sse_route.cache, "redis_client", _FakeRedisClient(), raising=False
    )

    payloads = [
        {
            "audit_id": 123,
            "progress": 100,
            "status": "completed",
            "error_message": None,
            "geo_score": 93.0,
            "total_pages": 6,
        }
    ]

    def _fake_load(_audit_id, _current_user):
        return payloads.pop(0)

    monkeypatch.setattr(sse_route, "_load_owned_audit_payload", _fake_load)
    request = _NeverDisconnectRequest()

    generator = sse_route.audit_progress_stream(
        audit_id=123,
        current_user=object(),
        request=request,
        initial_payload={
            "audit_id": 123,
            "progress": 15,
            "status": "running",
            "error_message": None,
            "geo_score": None,
            "total_pages": 1,
        },
    )

    first_chunk = await asyncio.wait_for(anext(generator), timeout=1.0)
    second_chunk = await asyncio.wait_for(anext(generator), timeout=3.0)
    first_payload, _ = _decode_sse_chunk(first_chunk)
    second_payload, _ = _decode_sse_chunk(second_chunk)

    assert first_payload["status"] == "running"
    assert second_payload["status"] == "completed"
    await generator.aclose()


@pytest.mark.asyncio
async def test_artifact_sse_closes_after_active_job_reaches_terminal_state(monkeypatch):
    monkeypatch.setattr(sse_route.settings, "SSE_RETRY_MS", 5000, raising=False)
    monkeypatch.setattr(sse_route.settings, "SSE_SOURCE", "db", raising=False)
    monkeypatch.setattr(
        sse_route.settings, "SSE_FALLBACK_DB_INTERVAL_SECONDS", 1, raising=False
    )
    monkeypatch.setattr(sse_route.settings, "SSE_MAX_DURATION", 60, raising=False)

    payloads = [
        {
            "audit_id": 123,
            "pagespeed_status": "completed",
            "pagespeed_available": True,
            "pagespeed_warnings": [],
            "pagespeed_retry_after_seconds": 0,
            "pdf_status": "idle",
            "pdf_available": False,
            "pdf_warnings": [],
            "pdf_retry_after_seconds": 0,
        }
    ]

    def _fake_load(_audit_id, _current_user):
        return payloads.pop(0)

    monkeypatch.setattr(sse_route, "_load_owned_artifact_payload", _fake_load)
    request = _NeverDisconnectRequest()

    generator = sse_route.audit_artifact_stream(
        audit_id=123,
        current_user=object(),
        request=request,
        initial_payload={
            "audit_id": 123,
            "pagespeed_status": "running",
            "pagespeed_available": False,
            "pagespeed_warnings": [],
            "pagespeed_retry_after_seconds": 3,
            "pdf_status": "waiting",
            "pdf_available": False,
            "pdf_warnings": [],
            "pdf_retry_after_seconds": 3,
        },
    )

    first_chunk = await asyncio.wait_for(anext(generator), timeout=1.0)
    second_chunk = await asyncio.wait_for(anext(generator), timeout=3.0)
    first_payload, _ = _decode_sse_chunk(first_chunk)
    second_payload, _ = _decode_sse_chunk(second_chunk)

    assert first_payload["pagespeed_status"] == "running"
    assert second_payload["pagespeed_status"] == "completed"

    with pytest.raises(StopAsyncIteration):
        await anext(generator)
