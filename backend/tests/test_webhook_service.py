"""
Tests for Webhook Service - Production Ready
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.services.webhook_service import (
    WebhookDeliveryStatus,
    WebhookEventType,
    WebhookService,
)


class TestWebhookSignature:
    """Tests for webhook signature generation and verification"""

    def test_generate_signature(self):
        """Test HMAC signature generation"""
        payload = '{"test": "data"}'
        secret = "test-secret-key-12345"

        signature = WebhookService.generate_signature(payload, secret)

        # Signature should be hex string
        assert len(signature) == 64  # SHA256 hex is 64 chars
        assert all(c in "0123456789abcdef" for c in signature)

    def test_signature_deterministic(self):
        """Test that same inputs produce same signature"""
        payload = '{"event": "test"}'
        secret = "my-secret"

        sig1 = WebhookService.generate_signature(payload, secret)
        sig2 = WebhookService.generate_signature(payload, secret)

        assert sig1 == sig2

    def test_signature_changes_with_payload(self):
        """Test that different payloads produce different signatures"""
        secret = "my-secret"

        sig1 = WebhookService.generate_signature('{"a": 1}', secret)
        sig2 = WebhookService.generate_signature('{"a": 2}', secret)

        assert sig1 != sig2

    def test_signature_changes_with_secret(self):
        """Test that different secrets produce different signatures"""
        payload = '{"test": "data"}'

        sig1 = WebhookService.generate_signature(payload, "secret1")
        sig2 = WebhookService.generate_signature(payload, "secret2")

        assert sig1 != sig2

    def test_verify_signature_valid(self):
        """Test signature verification with valid signature"""
        payload = '{"event": "test.completed"}'
        secret = "webhook-secret"

        signature = WebhookService.generate_signature(payload, secret)

        assert WebhookService.verify_signature(payload, signature, secret) is True

    def test_verify_signature_invalid(self):
        """Test signature verification with invalid signature"""
        payload = '{"event": "test"}'
        secret = "webhook-secret"

        invalid_signature = "invalid" * 8

        assert (
            WebhookService.verify_signature(payload, invalid_signature, secret) is False
        )

    def test_verify_signature_wrong_secret(self):
        """Test signature verification with wrong secret"""
        payload = '{"event": "test"}'

        signature = WebhookService.generate_signature(payload, "secret1")

        assert WebhookService.verify_signature(payload, signature, "secret2") is False


class TestWebhookEventTypes:
    """Tests for webhook event types"""

    def test_all_event_types_defined(self):
        """Test that all expected event types are defined"""
        expected_events = [
            "audit.created",
            "audit.started",
            "audit.completed",
            "audit.failed",
            "audit.progress",
            "report.generated",
            "pdf.ready",
            "pagespeed.completed",
            "geo_analysis.completed",
            "github.pr_created",
            "github.sync_completed",
            "competitor.analysis_completed",
        ]

        for event in expected_events:
            assert WebhookEventType(event) is not None

    def test_event_type_string_value(self):
        """Test that event types have correct string values"""
        assert WebhookEventType.AUDIT_COMPLETED.value == "audit.completed"
        assert WebhookEventType.PDF_READY.value == "pdf.ready"
        assert WebhookEventType.GITHUB_PR_CREATED.value == "github.pr_created"


class TestWebhookDelivery:
    """Tests for webhook delivery functionality"""

    @pytest.mark.asyncio
    async def test_send_webhook_no_url_skips(self):
        """Test that sending with no URL skips delivery"""
        result = await WebhookService.send_webhook(
            url="",
            event_type=WebhookEventType.AUDIT_COMPLETED,
            payload={"test": "data"},
        )

        assert result["status"] == "skipped"
        assert result["reason"] == "no_url"

    @pytest.mark.asyncio
    async def test_send_webhook_success(self):
        """Test successful webhook delivery"""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = '{"received": true}'

            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(return_value=mock_response)
            mock_client_instance.__aenter__ = AsyncMock(
                return_value=mock_client_instance
            )
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_client_instance

            result = await WebhookService.send_webhook(
                url="https://example.com/webhook",
                event_type=WebhookEventType.AUDIT_COMPLETED,
                payload={"audit_id": 1, "status": "completed"},
            )

            assert result["status"] == WebhookDeliveryStatus.DELIVERED.value
            assert result["status_code"] == 200
            assert result["attempts"] == 1

    @pytest.mark.asyncio
    async def test_send_webhook_with_signature(self):
        """Test webhook delivery includes signature when secret provided"""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = ""

            captured_headers = {}

            async def capture_post(url, content, headers):
                captured_headers.update(headers)
                return mock_response

            mock_client_instance = AsyncMock()
            mock_client_instance.post = capture_post
            mock_client_instance.__aenter__ = AsyncMock(
                return_value=mock_client_instance
            )
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_client_instance

            await WebhookService.send_webhook(
                url="https://example.com/webhook",
                event_type=WebhookEventType.AUDIT_COMPLETED,
                payload={"audit_id": 1},
                secret="my-webhook-secret",
            )

            assert "X-Webhook-Signature" in captured_headers
            assert captured_headers["X-Webhook-Signature"].startswith("sha256=")

    @pytest.mark.asyncio
    async def test_send_webhook_includes_required_headers(self):
        """Test that webhook request includes all required headers"""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = ""

            captured_headers = {}

            async def capture_post(url, content, headers):
                captured_headers.update(headers)
                return mock_response

            mock_client_instance = AsyncMock()
            mock_client_instance.post = capture_post
            mock_client_instance.__aenter__ = AsyncMock(
                return_value=mock_client_instance
            )
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_client_instance

            await WebhookService.send_webhook(
                url="https://example.com/webhook",
                event_type=WebhookEventType.AUDIT_COMPLETED,
                payload={"audit_id": 1},
            )

            assert captured_headers["Content-Type"] == "application/json"
            assert "X-Webhook-Event" in captured_headers
            assert "X-Webhook-Timestamp" in captured_headers
            assert "X-Webhook-Id" in captured_headers
            assert "AuditorGEO" in captured_headers["User-Agent"]


class TestWebhookNotificationHelpers:
    """Tests for webhook notification helper methods"""

    @pytest.mark.asyncio
    async def test_notify_audit_completed(self):
        """Test audit completed notification"""
        with patch.object(
            WebhookService, "send_webhook", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = {"status": "delivered"}

            mock_db = MagicMock()

            with patch("app.services.webhook_service.settings") as mock_settings:
                mock_settings.DEFAULT_WEBHOOK_URL = "https://example.com/webhook"
                mock_settings.WEBHOOK_SECRET = "secret"
                mock_settings.FRONTEND_URL = "https://app.example.com"

                await WebhookService.notify_audit_completed(
                    db=mock_db,
                    audit_id=123,
                    audit_url="https://site.com",
                    geo_score=7.5,
                    critical_issues=2,
                )

            assert mock_send.called
            call_args = mock_send.call_args

            # Check event type
            assert call_args.kwargs["event_type"] == WebhookEventType.AUDIT_COMPLETED

            # Check payload contains expected data
            payload = call_args.kwargs["payload"]
            assert payload["audit_id"] == 123
            assert payload["status"] == "completed"
            assert payload["geo_score"] == 7.5

    @pytest.mark.asyncio
    async def test_notify_audit_failed(self):
        """Test audit failed notification"""
        with patch.object(
            WebhookService, "send_webhook", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = {"status": "delivered"}

            mock_db = MagicMock()

            with patch("app.services.webhook_service.settings") as mock_settings:
                mock_settings.DEFAULT_WEBHOOK_URL = "https://example.com/webhook"
                mock_settings.WEBHOOK_SECRET = "secret"

                await WebhookService.notify_audit_failed(
                    db=mock_db,
                    audit_id=123,
                    audit_url="https://site.com",
                    error_message="Pipeline failed",
                )

            call_args = mock_send.call_args
            assert call_args.kwargs["event_type"] == WebhookEventType.AUDIT_FAILED
            assert call_args.kwargs["payload"]["error"] == "Pipeline failed"

    @pytest.mark.asyncio
    async def test_notify_progress_only_milestones(self):
        """Test that progress notifications only fire at milestones"""
        with patch.object(
            WebhookService, "send_webhook", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = {"status": "delivered"}

            # Non-milestone progress should be skipped
            result = await WebhookService.notify_audit_progress(
                audit_id=123,
                audit_url="https://site.com",
                progress=33,
                current_step="processing",
            )

            assert result["status"] == "skipped"
            assert not mock_send.called

            # Milestone progress should send
            result = await WebhookService.notify_audit_progress(
                audit_id=123,
                audit_url="https://site.com",
                progress=50,
                current_step="halfway",
            )

            assert mock_send.called

    @pytest.mark.asyncio
    async def test_notify_pdf_ready(self):
        """Test PDF ready notification"""
        with patch.object(
            WebhookService, "send_webhook", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = {"status": "delivered"}

            with patch("app.services.webhook_service.settings") as mock_settings:
                mock_settings.DEFAULT_WEBHOOK_URL = "https://example.com/webhook"
                mock_settings.WEBHOOK_SECRET = "secret"

                await WebhookService.notify_pdf_ready(
                    audit_id=123,
                    audit_url="https://site.com",
                    pdf_download_url="https://api.example.com/audits/123/download-pdf",
                    file_size=1024000,
                )

            call_args = mock_send.call_args
            assert call_args.kwargs["event_type"] == WebhookEventType.PDF_READY

            payload = call_args.kwargs["payload"]
            assert payload["file_size"] == 1024000
            assert "pdf_url" in payload


class TestWebhookPayloadFormat:
    """Tests for webhook payload format"""

    @pytest.mark.asyncio
    async def test_payload_structure(self):
        """Test that webhook payload has correct structure"""
        captured_payload = None

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = ""

            async def capture_post(url, content, headers):
                nonlocal captured_payload
                captured_payload = json.loads(content)
                return mock_response

            mock_client_instance = AsyncMock()
            mock_client_instance.post = capture_post
            mock_client_instance.__aenter__ = AsyncMock(
                return_value=mock_client_instance
            )
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_client_instance

            await WebhookService.send_webhook(
                url="https://example.com/webhook",
                event_type=WebhookEventType.AUDIT_COMPLETED,
                payload={"audit_id": 1, "custom": "data"},
            )

        assert captured_payload is not None
        assert "event" in captured_payload
        assert "timestamp" in captured_payload
        assert "data" in captured_payload
        assert "webhook_id" in captured_payload

        assert captured_payload["event"] == "audit.completed"
        assert captured_payload["data"]["audit_id"] == 1
        assert captured_payload["data"]["custom"] == "data"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
