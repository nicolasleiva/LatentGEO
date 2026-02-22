import pytest
from app.core.config import settings
from app.services.audit_local_service import AuditLocalService
from app.services.crawler_service import CrawlerService


class AlwaysFailSession:
    headers = {}

    def get(self, *args, **kwargs):
        raise RuntimeError("network failure")


@pytest.mark.asyncio
async def test_audit_local_does_not_use_insecure_ssl_when_disabled(monkeypatch):
    called = {"connector": False}

    def _forbidden_connector(*args, **kwargs):
        called["connector"] = True
        raise AssertionError("TCPConnector(ssl=False) should not be called")

    monkeypatch.setattr(settings, "ALLOW_INSECURE_SSL_FALLBACK", False, raising=False)
    monkeypatch.setattr(
        "app.services.audit_local_service.aiohttp.TCPConnector",
        _forbidden_connector,
    )

    status, text, content_type = await AuditLocalService.fetch_text(
        AlwaysFailSession(), "https://example.com"
    )
    assert (status, text, content_type) == (None, None, "")
    assert called["connector"] is False


@pytest.mark.asyncio
async def test_audit_local_attempts_insecure_ssl_when_enabled(monkeypatch):
    called = {"connector": False}

    def _failing_connector(*args, **kwargs):
        called["connector"] = True
        raise RuntimeError("connector creation failed")

    monkeypatch.setattr(settings, "ALLOW_INSECURE_SSL_FALLBACK", True, raising=False)
    monkeypatch.setattr(
        "app.services.audit_local_service.aiohttp.TCPConnector",
        _failing_connector,
    )

    status, text, content_type = await AuditLocalService.fetch_text(
        AlwaysFailSession(), "https://example.com"
    )
    assert (status, text, content_type) == (None, None, "")
    assert called["connector"] is True


@pytest.mark.asyncio
async def test_crawler_fetch_text_url_respects_insecure_ssl_flag_off(monkeypatch):
    called = {"connector": False}

    def _forbidden_connector(*args, **kwargs):
        called["connector"] = True
        raise AssertionError("TCPConnector(ssl=False) should not be called")

    monkeypatch.setattr(settings, "ALLOW_INSECURE_SSL_FALLBACK", False, raising=False)
    monkeypatch.setattr(
        "app.services.crawler_service.aiohttp.TCPConnector",
        _forbidden_connector,
    )

    value = await CrawlerService._fetch_text_url(
        AlwaysFailSession(),
        "https://example.com",
        timeout=1,
        allow_insecure_fallback=None,
    )
    assert value is None
    assert called["connector"] is False


@pytest.mark.asyncio
async def test_crawler_fetch_text_url_attempts_insecure_ssl_when_enabled(monkeypatch):
    called = {"connector": False}

    def _failing_connector(*args, **kwargs):
        called["connector"] = True
        raise RuntimeError("connector creation failed")

    monkeypatch.setattr(settings, "ALLOW_INSECURE_SSL_FALLBACK", True, raising=False)
    monkeypatch.setattr(
        "app.services.crawler_service.aiohttp.TCPConnector",
        _failing_connector,
    )

    value = await CrawlerService._fetch_text_url(
        AlwaysFailSession(),
        "https://example.com",
        timeout=1,
        allow_insecure_fallback=None,
    )
    assert value is None
    assert called["connector"] is True
