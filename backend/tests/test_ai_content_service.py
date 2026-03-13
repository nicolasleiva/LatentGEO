import json

import pytest
from app.models import Audit, AuditStatus
from app.services.ai_content_service import AIContentService


@pytest.mark.asyncio
async def test_generate_suggestions_only_tags_strategy_runs_when_requested(
    db_session, monkeypatch
):
    audit = Audit(
        url="https://suggestions.example.com",
        domain="suggestions.example.com",
        status=AuditStatus.COMPLETED,
        category="ERP",
        external_intelligence={"category": "ERP"},
    )
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)

    monkeypatch.setattr(
        "app.services.ai_content_service.is_kimi_configured",
        lambda: True,
    )

    async def _fake_llm_function(*_args, **_kwargs):
        return json.dumps(
            [
                {
                    "title": "Guide 1",
                    "content_type": "guide",
                    "target_keyword": "guide 1",
                    "priority": "high",
                    "outline": ["A", "B"],
                },
                {
                    "title": "Guide 2",
                    "content_type": "comparison",
                    "target_keyword": "guide 2",
                    "priority": "medium",
                    "outline": ["C", "D"],
                },
            ]
        )

    service = AIContentService(db_session)
    service.llm_function = _fake_llm_function

    legacy_rows = await service.generate_suggestions(
        audit.id,
        "suggestions.example.com",
        [],
        count=2,
    )
    assert all(row.strategy_run_id is None for row in legacy_rows)
    assert all(row.strategy_order is None for row in legacy_rows)

    strategy_rows = await service.generate_suggestions(
        audit.id,
        "suggestions.example.com",
        [],
        count=2,
        create_strategy_run=True,
    )
    strategy_run_ids = {row.strategy_run_id for row in strategy_rows}

    assert len(strategy_run_ids) == 1
    assert None not in strategy_run_ids
    assert [row.strategy_order for row in strategy_rows] == [0, 1]
