import pytest

from app.models import Audit, AuditStatus
from app.services.rank_tracker_service import RankTrackerService


@pytest.mark.asyncio
async def test_track_rankings_truncates_keywords_and_persists_warning(db_session):
    audit = Audit(
        url="https://example-rankings.com",
        domain="example-rankings.com",
        status=AuditStatus.COMPLETED,
        user_id="test-user",
        user_email="test@example.com",
    )
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)

    service = RankTrackerService(db_session)
    long_keyword = "keyword " * 40

    async def _fake_position(query: str, domain: str):
        return 3, [{"position": 1, "url": "https://example.com", "title": query}]

    service._get_position_and_top_results = _fake_position  # type: ignore[method-assign]

    rankings = await service.track_rankings(
        audit.id,
        audit.domain,
        [long_keyword, "   "],
    )

    assert len(rankings) == 1
    assert len(rankings[0].keyword) == 255
    refreshed_audit = db_session.query(Audit).filter(Audit.id == audit.id).first()
    assert refreshed_audit is not None
    assert any(
        item.get("code") == "rank_tracking_keyword_truncated"
        for item in refreshed_audit.runtime_diagnostics
    )
    assert any(
        item.get("code") == "rank_tracking_keyword_skipped"
        for item in refreshed_audit.runtime_diagnostics
    )


@pytest.mark.asyncio
async def test_track_rankings_continues_when_a_row_cannot_be_persisted(db_session):
    audit = Audit(
        url="https://example-rankings-retry.com",
        domain="example-rankings-retry.com",
        status=AuditStatus.COMPLETED,
        user_id="test-user",
        user_email="test@example.com",
    )
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)

    service = RankTrackerService(db_session)

    async def _fake_position(query: str, domain: str):
        return 1, []

    original_persist = service._persist_ranking

    def _persist_with_one_failure(ranking):
        if ranking.keyword == "first keyword":
            return False
        return original_persist(ranking)

    service._get_position_and_top_results = _fake_position  # type: ignore[method-assign]
    service._persist_ranking = _persist_with_one_failure  # type: ignore[method-assign]

    rankings = await service.track_rankings(
        audit.id,
        audit.domain,
        ["first keyword", "second keyword"],
    )

    assert [ranking.keyword for ranking in rankings] == ["second keyword"]
    refreshed_audit = db_session.query(Audit).filter(Audit.id == audit.id).first()
    assert refreshed_audit is not None
    assert any(
        item.get("code") == "rank_tracking_row_persist_failed"
        for item in refreshed_audit.runtime_diagnostics
    )


@pytest.mark.asyncio
async def test_track_rankings_endpoint_truncates_long_keywords(
    client, db_session, monkeypatch
):
    audit = Audit(
        url="https://example-rankings-endpoint.com",
        domain="example-rankings-endpoint.com",
        status=AuditStatus.COMPLETED,
        user_id="test-user",
        user_email="test@example.com",
    )
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)

    async def _fake_position(self, query: str, domain: str):
        return 2, [{"position": 1, "url": f"https://{domain}", "title": query}]

    monkeypatch.setattr(
        RankTrackerService,
        "_get_position_and_top_results",
        _fake_position,
    )

    long_keyword = "keyword " * 40
    response = client.post(
        f"/api/v1/rank-tracking/track/{audit.id}?domain={audit.domain}",
        json=[long_keyword],
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert len(payload[0]["keyword"]) == 255
