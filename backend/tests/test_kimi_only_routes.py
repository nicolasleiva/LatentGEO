from app.models import Audit, AuditStatus
from app.services.keyword_service import KeywordService
from app.services.llm_visibility_service import LLMVisibilityService
from app.core.llm_kimi import KimiGenerationError


def _seed_audit(db_session) -> int:
    audit = Audit(
        url="https://example.com",
        domain="example.com",
        status=AuditStatus.COMPLETED,
        user_id="test-user",
        user_email="test@example.com",
        category="software",
    )
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)
    return audit.id


def _disable_kimi_keys(monkeypatch):
    monkeypatch.setattr("app.core.llm_kimi.settings.NV_API_KEY_ANALYSIS", None)
    monkeypatch.setattr("app.core.llm_kimi.settings.NVIDIA_API_KEY", None)
    monkeypatch.setattr("app.core.llm_kimi.settings.NV_API_KEY", None)


def _enable_analysis_key_only(monkeypatch):
    monkeypatch.setattr("app.core.llm_kimi.settings.NV_API_KEY_ANALYSIS", "analysis-key")
    monkeypatch.setattr("app.core.llm_kimi.settings.NVIDIA_API_KEY", None)
    monkeypatch.setattr("app.core.llm_kimi.settings.NV_API_KEY", None)


def test_ai_content_generate_returns_503_when_kimi_missing(client, db_session, monkeypatch):
    audit_id = _seed_audit(db_session)
    _disable_kimi_keys(monkeypatch)

    response = client.post(
        f"/api/ai-content/generate/{audit_id}?domain=example.com",
        json=["ai"],
    )
    assert response.status_code == 503
    payload = response.json()
    assert payload["detail"]["code"] == "KIMI_UNAVAILABLE"


def test_keywords_research_returns_503_when_kimi_missing(client, db_session, monkeypatch):
    audit_id = _seed_audit(db_session)
    _disable_kimi_keys(monkeypatch)

    response = client.post(
        f"/api/keywords/research/{audit_id}?domain=example.com",
        json=["ai seo"],
    )
    assert response.status_code == 503
    payload = response.json()
    assert payload["detail"]["code"] == "KIMI_UNAVAILABLE"


def test_llm_visibility_check_returns_503_when_kimi_missing(client, db_session, monkeypatch):
    audit_id = _seed_audit(db_session)
    _disable_kimi_keys(monkeypatch)

    response = client.post(
        f"/api/llm-visibility/check/{audit_id}?brand_name=example",
        json=["best ai tools"],
    )
    assert response.status_code == 503
    payload = response.json()
    assert payload["detail"]["code"] == "KIMI_UNAVAILABLE"


def test_keyword_service_accepts_nv_api_key_analysis_only(db_session, monkeypatch):
    _enable_analysis_key_only(monkeypatch)

    service = KeywordService(db_session)
    assert service.nvidia_api_key == "analysis-key"
    assert service.client is not None


def test_ai_content_returns_502_on_invalid_kimi_json(client, db_session, monkeypatch):
    audit_id = _seed_audit(db_session)
    _enable_analysis_key_only(monkeypatch)

    async def fake_llm(system_prompt: str, user_prompt: str):
        return "not-json"

    monkeypatch.setattr("app.services.ai_content_service.get_llm_function", lambda: fake_llm)

    response = client.post(
        f"/api/ai-content/generate/{audit_id}?domain=example.com",
        json=["ai"],
    )
    assert response.status_code == 502
    payload = response.json()
    assert payload["detail"]["code"] == "KIMI_GENERATION_FAILED"


def test_llm_visibility_returns_502_on_kimi_runtime_error(client, db_session, monkeypatch):
    audit_id = _seed_audit(db_session)
    _enable_analysis_key_only(monkeypatch)

    async def fake_analyze(*args, **kwargs):
        raise KimiGenerationError("forced visibility failure")

    monkeypatch.setattr(LLMVisibilityService, "analyze_batch_visibility_with_llm", fake_analyze)

    response = client.post(
        f"/api/llm-visibility/check/{audit_id}?brand_name=example",
        json=["best ai tools"],
    )
    assert response.status_code == 502
    payload = response.json()
    assert payload["detail"]["code"] == "KIMI_GENERATION_FAILED"
    assert "forced visibility failure" in payload["detail"]["message"]
