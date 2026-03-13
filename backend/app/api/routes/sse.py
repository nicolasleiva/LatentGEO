"""
Server-Sent Events (SSE) endpoint for real-time audit progress updates.
Replaces polling to reduce server load and improve responsiveness.
"""

import asyncio
import json
from time import monotonic
from typing import Any, AsyncGenerator

from app.core.access_control import ensure_artifact_snapshot_access, ensure_audit_access
from app.core.auth import AuthUser, get_current_user
from app.core.config import settings
from app.core.logger import get_logger
from app.models import Audit
from app.services.audit_service import AuditService
from app.services.cache_service import cache
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.sse import EventSourceResponse, ServerSentEvent, format_sse_event
from starlette.concurrency import run_in_threadpool

logger = get_logger(__name__)
TERMINAL_STATUSES = {"completed", "failed"}
ACTIVE_ARTIFACT_STATUSES = {"queued", "waiting", "running"}
TERMINAL_ARTICLE_BATCH_STATUSES = {"completed", "failed", "partial_failed"}

router = APIRouter(
    prefix="/sse",
    tags=["sse"],
)


def _load_owned_audit_payload(audit_id: int, current_user: AuthUser) -> dict[str, Any]:
    from app.core.database import SessionLocal

    db_session = SessionLocal()
    try:
        audit = AuditService.get_audit(db_session, audit_id)
        audit = ensure_audit_access(audit, current_user)
        return AuditService.build_progress_payload(audit)
    finally:
        db_session.close()


def _load_owned_artifact_payload(
    audit_id: int, current_user: AuthUser
) -> dict[str, Any]:
    cached_payload = AuditService.get_cached_artifact_payload(audit_id)
    if cached_payload is not None:
        ensure_artifact_snapshot_access(cached_payload, current_user)
        public_cached_payload = AuditService.public_artifact_payload(cached_payload)
        if public_cached_payload is not None:
            return public_cached_payload

    from app.core.database import SessionLocal

    db_session = SessionLocal()
    try:
        payload = AuditService.rebuild_artifact_payload(db_session, audit_id)
        ensure_artifact_snapshot_access(payload, current_user)
        return AuditService.public_artifact_payload(payload) or {
            "audit_id": audit_id,
            "pagespeed_status": "idle",
            "pagespeed_available": False,
            "pagespeed_warnings": [],
            "pagespeed_retry_after_seconds": 0,
            "pdf_status": "idle",
            "pdf_available": False,
            "pdf_warnings": [],
            "pdf_retry_after_seconds": 0,
        }
    finally:
        db_session.close()


def _decode_redis_payload(raw_data: Any, audit_id: int) -> dict[str, Any] | None:
    payload: Any = raw_data
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8")
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return None
    if not isinstance(payload, dict):
        return None
    payload.setdefault("audit_id", audit_id)
    return payload


def _decode_batch_redis_payload(raw_data: Any, batch_id: int) -> dict[str, Any] | None:
    payload: Any = raw_data
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8")
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return None
    if not isinstance(payload, dict):
        return None
    try:
        if int(payload.get("batch_id")) != int(batch_id):
            return None
    except (TypeError, ValueError):
        payload["batch_id"] = batch_id
    return payload


def _serialize_sse_event(event: ServerSentEvent) -> bytes:
    data_str = event.raw_data
    if data_str is None and event.data is not None:
        data_str = json.dumps(event.data, default=str)
    return format_sse_event(
        data_str=data_str,
        event=event.event,
        id=event.id,
        retry=event.retry,
        comment=event.comment,
    )


def _artifact_payload_has_active_job(payload: dict[str, Any]) -> bool:
    return str(payload.get("pdf_status") or "").lower() in ACTIVE_ARTIFACT_STATUSES or (
        str(payload.get("pagespeed_status") or "").lower() in ACTIVE_ARTIFACT_STATUSES
    )


