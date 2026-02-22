from datetime import datetime

from app.services.pipeline_service import PipelineService


def test_now_iso_is_valid_utc_format():
    value = PipelineService.now_iso()
    assert value.endswith("Z")
    assert "+00:00Z" not in value
    datetime.fromisoformat(value.replace("Z", "+00:00"))


def test_parse_agent_json_or_raw_parses_valid_json():
    payload = '{"status":"ok","items":[1,2,3]}'
    parsed = PipelineService.parse_agent_json_or_raw(payload)
    assert parsed == {"status": "ok", "items": [1, 2, 3]}


def test_parse_agent_json_or_raw_handles_trailing_commas():
    payload = '{"status":"ok","items":[1,2,3,],}'
    parsed = PipelineService.parse_agent_json_or_raw(payload)
    assert parsed == {"status": "ok", "items": [1, 2, 3]}


def test_parse_agent_json_or_raw_rejects_oversized_payload(monkeypatch):
    monkeypatch.setattr(
        "app.services.pipeline_service.settings.PIPELINE_JSON_PARSE_MAX_CHARS",
        64,
        raising=False,
    )
    huge = "[" + ("[0]," * 200) + "]"
    parsed = PipelineService.parse_agent_json_or_raw(huge)
    assert "raw" in parsed
    assert len(parsed["raw"]) <= 64
