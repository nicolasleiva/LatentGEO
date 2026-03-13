from unittest.mock import AsyncMock, patch

from app.core.config import settings


def test_pagespeed_analyze_masks_provider_exceptions(client):
    with patch(
        "app.api.routes.pagespeed.PageSpeedService.analyze_url",
        new=AsyncMock(side_effect=RuntimeError("provider exploded")),
    ):
        response = client.get(
            "/api/v1/pagespeed/analyze",
            params={"url": "https://example.com", "strategy": "mobile"},
        )

    assert response.status_code == 502
    assert response.json() == {
        "detail": "PageSpeed analysis failed due to an upstream provider error."
    }


def test_pagespeed_analyze_returns_503_when_provider_not_configured(client):
    with patch(
        "app.api.routes.pagespeed.PageSpeedService.analyze_url",
        new=AsyncMock(side_effect=ValueError("missing API key")),
    ):
        response = client.get(
            "/api/v1/pagespeed/analyze",
            params={"url": "https://example.com", "strategy": "mobile"},
        )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "PageSpeed is unavailable because the provider is not configured."
    }


def test_pagespeed_compare_returns_504_on_timeout(client, monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_PAGESPEED_API_KEY", "test-key", raising=False)

    with patch(
        "app.api.routes.pagespeed.PageSpeedService.analyze_url",
        new=AsyncMock(side_effect=TimeoutError("timed out")),
    ):
        response = client.get(
            "/api/v1/pagespeed/compare",
            params={"url": "https://example.com"},
        )

    assert response.status_code == 504
    assert response.json() == {
        "detail": "PageSpeed provider timed out before returning a result."
    }


def test_pagespeed_analyze_maps_error_payload_to_upstream_status(client):
    with patch(
        "app.api.routes.pagespeed.PageSpeedService.analyze_url",
        new=AsyncMock(
            return_value={
                "error": "API error: 503",
                "status_code": 503,
                "public_message": "Lighthouse unavailable upstream",
            }
        ),
    ):
        response = client.get(
            "/api/v1/pagespeed/analyze",
            params={"url": "https://example.com", "strategy": "mobile"},
        )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "PageSpeed provider returned an error while processing the request."
    }


def test_pagespeed_compare_maps_timeout_payload_to_504(client, monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_PAGESPEED_API_KEY", "test-key", raising=False)

    with patch(
        "app.api.routes.pagespeed.PageSpeedService.analyze_url",
        new=AsyncMock(
            side_effect=[
                {
                    "error": "timeout",
                    "public_message": "PageSpeed request timed out before a response was received.",
                }
            ]
        ),
    ):
        response = client.get(
            "/api/v1/pagespeed/compare",
            params={"url": "https://example.com"},
        )

    assert response.status_code == 504
    assert response.json() == {
        "detail": "PageSpeed provider timed out before returning a result."
    }


def test_pagespeed_analyze_masks_unknown_error_payloads(client):
    with patch(
        "app.api.routes.pagespeed.PageSpeedService.analyze_url",
        new=AsyncMock(
            return_value={
                "error": "internal provider stack trace",
                "public_message": "token=secret upstream crash",
            }
        ),
    ):
        response = client.get(
            "/api/v1/pagespeed/analyze",
            params={"url": "https://example.com", "strategy": "mobile"},
        )

    assert response.status_code == 502
    assert response.json() == {
        "detail": "PageSpeed analysis failed due to an upstream provider error."
    }


def test_pagespeed_analyze_strips_sensitive_keys_from_success_payload(client):
    with patch(
        "app.api.routes.pagespeed.PageSpeedService.analyze_url",
        new=AsyncMock(
            return_value={
                "url": "https://example.com",
                "strategy": "mobile",
                "performance_score": 91,
                "metadata": {
                    "fetch_time": "2026-03-13T00:00:00Z",
                    "traceback": "Traceback (most recent call last): secret",
                },
                "screenshots": [
                    {"data": "data:image/png;base64,abc", "timestamp": 1200}
                ],
                "public_message": "internal details",
                "traceback": "Traceback (most recent call last): secret",
            }
        ),
    ):
        response = client.get(
            "/api/v1/pagespeed/analyze",
            params={"url": "https://example.com", "strategy": "mobile"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["performance_score"] == 91
    assert "public_message" not in payload
    assert "provider_message" not in payload
    assert "traceback" not in payload
    assert "traceback" not in payload["metadata"]