def _artifact_payload_is_terminal(payload: dict[str, Any]) -> bool:
    return not _artifact_payload_has_active_job(payload)


def _article_batch_payload_is_terminal(payload: dict[str, Any]) -> bool:
    return (
        str(payload.get("status") or "").strip().lower()
        in TERMINAL_ARTICLE_BATCH_STATUSES
    )


def _load_owned_article_batch_payload(
    batch_id: int, current_user: AuthUser
) -> dict[str, Any]:
    from app.core.database import SessionLocal
    from app.services.geo_article_engine_service import GeoArticleEngineService

    db_session = SessionLocal()
    try:
        batch_meta = GeoArticleEngineService.get_batch_status_projection(
            db_session, batch_id
        )
        if batch_meta is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Article batch not found",
            )

        audit_projection = AuditService.get_audit_projection(
            db_session,
            batch_meta.audit_id,
            Audit.id,
            Audit.user_id,
            Audit.user_email,
        )
        ensure_audit_access(audit_projection, current_user)

        cached_payload = GeoArticleEngineService.get_cached_batch_status_payload(
            batch_id
        )
        if (
            cached_payload
            and not GeoArticleEngineService.batch_status_payload_requires_refresh(
                cached_payload
            )
        ):
            return cached_payload

        batch = GeoArticleEngineService.get_batch(db_session, batch_id)
        if batch is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Article batch not found",
            )

        from app.api.routes.geo import _reconcile_article_batch_runtime_state

        batch = _reconcile_article_batch_runtime_state(db_session, batch)
        payload = GeoArticleEngineService.serialize_batch_status(batch)
        GeoArticleEngineService.cache_batch_status_payload(payload)
        return payload
    finally:
        db_session.close()


