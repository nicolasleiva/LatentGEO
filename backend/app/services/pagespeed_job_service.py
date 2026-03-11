"""
Persistent PageSpeed job orchestration helpers.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Iterable, Optional

from fastapi import HTTPException
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logger import get_logger
from app.models import Audit, AuditPageSpeedJob, AuditPageSpeedJobStatus
from app.schemas import AuditPageSpeedStatusResponse, PDFStatusError
from app.services.audit_service import AuditService
from app.services.cache_service import cache

logger = get_logger(__name__)

ACTIVE_PAGESPEED_JOB_STATUSES = {
    AuditPageSpeedJobStatus.QUEUED.value,
    AuditPageSpeedJobStatus.RUNNING.value,
}
DEFAULT_PAGESPEED_RETRY_AFTER_SECONDS = 3

_pagespeed_generation_in_progress: set[int] = set()
_pagespeed_generation_tokens: dict[int, str] = {}


def pagespeed_lock_key(audit_id: int) -> str:
    return f"pagespeed_generation_lock:{audit_id}"


def acquire_pagespeed_generation_lock(
    audit_id: int,
) -> tuple[bool, str | None, str | None]:
    token = str(uuid.uuid4())
    ttl_seconds = max(30, int(settings.PDF_LOCK_TTL_SECONDS or 900))

    if cache.enabled and cache.redis_client:
        try:
            acquired = bool(
                cache.redis_client.set(
                    pagespeed_lock_key(audit_id),
                    token,
                    nx=True,
                    ex=ttl_seconds,
                )
            )
            if acquired:
                return True, token, "redis"
            return False, None, "redis"
        except Exception as exc:
            if not settings.DEBUG:
                logger.error(
                    "Redis PageSpeed lock unavailable for audit %s; refusing generation in production: %s",
                    audit_id,
                    exc,
                )
                return False, None, "unavailable"
            logger.warning(
                "Redis PageSpeed lock unavailable for audit %s; falling back to local lock in debug: %s",
                audit_id,
                exc,
            )
    else:
        if not settings.DEBUG:
            logger.error(
                "Redis PageSpeed lock disabled for audit %s; refusing generation in production",
                audit_id,
            )
            return False, None, "unavailable"
        logger.warning(
            "Redis PageSpeed lock disabled for audit %s; using local in-memory lock in debug",
            audit_id,
        )

    if audit_id in _pagespeed_generation_in_progress:
        return False, None, "local"

    _pagespeed_generation_in_progress.add(audit_id)
    _pagespeed_generation_tokens[audit_id] = token
    return True, token, "local"


def release_pagespeed_generation_lock(
    audit_id: int, token: str | None, mode: str | None
) -> None:
    if not token or not mode:
        return

    if mode == "redis":
        if cache.enabled and cache.redis_client:
            try:
                lock_key = pagespeed_lock_key(audit_id)
                current_token = cache.redis_client.get(lock_key)
                if current_token == token:
                    cache.redis_client.delete(lock_key)
            except Exception as exc:
                logger.warning(
                    "Failed to release Redis PageSpeed lock for audit %s: %s",
                    audit_id,
                    exc,
                )
        return

    current_token = _pagespeed_generation_tokens.get(audit_id)
    if current_token and current_token != token:
        logger.warning(
            "PageSpeed local lock token mismatch for audit %s; forcing release",
            audit_id,
        )
    _pagespeed_generation_tokens.pop(audit_id, None)
    _pagespeed_generation_in_progress.discard(audit_id)


class PageSpeedJobService:
    @staticmethod
    def build_status_response_from_artifact_payload(
        payload: dict[str, Any],
        *,
        message: str | None = None,
    ) -> AuditPageSpeedStatusResponse:
        error_payload = payload.get("pagespeed_error")
        error = None
        if isinstance(error_payload, dict):
            error = PDFStatusError(
                code=error_payload.get("code") or None,
                message=error_payload.get("message") or None,
            )

        return AuditPageSpeedStatusResponse(
            audit_id=int(payload.get("audit_id")),
            job_id=payload.get("pagespeed_job_id"),
            status=str(payload.get("pagespeed_status") or "idle"),
            pagespeed_available=bool(payload.get("pagespeed_available")),
            warnings=PageSpeedJobService.normalize_warnings(
                payload.get("pagespeed_warnings")
            ),
            error=error,
            started_at=payload.get("pagespeed_started_at"),
            completed_at=payload.get("pagespeed_completed_at"),
            retry_after_seconds=max(
                0, int(payload.get("pagespeed_retry_after_seconds") or 0)
            ),
            message=(
                message if message is not None else payload.get("pagespeed_message")
            ),
        )

    @staticmethod
    def get_job(db: Session, audit_id: int) -> AuditPageSpeedJob | None:
        return (
            db.query(AuditPageSpeedJob)
            .filter(AuditPageSpeedJob.audit_id == audit_id)
            .first()
        )

    @staticmethod
    def has_active_job(job: AuditPageSpeedJob | None) -> bool:
        return bool(job and job.status in ACTIVE_PAGESPEED_JOB_STATUSES)

    @staticmethod
    def normalize_warnings(raw_warnings: Optional[Iterable[Any]]) -> list[str]:
        normalized: list[str] = []
        for warning in raw_warnings or []:
            message = " ".join(str(warning or "").split()).strip()
            if message:
                normalized.append(message)
        return normalized

    @staticmethod
    def runtime_technical_detail(exc: Exception) -> str | None:
        if isinstance(exc, HTTPException):
            if isinstance(exc.detail, dict):
                error_code = exc.detail.get("error_code")
                if error_code:
                    return f"HTTPException:{error_code}"
            return f"HTTPException:{exc.status_code}"
        return type(exc).__name__

    @staticmethod
    def classify_error(exc: Exception) -> tuple[str, str]:
        if isinstance(exc, HTTPException):
            if isinstance(exc.detail, dict):
                error_code = str(exc.detail.get("error_code") or "").strip()
                message = str(
                    exc.detail.get("message")
                    or exc.detail.get("detail")
                    or exc.detail.get("error")
                    or "HTTP error during PageSpeed generation."
                ).strip()
                return error_code or f"http_{exc.status_code}", message
            detail = str(exc.detail).strip() or "HTTP error during PageSpeed generation."
            return f"http_{exc.status_code}", detail

        if isinstance(exc, (OperationalError, DBAPIError)):
            return "db_unavailable", "Database is temporarily unavailable."

        name = type(exc).__name__.strip() or "PageSpeedGenerationFailed"
        return name.lower(), str(exc).strip() or name

    @staticmethod
    def has_usable_pagespeed_data(
        audit: Audit,
        *,
        require_complete: bool = True,
    ) -> bool:
        pagespeed_data = audit.pagespeed_data if isinstance(audit.pagespeed_data, dict) else {}
        if not pagespeed_data:
            return False

        if require_complete:
            mobile = pagespeed_data.get("mobile")
            desktop = pagespeed_data.get("desktop")
            if not isinstance(mobile, dict) or not isinstance(desktop, dict):
                return False
            if mobile.get("error") or desktop.get("error"):
                return False

        try:
            from app.services.pdf_service import PDFService

            return not PDFService._is_pagespeed_stale(pagespeed_data)
        except Exception:
            return True

    @staticmethod
    def extract_provider_warnings(
        pagespeed_data: dict[str, Any],
        *,
        strategy: str,
    ) -> tuple[list[str], dict[str, Any]]:
        warnings: list[str] = []
        successful_results: dict[str, Any] = {}

        if strategy == "both":
            candidates = [
                ("mobile", pagespeed_data.get("mobile")),
                ("desktop", pagespeed_data.get("desktop")),
            ]
        else:
            candidates = [(strategy, pagespeed_data.get(strategy))]

        for label, payload in candidates:
            if not isinstance(payload, dict):
                continue
            error_message = str(payload.get("error") or "").strip()
            provider_message = str(payload.get("provider_message") or "").strip()
            if error_message:
                warnings.append(
                    f"{label.capitalize()} PageSpeed unavailable: "
                    f"{provider_message or error_message}"
                )
                continue
            successful_results[label] = payload

        return warnings, successful_results

    @staticmethod
    def persist_runtime_warnings(
        db: Session,
        audit_id: int,
        warnings: list[str],
    ) -> None:
        for index, message in enumerate(PageSpeedJobService.normalize_warnings(warnings), start=1):
            AuditService.append_runtime_diagnostic(
                db,
                audit_id,
                source="pagespeed",
                stage="run-pagespeed",
                severity="warning",
                code=f"pagespeed_warning_{index}",
                message=message,
            )

    @staticmethod
    def build_status_response(
        *,
        audit: Audit,
        job: AuditPageSpeedJob | None = None,
        retry_after_seconds: int = 0,
        message: str | None = None,
    ) -> AuditPageSpeedStatusResponse:
        if job is None:
            if PageSpeedJobService.has_usable_pagespeed_data(audit, require_complete=False):
                return AuditPageSpeedStatusResponse(
                    audit_id=audit.id,
                    job_id=None,
                    status="completed",
                    pagespeed_available=True,
                    warnings=[],
                    error=None,
                    started_at=None,
                    completed_at=None,
                    retry_after_seconds=0,
                    message=message,
                )
            return AuditPageSpeedStatusResponse(
                audit_id=audit.id,
                job_id=None,
                status="idle",
                pagespeed_available=False,
                warnings=[],
                error=None,
                started_at=None,
                completed_at=None,
                retry_after_seconds=0,
                message=message,
            )

        error = None
        if job.status == AuditPageSpeedJobStatus.FAILED.value and (
            job.error_code or job.error_message
        ):
            error = PDFStatusError(
                code=job.error_code or None,
                message=job.error_message or None,
            )

        return AuditPageSpeedStatusResponse(
            audit_id=audit.id,
            job_id=job.id,
            status=job.status,
            pagespeed_available=PageSpeedJobService.has_usable_pagespeed_data(
                audit, require_complete=False
            ),
            warnings=PageSpeedJobService.normalize_warnings(job.warnings),
            error=error,
            started_at=job.started_at,
            completed_at=job.completed_at,
            retry_after_seconds=(
                retry_after_seconds
                if job.status in ACTIVE_PAGESPEED_JOB_STATUSES
                else 0
            ),
            message=message,
        )

    @staticmethod
    def publish_status_event(
        db: Session,
        audit: Audit,
        *,
        job: AuditPageSpeedJob | None = None,
    ) -> None:
        from app.services.pdf_job_service import PDFJobService

        pdf_job = PDFJobService.get_job(db, audit.id)
        pdf_report = PDFJobService.get_latest_pdf_report(db, audit.id)
        AuditService.publish_artifact_event(
            audit.id,
            AuditService.build_artifact_payload(
                audit,
                pagespeed_job=job or PageSpeedJobService.get_job(db, audit.id),
                pdf_job=pdf_job,
                pdf_report=pdf_report,
            ),
        )

    @staticmethod
    def queue_job(
        db: Session,
        *,
        audit: Audit,
        requested_by_user_id: str | None,
        strategy: str = "both",
        force_refresh: bool = False,
    ) -> AuditPageSpeedJob:
        job = PageSpeedJobService.get_job(db, audit.id)
        if job is None:
            job = AuditPageSpeedJob(audit_id=audit.id)
            db.add(job)

        job.requested_by_user_id = requested_by_user_id
        job.status = AuditPageSpeedJobStatus.QUEUED.value
        job.strategy = "both" if strategy not in {"mobile", "desktop", "both"} else strategy
        job.celery_task_id = None
        job.force_refresh = bool(force_refresh)
        job.warnings = []
        job.error_code = None
        job.error_message = None
        job.started_at = None
        job.completed_at = None
        job.updated_at = datetime.now(UTC)

        db.commit()
        db.refresh(job)
        PageSpeedJobService.publish_status_event(db, audit, job=job)
        return job

    @staticmethod
    def mark_job_running(db: Session, audit: Audit, job: AuditPageSpeedJob) -> AuditPageSpeedJob:
        now = datetime.now(UTC)
        job.status = AuditPageSpeedJobStatus.RUNNING.value
        job.started_at = now
        job.completed_at = None
        job.updated_at = now
        db.add(job)
        db.commit()
        db.refresh(job)
        PageSpeedJobService.publish_status_event(db, audit, job=job)
        return job

    @staticmethod
    def mark_job_completed(
        db: Session,
        audit: Audit,
        job: AuditPageSpeedJob,
        *,
        warnings: list[str],
    ) -> AuditPageSpeedJob:
        now = datetime.now(UTC)
        job.status = AuditPageSpeedJobStatus.COMPLETED.value
        job.warnings = warnings
        job.error_code = None
        job.error_message = None
        job.completed_at = now
        job.updated_at = now
        db.add(job)
        db.commit()
        db.refresh(job)
        PageSpeedJobService.publish_status_event(db, audit, job=job)
        return job

    @staticmethod
    def mark_job_failed(
        db: Session,
        audit: Audit,
        job: AuditPageSpeedJob,
        *,
        error_code: str,
        error_message: str,
        warnings: Optional[list[str]] = None,
    ) -> AuditPageSpeedJob:
        now = datetime.now(UTC)
        job.status = AuditPageSpeedJobStatus.FAILED.value
        job.error_code = error_code
        job.error_message = error_message[:500]
        job.warnings = warnings or []
        job.completed_at = now
        job.updated_at = now
        db.add(job)
        db.commit()
        db.refresh(job)
        PageSpeedJobService.publish_status_event(db, audit, job=job)
        return job

    @staticmethod
    def enqueue_job_task(db: Session, audit: Audit, job: AuditPageSpeedJob) -> AuditPageSpeedJob:
        from app.workers.tasks import run_pagespeed_generation_job_task

        task = run_pagespeed_generation_job_task.delay(job.id)
        job.celery_task_id = getattr(task, "id", None)
        job.updated_at = datetime.now(UTC)
        db.add(job)
        db.commit()
        db.refresh(job)
        PageSpeedJobService.publish_status_event(db, audit, job=job)
        return job

    @staticmethod
    def queue_if_needed(
        db: Session,
        *,
        audit: Audit,
        requested_by_user_id: str | None,
        strategy: str = "both",
        force_refresh: bool = False,
    ) -> AuditPageSpeedJob | None:
        if not settings.ENABLE_PAGESPEED or not settings.GOOGLE_PAGESPEED_API_KEY:
            return None

        existing_job = PageSpeedJobService.get_job(db, audit.id)
        if PageSpeedJobService.has_active_job(existing_job):
            return existing_job

        require_complete = strategy == "both"
        if (
            not force_refresh
            and PageSpeedJobService.has_usable_pagespeed_data(
                audit, require_complete=require_complete
            )
        ):
            return existing_job

        job = PageSpeedJobService.queue_job(
            db,
            audit=audit,
            requested_by_user_id=requested_by_user_id,
            strategy=strategy,
            force_refresh=force_refresh,
        )
        return PageSpeedJobService.enqueue_job_task(db, audit, job)

    @staticmethod
    async def _notify_pagespeed_completed_if_configured(audit: Audit) -> None:
        if not settings.DEFAULT_WEBHOOK_URL:
            return

        try:
            from app.services.webhook_service import WebhookEventType, WebhookService

            await WebhookService.send_webhook(
                url=settings.DEFAULT_WEBHOOK_URL,
                event_type=WebhookEventType.PAGESPEED_COMPLETED,
                payload={
                    "audit_id": audit.id,
                    "url": str(audit.url),
                },
                secret=settings.WEBHOOK_SECRET,
            )
        except Exception as exc:
            logger.warning(
                "pagespeed_completed_webhook_failed audit_id=%s error=%s",
                audit.id,
                exc,
            )

    @staticmethod
    async def execute_job(db: Session, job_id: int) -> AuditPageSpeedJob:
        from app.core.llm_kimi import get_llm_function
        from app.services.pipeline_service import PipelineService
        from app.services.pagespeed_service import PageSpeedService
        from app.workers.tasks import _save_pagespeed_analysis, _save_pagespeed_data

        job = db.query(AuditPageSpeedJob).filter(AuditPageSpeedJob.id == job_id).first()
        if job is None:
            raise ValueError(f"PageSpeed job {job_id} not found")

        audit = db.query(Audit).filter(Audit.id == job.audit_id).first()
        if audit is None:
            raise ValueError(f"Audit {job.audit_id} not found for PageSpeed job {job_id}")

        acquired_lock, lock_token, lock_mode = acquire_pagespeed_generation_lock(audit.id)
        if not acquired_lock:
            if lock_mode == "unavailable":
                return PageSpeedJobService.mark_job_failed(
                    db,
                    audit,
                    job,
                    error_code="lock_unavailable",
                    error_message="Distributed PageSpeed lock backend is unavailable. Redis is required.",
                )
            logger.info(
                "PageSpeed job %s skipped because another worker already holds the lock for audit %s",
                job_id,
                audit.id,
            )
            return job

        try:
            job = PageSpeedJobService.mark_job_running(db, audit, job)
            strategy = job.strategy if job.strategy in {"mobile", "desktop", "both"} else "both"

            if strategy == "both":
                pagespeed_data = await PageSpeedService.analyze_both_strategies(
                    url=str(audit.url),
                    api_key=settings.GOOGLE_PAGESPEED_API_KEY,
                )
            else:
                result = await PageSpeedService.analyze_url(
                    url=str(audit.url),
                    api_key=settings.GOOGLE_PAGESPEED_API_KEY,
                    strategy=strategy,
                )
                pagespeed_data = {strategy: result}

            if not isinstance(pagespeed_data, dict) or not pagespeed_data:
                raise RuntimeError("PageSpeed analysis returned no data.")

            warnings, successful_results = PageSpeedJobService.extract_provider_warnings(
                pagespeed_data,
                strategy=strategy,
            )

            merged_pagespeed = dict(audit.pagespeed_data or {})
            if successful_results:
                merged_pagespeed.update(successful_results)
                audit.pagespeed_data = merged_pagespeed
                db.add(audit)
                db.commit()
                db.refresh(audit)

                _save_pagespeed_data(audit.id, merged_pagespeed)

                try:
                    llm_function = get_llm_function()
                    ps_analysis = await PipelineService.generate_pagespeed_analysis(
                        merged_pagespeed,
                        llm_function,
                    )
                    if ps_analysis:
                        _save_pagespeed_analysis(audit.id, ps_analysis)
                except Exception as analysis_exc:
                    warnings.append(
                        "PageSpeed diagnostics were collected, but the analysis summary could not be refreshed."
                    )
                    logger.warning(
                        "PageSpeed analysis summary generation failed for audit %s: %s",
                        audit.id,
                        analysis_exc,
                    )

            normalized_warnings = PageSpeedJobService.normalize_warnings(warnings)
            if normalized_warnings:
                PageSpeedJobService.persist_runtime_warnings(
                    db,
                    audit.id,
                    normalized_warnings,
                )

            if not successful_results and normalized_warnings:
                logger.warning(
                    "PageSpeed provider returned warnings without usable data for audit %s",
                    audit.id,
                )

            if not successful_results and not normalized_warnings:
                raise RuntimeError("PageSpeed analysis returned no usable data.")

            job = PageSpeedJobService.mark_job_completed(
                db,
                audit,
                job,
                warnings=normalized_warnings,
            )
            await PageSpeedJobService._notify_pagespeed_completed_if_configured(audit)

            from app.services.pdf_job_service import PDFJobService

            PDFJobService.resume_waiting_job_after_pagespeed(
                db,
                audit=audit,
                pagespeed_job=job,
            )
            return job
        except Exception as exc:
            logger.error("PageSpeed job failed for audit %s", audit.id, exc_info=True)
            db.rollback()
            job = (
                db.query(AuditPageSpeedJob)
                .filter(AuditPageSpeedJob.id == job_id)
                .first()
                or job
            )
            error_code, error_message = PageSpeedJobService.classify_error(exc)
            job = PageSpeedJobService.mark_job_failed(
                db,
                audit,
                job,
                error_code=error_code,
                error_message=error_message,
            )
            AuditService.append_runtime_diagnostic(
                db,
                audit.id,
                source="pagespeed",
                stage="run-pagespeed",
                severity="error",
                code=error_code,
                message="PageSpeed analysis failed before performance data could be refreshed.",
                technical_detail=PageSpeedJobService.runtime_technical_detail(exc),
            )

            from app.services.pdf_job_service import PDFJobService

            PDFJobService.resume_waiting_job_after_pagespeed(
                db,
                audit=audit,
                pagespeed_job=job,
            )
            return job
        finally:
            release_pagespeed_generation_lock(audit.id, lock_token, lock_mode)
