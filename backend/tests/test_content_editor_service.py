from unittest.mock import AsyncMock, patch

import pytest
from app.services.content_editor_service import ContentEditorService


@pytest.mark.asyncio
async def test_content_editor_calls_llm_with_system_and_user_prompts():
    mock_llm = AsyncMock(
        return_value='{"score":80,"summary":"ok","pillars":{"direct_answer":{"score":8,"feedback":"ok"},"structure":{"score":8,"feedback":"ok"},"authority":{"score":8,"feedback":"ok"},"semantics":{"score":8,"feedback":"ok"}},"suggestions":[],"missing_entities":[]}'
    )

    with patch(
        "app.services.content_editor_service.get_llm_function",
        return_value=mock_llm,
    ):
        service = ContentEditorService()
        result = await service.analyze_content("Sample content", "nike shoes")

    assert result["score"] == 80
    _, kwargs = mock_llm.call_args
    assert "system_prompt" in kwargs
    assert "user_prompt" in kwargs