async def audit_progress_stream(
    audit_id: int,
    current_user: AuthUser,
    request: Request,
    initial_payload: dict[str, Any] | None = None,
) -> AsyncGenerator[bytes, None]:
    """
    Stream audit progress updates using Redis as primary source and DB as fallback.
    """
    max_duration = max(30, int(getattr(settings, "SSE_MAX_DURATION", 3600)))
    heartbeat_seconds = max(5, int(getattr(settings, "SSE_HEARTBEAT_SECONDS", 30)))
    fallback_db_interval = max(
        1, int(getattr(settings, "SSE_FALLBACK_DB_INTERVAL_SECONDS", 10))
    )
    retry_ms = max(1000, int(getattr(settings, "SSE_RETRY_MS", 5000)))
    sse_source = (getattr(settings, "SSE_SOURCE", "redis") or "redis").lower()

    use_redis_source = (
        sse_source == "redis" and cache.enabled and bool(cache.redis_client)
    )
    redis_channel = AuditService.progress_channel(audit_id)
    pubsub = None

    start_time = monotonic()
    last_emit_ts = start_time
    last_db_check_ts = 0.0
    last_payload_signature = None
    saw_active_artifact = False

    try:
        initial = initial_payload or await run_in_threadpool(
            _load_owned_audit_payload, audit_id, current_user
        )
        initial_json = json.dumps(initial, default=str)
        yield _serialize_sse_event(
            ServerSentEvent(raw_data=initial_json, retry=retry_ms)
        )
        last_payload_signature = json.dumps(initial, sort_keys=True, default=str)
        last_emit_ts = monotonic()
        last_db_check_ts = last_emit_ts
        saw_active_artifact = _artifact_payload_has_active_job(initial)

        initial_status = str(initial.get("status") or "").lower()
        if initial_status in TERMINAL_STATUSES:
            logger.info(f"SSE stream ended for audit {audit_id}: {initial_status}")
            return

        if use_redis_source:
            try:
                pubsub = cache.redis_client.pubsub()
                await run_in_threadpool(pubsub.subscribe, redis_channel)
                logger.info(f"SSE Redis subscribed: {redis_channel}")
            except Exception as redis_sub_error:
                logger.warning(
                    f"SSE Redis subscription failed for audit {audit_id}: {redis_sub_error}"
                )
                pubsub = None
                use_redis_source = False

        while True:
            now = monotonic()

            if now - start_time > max_duration:
                logger.warning(f"SSE stream timeout for audit {audit_id}")
                yield _serialize_sse_event(
                    ServerSentEvent(
                        raw_data=json.dumps({"error": "Stream timeout"}),
                        retry=retry_ms,
                    )
                )
                break

            if await request.is_disconnected():
                logger.info(f"SSE client disconnected for audit {audit_id}")
                break

            payload: dict[str, Any] | None = None

            if pubsub:
                try:
                    message = await run_in_threadpool(
                        lambda: pubsub.get_message(
                            ignore_subscribe_messages=True,
                            timeout=1.0,
                        )
                    )
                    if message and message.get("type") == "message":
                        payload = _decode_redis_payload(message.get("data"), audit_id)
                except Exception as redis_read_error:
                    logger.warning(
                        f"SSE Redis read failed for audit {audit_id}: {redis_read_error}"
                    )
                    try:
                        await run_in_threadpool(pubsub.unsubscribe, redis_channel)
                        await run_in_threadpool(pubsub.close)
                    except Exception:
                        logger.debug(
                            f"Failed to close Redis pubsub cleanly for audit {audit_id}",
                            exc_info=True,
                        )
                    pubsub = None
                    use_redis_source = False

            should_check_db = (
                payload is None and (now - last_db_check_ts) >= fallback_db_interval
            )

            if should_check_db:
                payload = await run_in_threadpool(
                    _load_owned_audit_payload, audit_id, current_user
                )
                last_db_check_ts = now

            if payload is not None:
                payload_signature = json.dumps(payload, sort_keys=True, default=str)
                saw_active_artifact = (
                    saw_active_artifact or _artifact_payload_has_active_job(payload)
                )
                if payload_signature != last_payload_signature:
                    yield _serialize_sse_event(
                        ServerSentEvent(
                            raw_data=json.dumps(payload, default=str),
                            retry=retry_ms,
                        )
                    )
                    last_payload_signature = payload_signature
                    last_emit_ts = now

                status_value = str(payload.get("status") or "").lower()
                if status_value in TERMINAL_STATUSES:
                    logger.info(
                        f"SSE stream ended for audit {audit_id}: {status_value}"
                    )
                    break
            elif now - last_emit_ts >= heartbeat_seconds:
                yield _serialize_sse_event(
                    ServerSentEvent(comment="heartbeat", retry=retry_ms)
                )
                last_emit_ts = now

            if not pubsub:
                await asyncio.sleep(0.25)

    except asyncio.CancelledError:
        logger.info(f"SSE stream cancelled for audit {audit_id}")
        raise
    except Exception:
        logger.exception(f"Error in SSE stream for audit {audit_id}")
        yield _serialize_sse_event(
            ServerSentEvent(
                raw_data=json.dumps({"error": "Internal server error"}),
                retry=retry_ms,
            )
        )
    finally:
        if pubsub:
            try:
                await run_in_threadpool(pubsub.unsubscribe, redis_channel)
                await run_in_threadpool(pubsub.close)
            except Exception:
                logger.debug(
                    f"SSE Redis cleanup failed for audit {audit_id}",
                    exc_info=True,
                )


