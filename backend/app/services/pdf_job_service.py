"""
Persistent PDF job orchestration helpers.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from typing import Any, Iterable, Optional

from app.core.config import settings
from app.core.logger import get_logger
from app.models import Audit, AuditPageSpeedJob, AuditPdfJob, AuditPdfJobStatus, Report
from app.schemas import AuditPDFStatusResponse, PDFStatusError
from app.services.audit_service import AuditService
from app.services.cache_service import cache
from fastapi import HTTPException
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.orm import Session

logger = get_logger(__name__)

ACTIVE_PDF_JOB_STATUSES = {
    AuditPdfJobStatus.QUEUED.value,
    AuditPdfJobStatus.WAITING.value,
    AuditPdfJobStatus.RUNNING.value,
}
DEFAULT_PDF_RETRY_AFTER_SECONDS = 3

_pdf_generation_in_progress: set[int] = set()
_pdf_generation_tokens: dict[int, str] = {}
_REDIS_COMPARE_AND_DELETE_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
end
return 0
"""


def pdf_lock_key(audit_id: int) -> str:
    return f"pdf_generation_lock:{audit_id}"


def acquire_pdf_generation_lock(audit_id: int) -> tuple[bool, str | None, str | None]:
    """
    Acquire PDF generation lock using Redis in production and memory in debug fallback.
    """
    token = str(uuid.uuid4())
    ttl_seconds = max(1800, int(settings.PDF_LOCK_TTL_SECONDS or 1800))

    if cache.enabled and cache.redis_client:
        try:
            acquired = bool(
                cache.redis_client.set(
                    pdf_lock_key(audit_id),
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
                    "Redis PDF lock unavailable for audit %s; refusing generation in production: %s",
                    audit_id,
                    exc,
                )
                return False, None, "unavailable"
            logger.warning(
                "Redis PDF lock unavailable for audit %s; falling back to local lock in debug: %s",
                audit_id,
                exc,
            )
    else:
        if not settings.DEBUG:
            logger.error(
                "Redis PDF lock disabled for audit %s; refusing generation in production",
                audit_id,
            )
            return False, None, "unavailable"
        logger.warning(
            "Redis PDF lock disabled for audit %s; using local in-memory lock in debug",
            audit_id,
        )

    if audit_id in _pdf_generation_in_progress:
        return False, None, "local"

    _pdf_generation_in_progress.add(audit_id)
    _pdf_generation_tokens[audit_id] = token
    return True, token, "local"


def release_pdf_generation_lock(
    audit_id: int, token: str | None, mode: str | None
) -> None:
    if not token or not mode:
        return

    if mode == "redis":
        if cache.enabled and cache.redis_client:
            try:
                lock_key = pdf_lock_key(audit_id)
                if hasattr(cache.redis_client, "eval"):
                    cache.redis_client.eval(
                        _REDIS_COMPARE_AND_DELETE_SCRIPT,
                        1,
                        lock_key,
                        token,
                    )
                else:
                    current_token = cache.redis_client.get(lock_key)
                    if current_token == token:
                        cache.redis_client.delete(lock_key)
            except Exception as exc:
                logger.warning(
                    "Failed to release Redis PDF lock for audit %s: %s",
                    audit_id,
                    exc,
                )
        return

    current_token = _pdf_generation_tokens.get(audit_id)
    if current_token and current_token != token:
        logger.warning(
            "PDF local lock token mismatch for audit %s; forcing release",
            audit_id,
        )
    _pdf_generation_tokens.pop(audit_id, None)
    _pdf_generation_in_progress.discard(audit_id)


class PDFJobService:
    @staticmethod
    def build_status_response_from_artifact_payload(
        payload: dict[str, Any],
        *,
        message: str | None = None,
    ) -> AuditPDFStatusResponse:
        error_payload = payload.get("pdf_error")
        error = None
        if isinstance(error_payload, dict):
            error = PDFStatusError(
                code=error_payload.get("code") or None,
                message=error_payload.get("message") or None,
            )

        return AuditPDFStatusResponse(
            audit_id=int(payload.get("audit_id")),
            job_id=payload.get("pdf_job_id"),
            status=str(payload.get("pdf_status") or "idle"),
            download_ready=bool(payload.get("pdf_available")),
            report_id=payload.get("pdf_report_id"),
            warnings=PDFJobService.normalize_warnings(payload.get("pdf_warnings")),
            error=error,
            started_at=payload.get("pdf_started_at"),
            completed_at=payload.get("pdf_completed_at"),
            retry_after_seconds=max(
                0, int(payload.get("pdf_retry_after_seconds") or 0)
            ),
            waiting_on=payload.get("pdf_waiting_on"),
            dependency_job_id=payload.get("pdf_dependency_job_id"),
            message=message if message is not None else payload.get("pdf_message"),
        )

    @staticmethod
    def get_job(db: Session, audit_id: int) -> AuditPdfJob | None:
        return db.query(AuditPdfJob).filter(AuditPdfJob.audit_id == audit_id).first()

    @staticmethod
    def get_latest_pdf_report(db: Session, audit_id: int) -> Report | None:
        return (
            db.query(Report)
            .filter(Report.audit_id == audit_id, Report.report_type == "PDF")
            .order_by(Report.created_at.desc(), Report.id.desc())
            .first()
        )

    @staticmethod
    def has_active_job(job: AuditPdfJob | None) -> bool:
        return bool(job and job.status in ACTIVE_PDF_JOB_STATUSES)

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
    def persist_runtime_diagnostic_safely(
        db: Session,
        audit_id: int,
        *,
        source: str,
        stage: str,
        severity: str,
        code: str,
        message: str,
        technical_detail: str | None = None,
    ) -> None:
        try:
            AuditService.append_runtime_diagnostic(
                db,
                audit_id,
                source=source,
                stage=stage,
                severity=severity,
                code=code,
                message=message,
                technical_detail=technical_detail,
            )
        except Exception as diag_err:
            logger.warning(
                "runtime_diagnostic_persist_failed audit_id=%s code=%s error=%s",
                audit_id,
                code,
                diag_err,
            )

    @staticmethod
    def persist_generation_warnings(
        db: Session, audit_id: int, warnings: Optional[Iterable[Any]]
    ) -> list[str]:
        normalized = PDFJobService.normalize_warnings(warnings)
        for index, message in enumerate(normalized, start=1):
            PDFJobService.persist_runtime_diagnostic_safely(
                db,
                audit_id,
                source="pdf",
                stage="generate-pdf",
                severity="warning",
                code=f"pdf_generation_warning_{index}",
                message=message,
            )
        return normalized

    @staticmethod
    def classify_error(exc: Exception) -> tuple[str, str]:
        if isinstance(exc, HTTPException):
            if isinstance(exc.detail, dict):
                error_code = str(exc.detail.get("error_code") or "").strip()
                message = str(
                    exc.detail.get("message")
                    or exc.detail.get("detail")
                    or exc.detail.get("error")
                    or "HTTP error during PDF generation."
                ).strip()
                return error_code or f"http_{exc.status_code}", message
            detail = str(exc.detail).strip() or "HTTP error during PDF generation."
            return f"http_{exc.status_code}", detail

        if isinstance(exc, (OperationalError, DBAPIError)):
            return "db_unavailable", "Database is temporarily unavailable."

        snake_name = re.sub(r"(?<!^)(?=[A-Z])", "_", type(exc).__name__).lower()
        return snake_name or "pdf_generation_failed", str(exc).strip() or str(type(exc))

    @staticmethod
    def build_status_response(
        *,
        audit_id: int,
        job: AuditPdfJob | None = None,
        report: Report | None = None,
        retry_after_seconds: int = 0,
        message: str | None = None,
    ) -> AuditPDFStatusResponse:
        if job is None:
            if report and report.file_path:
                return AuditPDFStatusResponse(
                    audit_id=audit_id,
                    job_id=None,
                    status="completed",
                    download_ready=True,
                    report_id=report.id,
                    warnings=[],
                    error=None,
                    started_at=report.created_at,
                    completed_at=report.created_at,
                    retry_after_seconds=0,
                    message=message,
                )
            return AuditPDFStatusResponse(
                audit_id=audit_id,
                job_id=None,
                status="idle",
                download_ready=False,
                report_id=None,
                warnings=[],
                error=None,
                started_at=None,
                completed_at=None,
                retry_after_seconds=0,
                message=message,
            )

        is_completed = job.status == AuditPdfJobStatus.COMPLETED.value
        effective_report = report if is_completed else None
        error = None
        if job.status == AuditPdfJobStatus.FAILED.value and (
            job.error_code or job.error_message
        ):
            error = PDFStatusError(
                code=job.error_code or None,
                message=job.error_message or None,
            )

        return AuditPDFStatusResponse(
            audit_id=audit_id,
            job_id=job.id,
            status=job.status,
            download_ready=bool(
                is_completed and effective_report and effective_report.file_path
            ),
            report_id=effective_report.id if effective_report else None,
            warnings=PDFJobService.normalize_warnings(job.warnings),
            error=error,
            started_at=job.started_at,
            completed_at=job.completed_at,
            retry_after_seconds=(
                retry_after_seconds if job.status in ACTIVE_PDF_JOB_STATUSES else 0
            ),
            waiting_on=job.waiting_on,
            dependency_job_id=job.dependency_job_id,
            message=message,
        )

    @staticmethod
    def queue_job(
        db: Session,
        *,
        audit_id: int,
        requested_by_user_id: str | None,
        force_pagespeed_refresh: bool,
        force_report_refresh: bool,
        force_external_intel_refresh: bool,
    ) -> AuditPdfJob:
        job = PDFJobService.get_job(db, audit_id)
        if job is None:
            job = AuditPdfJob(audit_id=audit_id)
            db.add(job)

        job.requested_by_user_id = requested_by_user_id
        job.status = AuditPdfJobStatus.QUEUED.value
        job.celery_task_id = None
        job.force_pagespeed_refresh = bool(force_pagespeed_refresh)
        job.force_report_refresh = bool(force_report_refresh)
        job.force_external_intel_refresh = bool(force_external_intel_refresh)
        job.warnings = []
        job.error_code = None
        job.error_message = None
        job.waiting_on = None
        job.dependency_job_id = None
        job.report_id = None
        job.started_at = None
        job.completed_at = None
        job.updated_at = datetime.now(UTC)

        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def mark_job_running(db: Session, job: AuditPdfJob) -> AuditPdfJob:
        now = datetime.now(UTC)
        job.status = AuditPdfJobStatus.RUNNING.value
        job.waiting_on = None
        job.dependency_job_id = None
        job.started_at = now
        job.completed_at = None
        job.updated_at = now
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def mark_job_waiting(
        db: Session,
        job: AuditPdfJob,
        *,
        waiting_on: str,
        dependency_job_id: int | None,
    ) -> AuditPdfJob:
        now = datetime.now(UTC)
        job.status = AuditPdfJobStatus.WAITING.value
        job.waiting_on = waiting_on[:40]
        job.dependency_job_id = dependency_job_id
        job.started_at = None
        job.completed_at = None
        job.updated_at = now
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def mark_job_completed(
        db: Session,
        job: AuditPdfJob,
        *,
        report_id: int,
        warnings: list[str],
    ) -> AuditPdfJob:
        now = datetime.now(UTC)
        job.status = AuditPdfJobStatus.COMPLETED.value
        job.report_id = report_id
        job.warnings = warnings
        job.error_code = None
        job.error_message = None
        job.waiting_on = None
        job.dependency_job_id = None
        job.completed_at = now
        job.updated_at = now
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def mark_job_failed(
        db: Session,
        job: AuditPdfJob,
        *,
        error_code: str,
        error_message: str,
        warnings: Optional[list[str]] = None,
    ) -> AuditPdfJob:
        now = datetime.now(UTC)
        job.status = AuditPdfJobStatus.FAILED.value
        job.error_code = error_code
        job.error_message = error_message[:500]
        job.warnings = warnings or []
        job.waiting_on = None
        job.completed_at = now
        job.updated_at = now
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    async def _notify_pdf_ready_if_configured(
        *,
        audit: Audit,
        report: Report,
        file_size: int | None,
    ) -> None:
        if not settings.DEFAULT_WEBHOOK_URL:
            return
        if not report.file_path or not str(report.file_path).startswith("supabase://"):
            return

        try:
            from app.services.supabase_service import SupabaseService
            from app.services.webhook_service import WebhookService

            storage_path = str(report.file_path).replace("supabase://", "", 1)
            signed_url = SupabaseService.get_signed_url(
                bucket=settings.SUPABASE_STORAGE_BUCKET,
                path=storage_path,
            )
            await WebhookService.notify_pdf_ready(
                audit_id=audit.id,
                audit_url=str(audit.url),
                pdf_download_url=signed_url,
                file_size=int(file_size or 0),
            )
        except Exception as exc:
            logger.warning(
                "pdf_ready_webhook_failed audit_id=%s report_id=%s error=%s",
                audit.id,
                report.id,
                exc,
            )

    @staticmethod
    def publish_status_event(
        db: Session,
        audit: Audit,
        *,
        job: AuditPdfJob | None = None,
        report: Report | None = None,
    ) -> None:
        from app.services.pagespeed_job_service import PageSpeedJobService

        pagespeed_job = PageSpeedJobService.get_job(db, audit.id)
        AuditService.publish_artifact_event(
            audit.id,
            AuditService.build_artifact_payload(
                audit,
                pagespeed_job=pagespeed_job,
                pdf_job=job or PDFJobService.get_job(db, audit.id),
                pdf_report=report or PDFJobService.get_latest_pdf_report(db, audit.id),
            ),
        )

    @staticmethod
    def enqueue_job_task(db: Session, audit: Audit, job: AuditPdfJob) -> AuditPdfJob:
        from app.workers.tasks import run_pdf_generation_job_task

        task = run_pdf_generation_job_task.delay(job.id)
        job.celery_task_id = getattr(task, "id", None)
        job.updated_at = datetime.now(UTC)
        db.add(job)
        db.commit()
        db.refresh(job)
        PDFJobService.publish_status_event(db, audit, job=job)
        return job

    @staticmethod
    def resume_waiting_job_after_pagespeed(
        db: Session,
        *,
        audit: Audit,
        pagespeed_job: AuditPageSpeedJob | None,
    ) -> AuditPdfJob | None:
        job = PDFJobService.get_job(db, audit.id)
        if job is None:
            return None
        if job.status != AuditPdfJobStatus.WAITING.value:
            return job
        if job.waiting_on != "pagespeed":
            return job
        if (
            job.dependency_job_id is not None
            and pagespeed_job is not None
            and pagespeed_job.id is not None
            and job.dependency_job_id != pagespeed_job.id
        ):
            return job
        if job.dependency_job_id is not None and pagespeed_job is None:
            return job

        job.status = AuditPdfJobStatus.QUEUED.value
        job.waiting_on = None
        job.dependency_job_id = None
        job.error_code = None
        job.error_message = None
        job.updated_at = datetime.now(UTC)
        db.add(job)
        db.commit()
        db.refresh(job)

        try:
            job = PDFJobService.enqueue_job_task(db, audit, job)
        except Exception as exc:
            error_code, error_message = PDFJobService.classify_error(exc)
            job = PDFJobService.mark_job_failed(
                db,
                job,
                error_code="worker_unavailable",
                error_message=error_message or error_code,
            )
            PDFJobService.persist_runtime_diagnostic_safely(
                db,
                audit.id,
                source="pdf",
                stage="generate-pdf",
                severity="error",
                code="worker_unavailable",
                message="PDF generation could not be resumed after PageSpeed completed.",
                technical_detail=PDFJobService.runtime_technical_detail(exc),
            )
            PDFJobService.publish_status_event(db, audit, job=job)
        return job

    @staticmethod
    async def execute_job(db: Session, job_id: int) -> AuditPdfJob:
        from app.services.pagespeed_job_service import PageSpeedJobService
        from app.services.pdf_service import PDFService

        job = db.query(AuditPdfJob).filter(AuditPdfJob.id == job_id).first()
        if job is None:
            raise ValueError(f"PDF job {job_id} not found")
        audit_id_for_lock = int(job.audit_id)

        audit = db.query(Audit).filter(Audit.id == job.audit_id).first()
        if audit is None:
            raise ValueError(f"Audit {job.audit_id} not found for PDF job {job_id}")

        acquired_lock, lock_token, lock_mode = acquire_pdf_generation_lock(
            audit_id_for_lock
        )
        if not acquired_lock:
            if lock_mode == "unavailable":
                error_code = "lock_unavailable"
                error_message = (
                    "Distributed PDF lock backend is unavailable. Redis is required."
                )
                PDFJobService.mark_job_failed(
                    db,
                    job,
                    error_code=error_code,
                    error_message=error_message,
                )
                PDFJobService.persist_runtime_diagnostic_safely(
                    db,
                    audit.id,
                    source="pdf",
                    stage="generate-pdf",
                    severity="error",
                    code=error_code,
                    message=error_message,
                )
                return job

            logger.info(
                "PDF job %s skipped because another worker already holds the lock for audit %s",
                job_id,
                audit.id,
            )
            return job

        try:
            pagespeed_job = PageSpeedJobService.get_job(db, audit.id)
            if pagespeed_job is not None and PageSpeedJobService.has_active_job(
                pagespeed_job
            ):
                job = PDFJobService.mark_job_waiting(
                    db,
                    job,
                    waiting_on="pagespeed",
                    dependency_job_id=pagespeed_job.id,
                )
                PDFJobService.publish_status_event(db, audit, job=job)
                logger.info(
                    "PDF job %s returned to waiting because PageSpeed job %s is still active for audit %s",
                    job_id,
                    pagespeed_job.id,
                    audit.id,
                )
                refreshed_pagespeed_job = PageSpeedJobService.get_job(db, audit.id)
                if (
                    refreshed_pagespeed_job is None
                    or not PageSpeedJobService.has_active_job(refreshed_pagespeed_job)
                ):
                    release_pdf_generation_lock(
                        audit_id_for_lock, lock_token, lock_mode
                    )
                    lock_token = None
                    lock_mode = None
                    return (
                        PDFJobService.resume_waiting_job_after_pagespeed(
                            db,
                            audit=audit,
                            pagespeed_job=refreshed_pagespeed_job,
                        )
                        or job
                    )
                return job

            job = PDFJobService.mark_job_running(db, job)
            PDFJobService.publish_status_event(db, audit, job=job)
            generation_result = await PDFService.generate_pdf_with_complete_context(
                db=db,
                audit_id=audit.id,
                force_pagespeed_refresh=bool(job.force_pagespeed_refresh),
                force_report_refresh=bool(job.force_report_refresh),
                force_external_intel_refresh=bool(job.force_external_intel_refresh),
                allow_pagespeed_refresh=False,
                return_details=True,
            )

            pdf_path = generation_result.get("pdf_path")
            if not pdf_path:
                raise RuntimeError("PDF generation failed - missing path")
            if not str(pdf_path).startswith("supabase://"):
                raise RuntimeError(
                    "PDF generation failed - expected Supabase storage path."
                )

            file_size_raw = generation_result.get("file_size")
            try:
                file_size = int(file_size_raw) if file_size_raw is not None else None
            except (TypeError, ValueError):
                file_size = None

            report = PDFJobService.get_latest_pdf_report(db, audit.id)
            if report:
                report.file_path = str(pdf_path)
                report.file_size = file_size
                report.created_at = datetime.now(UTC)
            else:
                report = Report(
                    audit_id=audit.id,
                    report_type="PDF",
                    file_path=str(pdf_path),
                    file_size=file_size,
                )
                db.add(report)

            db.commit()
            db.refresh(report)

            warnings = PDFJobService.persist_generation_warnings(
                db,
                audit.id,
                generation_result.get("generation_warnings", []),
            )
            job = PDFJobService.mark_job_completed(
                db,
                job,
                report_id=report.id,
                warnings=warnings,
            )
            PDFJobService.publish_status_event(db, audit, job=job, report=report)
            await PDFJobService._notify_pdf_ready_if_configured(
                audit=audit,
                report=report,
                file_size=file_size,
            )
            return job
        except Exception as exc:
            logger.error("PDF job failed for audit %s", audit.id, exc_info=True)
            db.rollback()
            job = db.query(AuditPdfJob).filter(AuditPdfJob.id == job_id).first() or job
            error_code, error_message = PDFJobService.classify_error(exc)
            job = PDFJobService.mark_job_failed(
                db,
                job,
                error_code=error_code,
                error_message=error_message,
            )
            PDFJobService.persist_runtime_diagnostic_safely(
                db,
                audit.id,
                source="pdf",
                stage="generate-pdf",
                severity="error",
                code=error_code,
                message="PDF generation failed before the report could be delivered.",
                technical_detail=PDFJobService.runtime_technical_detail(exc),
            )
            PDFJobService.publish_status_event(db, audit, job=job)
            return job
        finally:
            release_pdf_generation_lock(audit_id_for_lock, lock_token, lock_mode)
