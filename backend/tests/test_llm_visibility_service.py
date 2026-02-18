from unittest.mock import AsyncMock, patch

import pytest
from app.services.llm_visibility_service import LLMVisibilityService


@pytest.mark.asyncio
async def test_generate_llm_visibility_accepts_keyword_dict_shape():
    batch_response = {
        "running shoes": {
            "chatgpt": {"visible": True, "rank": 3, "citation": "Example"},
            "gemini": {"visible": False, "rank": None, "citation": None},
            "perplexity": {"visible": True, "rank": 5, "citation": "Example"},
        }
    }

    with patch.object(
        LLMVisibilityService,
        "analyze_batch_visibility_with_llm",
        new=AsyncMock(return_value=batch_response),
    ):
        results = await LLMVisibilityService.generate_llm_visibility(
            [{"keyword": "running shoes"}],
            "https://example.com",
        )

    assert len(results) == 3
    assert all(item["query"] == "running shoes" for item in results)
    assert any(item["is_visible"] for item in results)
    gemini_row = next(item for item in results if item["llm_name"] == "Gemini")
    assert gemini_row["is_visible"] is False
    assert gemini_row["citation_text"] is None


def test_extract_term_supports_keyword_and_query_keys():
    assert LLMVisibilityService._extract_term({"keyword": "nike shoes"}) == "nike shoes"
    assert (
        LLMVisibilityService._extract_term({"query": "best sneakers"})
        == "best sneakers"
    )


@pytest.mark.asyncio
async def test_generate_llm_visibility_returns_empty_when_no_keywords():
    results = await LLMVisibilityService.generate_llm_visibility(
        [], "https://example.com"
    )
    assert results == []