async def audit_artifact_stream(
    audit_id: int,
    current_user: AuthUser,
    request: Request,
    initial_payload: dict[str, Any] | None = None,
) -> AsyncGenerator[bytes, None]:
    max_duration = max(30, int(getattr(settings, "SSE_MAX_DURATION", 3600)))
    heartbeat_seconds = max(5, int(getattr(settings, "SSE_HEARTBEAT_SECONDS", 30)))
    fallback_db_interval = max(
        1, int(getattr(settings, "SSE_FALLBACK_DB_INTERVAL_SECONDS", 10))
    )
    retry_ms = max(1000, int(getattr(settings, "SSE_RETRY_MS", 5000)))
    sse_source = (getattr(settings, "SSE_SOURCE", "redis") or "redis").lower()

    use_redis_source = (
        sse_source == "redis" and cache.enabled and bool(cache.redis_client)
    )
    redis_channel = AuditService.artifact_channel(audit_id)
    pubsub = None

    start_time = monotonic()
    last_emit_ts = start_time
    last_db_check_ts = 0.0
    last_payload_signature = None
    saw_active_artifact = False

    try:
        initial = initial_payload or await run_in_threadpool(
            _load_owned_artifact_payload, audit_id, current_user
        )
        initial_json = json.dumps(initial, default=str)
        yield _serialize_sse_event(
            ServerSentEvent(raw_data=initial_json, retry=retry_ms)
        )
        last_payload_signature = json.dumps(initial, sort_keys=True, default=str)
        last_emit_ts = monotonic()
        last_db_check_ts = last_emit_ts
        saw_active_artifact = _artifact_payload_has_active_job(initial)

        if use_redis_source:
            try:
                pubsub = cache.redis_client.pubsub()
                await run_in_threadpool(pubsub.subscribe, redis_channel)
                logger.info(f"Artifact SSE Redis subscribed: {redis_channel}")
            except Exception as redis_sub_error:
                logger.warning(
                    f"Artifact SSE Redis subscription failed for audit {audit_id}: {redis_sub_error}"
                )
                pubsub = None
                use_redis_source = False

        while True:
            now = monotonic()

            if now - start_time > max_duration:
                logger.warning(f"Artifact SSE stream timeout for audit {audit_id}")
                yield _serialize_sse_event(
                    ServerSentEvent(
                        raw_data=json.dumps({"error": "Stream timeout"}),
                        retry=retry_ms,
                    )
                )
                break

            if await request.is_disconnected():
                logger.info(f"Artifact SSE client disconnected for audit {audit_id}")
                break

            payload: dict[str, Any] | None = None

            if pubsub:
                try:
                    message = await run_in_threadpool(
                        lambda: pubsub.get_message(
                            ignore_subscribe_messages=True,
                            timeout=1.0,
                        )
                    )
                    if message and message.get("type") == "message":
                        payload = _decode_redis_payload(message.get("data"), audit_id)
                except Exception as redis_read_error:
                    logger.warning(
                        f"Artifact SSE Redis read failed for audit {audit_id}: {redis_read_error}"
                    )
                    try:
                        await run_in_threadpool(pubsub.unsubscribe, redis_channel)
                        await run_in_threadpool(pubsub.close)
                    except Exception:
                        logger.debug(
                            f"Failed to close artifact Redis pubsub cleanly for audit {audit_id}",
                            exc_info=True,
                        )
                    pubsub = None
                    use_redis_source = False

            should_check_db = (
                payload is None and (now - last_db_check_ts) >= fallback_db_interval
            )

            if should_check_db:
                payload = await run_in_threadpool(
                    _load_owned_artifact_payload, audit_id, current_user
                )
                last_db_check_ts = now

            if payload is not None:
                payload_signature = json.dumps(payload, sort_keys=True, default=str)
                saw_active_artifact = (
                    saw_active_artifact or _artifact_payload_has_active_job(payload)
                )
                if payload_signature != last_payload_signature:
                    yield _serialize_sse_event(
                        ServerSentEvent(
                            raw_data=json.dumps(payload, default=str),
                            retry=retry_ms,
                        )
                    )
                    last_payload_signature = payload_signature
                    last_emit_ts = now
                if saw_active_artifact and _artifact_payload_is_terminal(payload):
                    logger.info(
                        "Artifact SSE stream ended for audit %s: terminal payload reached",
                        audit_id,
                    )
                    break
            elif now - last_emit_ts >= heartbeat_seconds:
                yield _serialize_sse_event(
                    ServerSentEvent(comment="heartbeat", retry=retry_ms)
                )
                last_emit_ts = now

            if not pubsub:
                await asyncio.sleep(0.25)

    except asyncio.CancelledError:
        logger.info(f"Artifact SSE stream cancelled for audit {audit_id}")
        raise
    except Exception:
        logger.exception(f"Error in artifact SSE stream for audit {audit_id}")
        yield _serialize_sse_event(
            ServerSentEvent(
                raw_data=json.dumps({"error": "Internal server error"}),
                retry=retry_ms,
            )
        )
    finally:
        if pubsub:
            try:
                await run_in_threadpool(pubsub.unsubscribe, redis_channel)
                await run_in_threadpool(pubsub.close)
            except Exception:
                logger.debug(
                    f"Artifact SSE Redis cleanup failed for audit {audit_id}",
                    exc_info=True,
                )


