import asyncio
import os

import pytest
from app.core.config import settings
from app.core.llm_kimi import KimiSearchUnavailableError, kimi_search_serp

STRICT_TEST_MODE = os.getenv("STRICT_TEST_MODE") == "1"


def test_kimi_search_requires_feature_flag(monkeypatch):
    monkeypatch.setattr(settings, "NV_KIMI_SEARCH_ENABLED", False)
    with pytest.raises(KimiSearchUnavailableError):
        asyncio.run(kimi_search_serp("zapatilla nike", "AR", top_k=5, language="es"))


@pytest.mark.integration
@pytest.mark.live
def test_kimi_search_live_contract_optional(monkeypatch):
    if os.getenv("RUN_REAL_KIMI_SEARCH_TEST") != "1":
        if STRICT_TEST_MODE:
            pytest.fail("RUN_REAL_KIMI_SEARCH_TEST=1 is required in STRICT_TEST_MODE.")
        pytest.skip(
            "Set RUN_REAL_KIMI_SEARCH_TEST=1 to run live Kimi Search contract test."
        )

    if not any(
        [settings.NV_API_KEY, settings.NVIDIA_API_KEY, settings.NV_API_KEY_ANALYSIS]
    ):
        if STRICT_TEST_MODE:
            pytest.fail("No NVIDIA API key configured for live Kimi Search test.")
        pytest.skip("No NVIDIA API key configured for live Kimi Search test.")

    monkeypatch.setattr(settings, "NV_KIMI_SEARCH_ENABLED", True)
    result = asyncio.run(
        kimi_search_serp("nike running shoes", "US", top_k=5, language="en")
    )

    expected_provider = (
        "google-cse"
        if settings.NV_KIMI_SEARCH_PROVIDER == "google"
        else "kimi-2.5-search"
    )
    assert result["provider"] == expected_provider
    assert result["results"]
    assert isinstance(result["results"][0]["url"], str)
    assert result["results"][0]["url"]
