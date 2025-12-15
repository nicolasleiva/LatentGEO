
import pytest
import asyncio
import sys
import os
from unittest.mock import MagicMock
from pathlib import Path

# Add project root to sys.path to allow importing backend.app
# Assuming this file is in backend/tests/
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

# Mock sqlalchemy to avoid environment issues during import of PipelineService
sys.modules["sqlalchemy"] = MagicMock()
sys.modules["sqlalchemy.orm"] = MagicMock()

try:
    from auditor_geo.backend.app.services.pipeline_service import PipelineService
except ImportError:
    # Try alternative import if running directly from root without package structure
    try:
        from backend.app.services.pipeline_service import PipelineService
    except ImportError:
        # If running from backend directory
        from app.services.pipeline_service import PipelineService

@pytest.mark.asyncio
async def test_generate_report_v11_structure():
    """Verify that generate_report accepts new arguments and passes them to LLM prompt."""
    
    captured_prompts = {}

    # Mock LLM function to capture prompts
    async def mock_llm(system_prompt, user_prompt):
        captured_prompts['system'] = system_prompt
        captured_prompts['user'] = user_prompt
        return "Reporte\n---START_FIX_PLAN---\n[]"

    # Mock data
    target_audit = {"url": "https://example.com"}
    external_intelligence = {"is_ymyl": False}
    search_results = {}
    competitor_audits = []
    
    # New data
    pagespeed = {"mobile": {"score": 90}}
    keywords = {"opportunities": ["kw1"]}
    backlinks = {"top_links": ["link1"]}
    rank_tracking = {"positions": ["pos1"]}
    llm_visibility = {"mentions": ["gpt"]}
    ai_content = {"suggestions": ["blog1"]}

    # Call generate_report with all arguments
    report, fix_plan = await PipelineService.generate_report(
        target_audit,
        external_intelligence,
        search_results,
        competitor_audits,
        pagespeed_data=pagespeed,
        keywords_data=keywords,
        backlinks_data=backlinks,
        rank_tracking_data=rank_tracking,
        llm_visibility_data=llm_visibility,
        ai_content_suggestions=ai_content,
        llm_function=mock_llm
    )

    # Verify System Prompt contains new sections
    system_prompt = captured_prompts.get('system', '')
    assert "1. 'target_audit'" in system_prompt
    assert "10. 'ai_content_suggestions'" in system_prompt
    assert "3. Análisis de Rendimiento Web (PageSpeed & CWV)" in system_prompt
    assert "5. Análisis de Visibilidad y Competencia" in system_prompt
    
    # Verify User Prompt contains new data
    user_prompt = captured_prompts.get('user', '')
    assert '"pagespeed":' in user_prompt
    assert '"keywords":' in user_prompt
    assert '"rank_tracking":' in user_prompt
    assert '"kw1"' in user_prompt  # Check content of keywords
    
    print("Test passed: generate_report correctly integrates new V11 prompt and context data.")

@pytest.mark.asyncio
async def test_generate_report_partial_data():
    """Verify that generate_report handles partial data gracefully (Requirement 4.3)."""
    
    captured_prompts = {}
    async def mock_llm(system_prompt, user_prompt):
        captured_prompts['user'] = user_prompt
        return "Reporte\n---START_FIX_PLAN---\n[]"

    target_audit = {"url": "https://example.com"}
    external_intelligence = {"is_ymyl": False}
    search_results = {}
    competitor_audits = []

    # Only PageSpeed is present
    pagespeed = {"mobile": {"score": 50}}

    await PipelineService.generate_report(
        target_audit,
        external_intelligence,
        search_results,
        competitor_audits,
        pagespeed_data=pagespeed,
        # other optional data missing
        llm_function=mock_llm
    )

    user_prompt = captured_prompts.get('user', '')
    
    # Check that pagespeed is present
    assert '"pagespeed":' in user_prompt
    assert '"score": 50' in user_prompt
    
    # Check that missing keys are present as empty dicts (based on _ensure_dict or logic in generate_report)
    # The current implementation generates a context dict with keys even if None, 
    # but let's verify if they are empty objects in the JSON
    import json
    context_data = json.loads(user_prompt)
    
    assert context_data['keywords'] == {}
    assert context_data['backlinks'] == {}
    assert context_data['rank_tracking'] == {}
    
    print("Test passed: Partial data handled correctly, missing keys are empty dicts.")

@pytest.mark.asyncio
async def test_generate_report_complete_context_properties():
    """Verify property: All 10 keys are always present in the context passed to LLM (Requirement 4.4)."""
    
    captured_prompts = {}
    async def mock_llm(system_prompt, user_prompt):
        captured_prompts['user'] = user_prompt
        return "Report"

    # Minimal input
    target_audit = {"url": "https://example.com"}
    
    await PipelineService.generate_report(
        target_audit, {}, {}, [],
        llm_function=mock_llm
    )
    
    import json
    context_data = json.loads(captured_prompts['user'])
    
    expected_keys = [
        "target_audit", "external_intelligence", "search_results", "competitor_audits",
        "pagespeed", "keywords", "backlinks", "rank_tracking", 
        "llm_visibility", "ai_content_suggestions"
    ]
    
    for key in expected_keys:
        assert key in context_data, f"Key {key} missing from context"
        
    print("Test passed: All 10 context keys are present.")

if __name__ == "__main__":
    asyncio.run(test_generate_report_v11_structure())
    asyncio.run(test_generate_report_partial_data())
    asyncio.run(test_generate_report_complete_context_properties())