async def article_batch_progress_stream(
    batch_id: int,
    current_user: AuthUser,
    request: Request,
    initial_payload: dict[str, Any] | None = None,
) -> AsyncGenerator[bytes, None]:
    from app.services.geo_article_engine_service import GeoArticleEngineService

    max_duration = max(30, int(getattr(settings, "SSE_MAX_DURATION", 3600)))
    heartbeat_seconds = max(5, int(getattr(settings, "SSE_HEARTBEAT_SECONDS", 30)))
    fallback_db_interval = max(
        1, int(getattr(settings, "SSE_FALLBACK_DB_INTERVAL_SECONDS", 10))
    )
    retry_ms = max(1000, int(getattr(settings, "SSE_RETRY_MS", 5000)))
    sse_source = (getattr(settings, "SSE_SOURCE", "redis") or "redis").lower()

    use_redis_source = (
        sse_source == "redis" and cache.enabled and bool(cache.redis_client)
    )
    redis_channel = GeoArticleEngineService.article_batch_channel(batch_id)
    pubsub = None

    start_time = monotonic()
    last_emit_ts = start_time
    last_db_check_ts = 0.0
    last_payload_signature = None

    try:
        initial = initial_payload or await run_in_threadpool(
            _load_owned_article_batch_payload, batch_id, current_user
        )
        initial_json = json.dumps(initial, default=str)
        yield _serialize_sse_event(
            ServerSentEvent(raw_data=initial_json, retry=retry_ms)
        )
        last_payload_signature = json.dumps(initial, sort_keys=True, default=str)
        last_emit_ts = monotonic()
        last_db_check_ts = last_emit_ts

        if _article_batch_payload_is_terminal(initial):
            logger.info(
                "Article batch SSE stream ended for batch %s: terminal payload reached",
                batch_id,
            )
            return

        if use_redis_source:
            try:
                pubsub = cache.redis_client.pubsub()
                await run_in_threadpool(pubsub.subscribe, redis_channel)
                logger.info("Article batch SSE Redis subscribed: %s", redis_channel)
            except Exception as redis_sub_error:
                logger.warning(
                    "Article batch SSE Redis subscription failed for batch %s: %s",
                    batch_id,
                    redis_sub_error,
                )
                pubsub = None
                use_redis_source = False

        while True:
            now = monotonic()

            if now - start_time > max_duration:
                logger.warning(
                    "Article batch SSE stream timeout for batch %s", batch_id
                )
                yield _serialize_sse_event(
                    ServerSentEvent(
                        raw_data=json.dumps({"error": "Stream timeout"}),
                        retry=retry_ms,
                    )
                )
                break

            if await request.is_disconnected():
                logger.info(
                    "Article batch SSE client disconnected for batch %s", batch_id
                )
                break

            payload: dict[str, Any] | None = None

            if pubsub:
                try:
                    message = await run_in_threadpool(
                        lambda: pubsub.get_message(
                            ignore_subscribe_messages=True,
                            timeout=1.0,
                        )
                    )
                    if message and message.get("type") == "message":
                        payload = _decode_batch_redis_payload(
                            message.get("data"), batch_id
                        )
                except Exception as redis_read_error:
                    logger.warning(
                        "Article batch SSE Redis read failed for batch %s: %s",
                        batch_id,
                        redis_read_error,
                    )
                    try:
                        await run_in_threadpool(pubsub.unsubscribe, redis_channel)
                        await run_in_threadpool(pubsub.close)
                    except Exception:
                        logger.debug(
                            "Failed to close article batch Redis pubsub cleanly for batch %s",
                            batch_id,
                            exc_info=True,
                        )
                    pubsub = None
                    use_redis_source = False

            should_check_db = (
                payload is None and (now - last_db_check_ts) >= fallback_db_interval
            )

            if should_check_db:
                payload = await run_in_threadpool(
                    _load_owned_article_batch_payload, batch_id, current_user
                )
                last_db_check_ts = now

            if payload is not None:
                payload_signature = json.dumps(payload, sort_keys=True, default=str)
                if payload_signature != last_payload_signature:
                    yield _serialize_sse_event(
                        ServerSentEvent(
                            raw_data=json.dumps(payload, default=str),
                            retry=retry_ms,
                        )
                    )
                    last_payload_signature = payload_signature
                    last_emit_ts = now

                if _article_batch_payload_is_terminal(payload):
                    logger.info(
                        "Article batch SSE stream ended for batch %s: terminal payload reached",
                        batch_id,
                    )
                    break
            elif now - last_emit_ts >= heartbeat_seconds:
                yield _serialize_sse_event(
                    ServerSentEvent(comment="heartbeat", retry=retry_ms)
                )
                last_emit_ts = now

            if not pubsub:
                await asyncio.sleep(0.25)

    except asyncio.CancelledError:
        logger.info("Article batch SSE stream cancelled for batch %s", batch_id)
        raise
    except Exception:
        logger.exception("Error in article batch SSE stream for batch %s", batch_id)
        yield _serialize_sse_event(
            ServerSentEvent(
                raw_data=json.dumps({"error": "Internal server error"}),
                retry=retry_ms,
            )
        )
    finally:
        if pubsub:
            try:
                await run_in_threadpool(pubsub.unsubscribe, redis_channel)
                await run_in_threadpool(pubsub.close)
            except Exception:
                logger.debug(
                    "Article batch SSE Redis cleanup failed for batch %s",
                    batch_id,
                    exc_info=True,
                )


