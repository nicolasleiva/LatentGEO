import os
import pytest

from app.core.config import settings
from app.services.pagespeed_service import PageSpeedService


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pagespeed_api():
    if os.getenv("RUN_INTEGRATION") != "1":
        pytest.skip("Set RUN_INTEGRATION=1 to run external PageSpeed API test.")

    if not settings.ENABLE_PAGESPEED or not settings.GOOGLE_PAGESPEED_API_KEY:
        pytest.skip("PageSpeed disabled or API key missing.")

    url = os.getenv("PAGESPEED_TEST_URL")
    if not url:
        pytest.fail("PAGESPEED_TEST_URL is required for real PageSpeed tests.")

    api_key = settings.GOOGLE_PAGESPEED_API_KEY

    mobile = await PageSpeedService.analyze_url(url, api_key, "mobile")
    assert "performance_score" in mobile

    desktop = await PageSpeedService.analyze_url(url, api_key, "desktop")
    assert "performance_score" in desktop
