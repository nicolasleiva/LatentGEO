from datetime import datetime
from types import SimpleNamespace

import pytest

from app.services.competitor_citation_service import CompetitorCitationService


@pytest.mark.asyncio
async def test_gap_analysis_error_returns_safe_payload():
    async def failing_llm(_prompt):
        raise TimeoutError("request timeout")

    result = await CompetitorCitationService._analyze_citation_gaps(
        results={
            "your_brand": {"name": "Brand", "mentions": 0},
            "competitors": [{"name": "Competitor A", "mentions": 3}],
        },
        queries=["best brand alternatives"],
        llm_function=failing_llm,
    )

    assert result == {
        "has_data": False,
        "has_gaps": None,
        "error": "internal_error",
        "error_code": "timeout",
    }


def test_sanitize_gap_analysis_strips_historical_free_text():
    sanitized = CompetitorCitationService._sanitize_gap_analysis(
        {
            "has_gaps": True,
            "error": "Traceback (most recent call last): ...",
            "error_code": "raw_failure",
            "analysis": "sensitive text should not be sent to clients",
        }
    )

    assert sanitized == {
        "has_data": False,
        "has_gaps": None,
        "error": "internal_error",
        "error_code": "dependency_error",
    }


def test_get_citation_benchmark_sanitizes_historical_gap_analysis():
    analysis_row = SimpleNamespace(
        competitor_data="[]",
        gap_analysis='{"has_gaps": true, "error": "Traceback details", "error_code": "boom"}',
        your_mentions=2,
        analyzed_at=datetime.utcnow(),
    )

    class _Query:
        def filter(self, *_args, **_kwargs):
            return self

        def order_by(self, *_args, **_kwargs):
            return self

        def first(self):
            return analysis_row

    class _DB:
        def query(self, *_args, **_kwargs):
            return _Query()

    payload = CompetitorCitationService.get_citation_benchmark(_DB(), audit_id=1)
    assert payload["has_data"] is True
    assert payload["gap_analysis"] == {
        "has_data": False,
        "has_gaps": None,
        "error": "internal_error",
        "error_code": "dependency_error",
    }