@router.get("/audits/{audit_id}/progress")
async def stream_audit_progress(
    request: Request,
    audit_id: int,
    current_user: AuthUser = Depends(get_current_user),
):
    """
    SSE endpoint for streaming audit progress updates.
    Requires standard Authorization: Bearer header.
    """
    initial_payload = await run_in_threadpool(
        _load_owned_audit_payload, audit_id, current_user
    )

    logger.info(f"SSE connection established for audit {audit_id}")

    return EventSourceResponse(
        audit_progress_stream(audit_id, current_user, request, initial_payload),
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/audits/{audit_id}/artifacts")
async def stream_audit_artifacts(
    request: Request,
    audit_id: int,
    current_user: AuthUser = Depends(get_current_user),
):
    initial_payload = await run_in_threadpool(
        _load_owned_artifact_payload, audit_id, current_user
    )

    logger.info(f"Artifact SSE connection established for audit {audit_id}")

    return EventSourceResponse(
        audit_artifact_stream(audit_id, current_user, request, initial_payload),
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/article-engine/{batch_id}/progress")
async def stream_article_batch_progress(
    request: Request,
    batch_id: int,
    current_user: AuthUser = Depends(get_current_user),
):
    initial_payload = await run_in_threadpool(
        _load_owned_article_batch_payload, batch_id, current_user
    )

    logger.info("Article batch SSE connection established for batch %s", batch_id)

    return EventSourceResponse(
        article_batch_progress_stream(batch_id, current_user, request, initial_payload),
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
