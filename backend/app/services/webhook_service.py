"""
Webhook Service for sending notifications to external systems.
Production-ready implementation with retry logic, signature verification, and logging.
"""

import asyncio
import hashlib
import hmac
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

import httpx
from app.core.config import settings
from app.core.logger import get_logger
from sqlalchemy.orm import Session

logger = get_logger(__name__)


class WebhookEventType(str, Enum):
    """Types of webhook events that can be sent."""

    AUDIT_CREATED = "audit.created"
    AUDIT_STARTED = "audit.started"
    AUDIT_COMPLETED = "audit.completed"
    AUDIT_FAILED = "audit.failed"
    AUDIT_PROGRESS = "audit.progress"

    REPORT_GENERATED = "report.generated"
    PDF_READY = "pdf.ready"

    PAGESPEED_COMPLETED = "pagespeed.completed"
    GEO_ANALYSIS_COMPLETED = "geo_analysis.completed"

    GITHUB_PR_CREATED = "github.pr_created"
    GITHUB_SYNC_COMPLETED = "github.sync_completed"

    COMPETITOR_ANALYSIS_COMPLETED = "competitor.analysis_completed"


class WebhookDeliveryStatus(str, Enum):
    """Status of webhook delivery."""

    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"


class WebhookService:
    """
    Service for managing and sending webhooks.
    Supports retry logic, signature verification, and delivery tracking.
    """

    MAX_RETRIES = 3
    RETRY_DELAYS = [5, 30, 300]  # 5s, 30s, 5min
    TIMEOUT = 30  # seconds

    @staticmethod
    def generate_signature(payload: str, secret: str) -> str:
        """
        Generate HMAC-SHA256 signature for webhook payload.

        Args:
            payload: JSON string payload
            secret: Webhook secret key

        Returns:
            Hex-encoded signature
        """
        return hmac.new(
            secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
        ).hexdigest()

    @staticmethod
    def verify_signature(payload: str, signature: str, secret: str) -> bool:
        """
        Verify incoming webhook signature.

        Args:
            payload: JSON string payload
            signature: Received signature
            secret: Webhook secret key

        Returns:
            True if signature is valid
        """
        expected = WebhookService.generate_signature(payload, secret)
        return hmac.compare_digest(expected, signature)

    @staticmethod
    async def send_webhook(
        url: str,
        event_type: WebhookEventType,
        payload: Dict[str, Any],
        secret: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Send a webhook notification to the specified URL.

        Args:
            url: Webhook endpoint URL
            event_type: Type of event
            payload: Event data
            secret: Optional secret for signing
            headers: Additional headers

        Returns:
            Delivery result with status and response
        """
        if not url:
            logger.warning("No webhook URL provided, skipping notification")
            return {"status": "skipped", "reason": "no_url"}

        # Build webhook payload
        now = datetime.now(timezone.utc)
        webhook_payload = {
            "event": event_type.value,
            "timestamp": now.isoformat() + "Z",
            "data": payload,
            "webhook_id": hashlib.sha256(
                f"{event_type.value}:{now.timestamp()}".encode()
            ).hexdigest()[:16],
        }

        payload_json = json.dumps(webhook_payload, default=str)

        # Build headers
        request_headers = {
            "Content-Type": "application/json",
            "User-Agent": f"AuditorGEO-Webhook/1.0 ({settings.APP_NAME})",
            "X-Webhook-Event": event_type.value,
            "X-Webhook-Timestamp": webhook_payload["timestamp"],
            "X-Webhook-Id": webhook_payload["webhook_id"],
        }

        # Add signature if secret provided
        if secret:
            signature = WebhookService.generate_signature(payload_json, secret)
            request_headers["X-Webhook-Signature"] = f"sha256={signature}"

        # Merge custom headers
        if headers:
            request_headers.update(headers)

        # Send with retries
        last_error = None
        for attempt in range(WebhookService.MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=WebhookService.TIMEOUT) as client:
                    response = await client.post(
                        url, content=payload_json, headers=request_headers
                    )

                    if response.status_code in [200, 201, 202, 204]:
                        logger.info(
                            f"Webhook delivered successfully: {event_type.value} to {url}"
                        )
                        return {
                            "status": WebhookDeliveryStatus.DELIVERED.value,
                            "status_code": response.status_code,
                            "response": response.text[:500] if response.text else None,
                            "attempts": attempt + 1,
                        }
                    else:
                        logger.warning(
                            f"Webhook delivery failed with status {response.status_code}: "
                            f"{event_type.value} to {url}"
                        )
                        last_error = f"HTTP {response.status_code}"

            except httpx.TimeoutException:
                logger.warning(f"Webhook timeout (attempt {attempt + 1}): {url}")
                last_error = "timeout"
            except httpx.RequestError as e:
                logger.warning(f"Webhook request error (attempt {attempt + 1}): {e}")
                last_error = str(e)
            except Exception as e:
                logger.error(f"Webhook unexpected error (attempt {attempt + 1}): {e}")
                last_error = str(e)

            # Wait before retry
            if attempt < WebhookService.MAX_RETRIES - 1:
                delay = WebhookService.RETRY_DELAYS[attempt]
                logger.info(f"Retrying webhook in {delay}s...")
                await asyncio.sleep(delay)

        logger.error(
            f"Webhook delivery failed after {WebhookService.MAX_RETRIES} attempts: "
            f"{event_type.value} to {url}"
        )
        return {
            "status": WebhookDeliveryStatus.FAILED.value,
            "error": last_error,
            "attempts": WebhookService.MAX_RETRIES,
        }

    @staticmethod
    async def notify_audit_created(
        db: Session,
        audit_id: int,
        audit_url: str,
        webhook_url: Optional[str] = None,
        webhook_secret: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send notification when audit is created."""
        payload = {"audit_id": audit_id, "url": audit_url, "status": "pending"}

        return await WebhookService.send_webhook(
            url=webhook_url or getattr(settings, "DEFAULT_WEBHOOK_URL", ""),
            event_type=WebhookEventType.AUDIT_CREATED,
            payload=payload,
            secret=webhook_secret or getattr(settings, "WEBHOOK_SECRET", ""),
        )

    @staticmethod
    async def notify_audit_completed(
        db: Session,
        audit_id: int,
        audit_url: str,
        geo_score: float,
        critical_issues: int,
        webhook_url: Optional[str] = None,
        webhook_secret: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send notification when audit is completed."""
        payload = {
            "audit_id": audit_id,
            "url": audit_url,
            "status": "completed",
            "geo_score": geo_score,
            "critical_issues": critical_issues,
            "dashboard_url": f"{getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')}/dashboard/{audit_id}",
        }

        return await WebhookService.send_webhook(
            url=webhook_url or getattr(settings, "DEFAULT_WEBHOOK_URL", ""),
            event_type=WebhookEventType.AUDIT_COMPLETED,
            payload=payload,
            secret=webhook_secret or getattr(settings, "WEBHOOK_SECRET", ""),
        )

    @staticmethod
    async def notify_audit_failed(
        db: Session,
        audit_id: int,
        audit_url: str,
        error_message: str,
        webhook_url: Optional[str] = None,
        webhook_secret: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send notification when audit fails."""
        payload = {
            "audit_id": audit_id,
            "url": audit_url,
            "status": "failed",
            "error": error_message,
        }

        return await WebhookService.send_webhook(
            url=webhook_url or getattr(settings, "DEFAULT_WEBHOOK_URL", ""),
            event_type=WebhookEventType.AUDIT_FAILED,
            payload=payload,
            secret=webhook_secret or getattr(settings, "WEBHOOK_SECRET", ""),
        )

    @staticmethod
    async def notify_audit_progress(
        audit_id: int,
        audit_url: str,
        progress: int,
        current_step: str,
        webhook_url: Optional[str] = None,
        webhook_secret: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send progress update notification."""
        # Only send progress updates at key milestones to avoid flooding
        if progress not in [10, 25, 50, 75, 90, 100]:
            return {"status": "skipped", "reason": "not_milestone"}

        payload = {
            "audit_id": audit_id,
            "url": audit_url,
            "progress": progress,
            "current_step": current_step,
        }

        return await WebhookService.send_webhook(
            url=webhook_url or getattr(settings, "DEFAULT_WEBHOOK_URL", ""),
            event_type=WebhookEventType.AUDIT_PROGRESS,
            payload=payload,
            secret=webhook_secret or getattr(settings, "WEBHOOK_SECRET", ""),
        )

    @staticmethod
    async def notify_pdf_ready(
        audit_id: int,
        audit_url: str,
        pdf_download_url: str,
        file_size: int,
        webhook_url: Optional[str] = None,
        webhook_secret: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send notification when PDF is ready for download."""
        payload = {
            "audit_id": audit_id,
            "url": audit_url,
            "pdf_url": pdf_download_url,
            "file_size": file_size,
        }

        return await WebhookService.send_webhook(
            url=webhook_url or getattr(settings, "DEFAULT_WEBHOOK_URL", ""),
            event_type=WebhookEventType.PDF_READY,
            payload=payload,
            secret=webhook_secret or getattr(settings, "WEBHOOK_SECRET", ""),
        )

    @staticmethod
    async def notify_competitor_analysis_completed(
        audit_id: int,
        audit_url: str,
        competitor_count: int,
        avg_geo_score: float,
        webhook_url: Optional[str] = None,
        webhook_secret: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send notification when competitor analysis is completed."""
        payload = {
            "audit_id": audit_id,
            "url": audit_url,
            "competitor_count": competitor_count,
            "avg_geo_score": avg_geo_score,
        }

        return await WebhookService.send_webhook(
            url=webhook_url or getattr(settings, "DEFAULT_WEBHOOK_URL", ""),
            event_type=WebhookEventType.COMPETITOR_ANALYSIS_COMPLETED,
            payload=payload,
            secret=webhook_secret or getattr(settings, "WEBHOOK_SECRET", ""),
        )


# Celery task for async webhook delivery
def send_webhook_task(
    url: str, event_type: str, payload: Dict[str, Any], secret: Optional[str] = None
):
    """
    Celery task wrapper for sending webhooks asynchronously.
    Use this for fire-and-forget webhook notifications.
    """
    try:
        from app.workers.celery_app import celery_app

        @celery_app.task(name="send_webhook_async", bind=True, max_retries=3)
        def _send_webhook_async(self, url, event_type, payload, secret):
            import asyncio

            try:
                event = WebhookEventType(event_type)
                result = asyncio.run(
                    WebhookService.send_webhook(url, event, payload, secret)
                )
                return result
            except Exception as e:
                logger.error(f"Webhook task failed: {e}")
                raise self.retry(exc=e, countdown=60)

        return _send_webhook_async.delay(url, event_type, payload, secret)
    except ImportError:
        logger.warning("Celery not available, sending webhook synchronously")
        import asyncio

        event = WebhookEventType(event_type)
        return asyncio.run(WebhookService.send_webhook(url, event, payload, secret))
