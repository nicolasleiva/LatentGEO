from datetime import datetime, timezone

from app.models import Audit, AuditStatus
from app.services.backlink_service import BacklinkService
from app.services.keyword_service import KeywordService
from app.services.llm_visibility_service import LLMVisibilityService
from app.services.rank_tracker_service import RankTrackerService


def _seed_audit(db_session) -> int:
    audit = Audit(
        url="https://www.robot.com",
        domain="www.robot.com",
        status=AuditStatus.COMPLETED,
        user_id="test-user",
        user_email="test@example.com",
    )
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)
    return audit.id


def test_manual_smoke_equivalent_endpoints(client, db_session, monkeypatch):
    audit_id = _seed_audit(db_session)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    async def fake_keywords(self, audit_id: int, domain: str, seed_keywords=None):
        return [
            {
                "id": 1,
                "audit_id": audit_id,
                "term": "geo seo tool",
                "volume": 800,
                "difficulty": 42,
                "cpc": 1.2,
                "intent": "commercial",
                "created_at": now,
            }
        ]

    async def fake_backlinks(self, audit_id: int, domain: str):
        return [
            {
                "id": 1,
                "audit_id": audit_id,
                "source_url": "https://example.com/post",
                "target_url": "https://www.robot.com/page",
                "anchor_text": "robot",
                "is_dofollow": True,
                "domain_authority": 60,
                "created_at": now,
            }
        ]

    async def fake_rankings(self, audit_id: int, domain: str, keywords):
        return [
            {
                "id": 1,
                "audit_id": audit_id,
                "keyword": "geo seo tool",
                "position": 5,
                "url": "https://www.robot.com/page",
                "device": "desktop",
                "location": "US",
                "top_results": [],
                "tracked_at": now,
            }
        ]

    async def fake_visibility(self, audit_id: int, brand_name: str, queries):
        return [
            {
                "id": 1,
                "audit_id": audit_id,
                "llm_name": "kimi",
                "query": queries[0],
                "is_visible": True,
                "rank": 1,
                "citation_text": "Robot mention",
                "checked_at": now,
            }
        ]

    monkeypatch.setattr(KeywordService, "research_keywords", fake_keywords)
    monkeypatch.setattr(BacklinkService, "analyze_backlinks", fake_backlinks)
    monkeypatch.setattr(RankTrackerService, "track_rankings", fake_rankings)
    monkeypatch.setattr(LLMVisibilityService, "check_visibility", fake_visibility)

    keywords = client.post(
        f"/api/v1/keywords/research/{audit_id}?domain=www.robot.com",
        json=[],
    )
    backlinks = client.post(
        f"/api/v1/backlinks/analyze/{audit_id}?domain=www.robot.com",
    )
    rankings = client.post(
        f"/api/v1/rank-tracking/track/{audit_id}?domain=www.robot.com",
        json=["geo seo tool"],
    )
    visibility = client.post(
        f"/api/v1/llm-visibility/check/{audit_id}?brand_name=LatentGEO",
        json=["Is this brand visible in AI answers?"],
    )

    assert keywords.status_code == 200
    assert backlinks.status_code == 200
    assert rankings.status_code == 200
    assert visibility.status_code == 200
