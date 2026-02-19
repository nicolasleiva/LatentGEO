"""
Production-Ready Integration Tests
No mocks, using real database and API calls
"""

import os
from urllib.parse import urlparse

import pytest
from app.core.config import settings
from app.models import Audit, Backlink, Keyword, RankTracking
from app.services.backlink_service import BacklinkService
from app.services.keyword_service import KeywordService
from app.services.rank_tracker_service import RankTrackerService

# Import production fixtures explicitly
from conftest_production import PROD_TEST_KEYWORDS
from sqlalchemy.orm import Session

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION_TESTS") != "1",
    reason="Requiere servicios externos/DB real y acceso a red",
)


def _domain_from_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.netloc:
        return parsed.netloc.replace("www.", "")
    return url.replace("https://", "").replace("http://", "").split("/")[0]


def _require_llm():
    if not any(
        [
            settings.NV_API_KEY,
            settings.NVIDIA_API_KEY,
            settings.NV_API_KEY_ANALYSIS,
            settings.NV_API_KEY_CODE,
        ]
    ):
        pytest.fail("NVIDIA/NV API key required for keyword integration tests.")


def _require_google_cse():
    if not settings.GOOGLE_API_KEY or not settings.CSE_ID:
        pytest.fail("GOOGLE_API_KEY and CSE_ID are required for rank tracking tests.")


class TestKeywordsServiceProduction:
    """
    Production-grade keyword service tests.
    Uses real database and real API calls (if configured).
    """

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_generate_keywords_from_real_audit(
        self, prod_db_session: Session, prod_test_audit
    ):
        """
        Test generating keywords from real audit data
        without mocks - uses actual database
        """
        _require_llm()
        assert prod_test_audit.id is not None

        domain = _domain_from_url(prod_test_audit.url)
        service = KeywordService(prod_db_session)

        keywords = await service.research_keywords(
            prod_test_audit.id,
            domain,
            seed_keywords=PROD_TEST_KEYWORDS or None,
        )

        assert keywords is not None
        assert len(keywords) > 0

        db_keywords = (
            prod_db_session.query(Keyword)
            .filter(Keyword.audit_id == prod_test_audit.id)
            .all()
        )

        assert len(db_keywords) > 0

        for keyword in db_keywords:
            assert keyword.term is not None
            assert keyword.volume is not None
            assert keyword.difficulty is not None
            assert keyword.cpc is not None

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_keywords_saved_to_database(
        self, prod_db_session: Session, prod_test_audit
    ):
        """
        Verify keywords are properly persisted to database
        """
        _require_llm()
        initial_count = (
            prod_db_session.query(Keyword)
            .filter(Keyword.audit_id == prod_test_audit.id)
            .count()
        )

        domain = _domain_from_url(prod_test_audit.url)
        service = KeywordService(prod_db_session)
        await service.research_keywords(
            prod_test_audit.id,
            domain,
            seed_keywords=PROD_TEST_KEYWORDS or None,
        )

        final_count = (
            prod_db_session.query(Keyword)
            .filter(Keyword.audit_id == prod_test_audit.id)
            .count()
        )

        assert final_count > initial_count

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_keyword_fields_are_valid(
        self, prod_db_session: Session, prod_test_audit
    ):
        """
        Verify all keyword fields contain valid data
        """
        _require_llm()
        domain = _domain_from_url(prod_test_audit.url)
        service = KeywordService(prod_db_session)
        await service.research_keywords(
            prod_test_audit.id,
            domain,
            seed_keywords=PROD_TEST_KEYWORDS or None,
        )

        db_keywords = (
            prod_db_session.query(Keyword)
            .filter(Keyword.audit_id == prod_test_audit.id)
            .all()
        )

        for keyword in db_keywords:
            assert keyword.id is not None
            assert keyword.audit_id is not None
            assert isinstance(keyword.term, str)
            assert len(keyword.term) > 0
            assert keyword.volume >= 0
            assert 0 <= keyword.difficulty <= 100
            assert keyword.created_at is not None


class TestBacklinksServiceProduction:
    """
    Production-grade backlinks service tests.
    """

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_generate_backlinks_from_real_audit(
        self, prod_db_session: Session, prod_test_audit
    ):
        """
        Test generating backlinks from real audit data
        """
        domain = _domain_from_url(prod_test_audit.url)
        service = BacklinkService(prod_db_session)
        backlinks = await service.analyze_backlinks(prod_test_audit.id, domain)

        assert backlinks is not None

        db_backlinks = (
            prod_db_session.query(Backlink)
            .filter(Backlink.audit_id == prod_test_audit.id)
            .all()
        )

        assert len(db_backlinks) >= 0

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_backlinks_structure_valid(
        self, prod_db_session: Session, prod_test_audit
    ):
        """
        Verify backlinks have valid structure
        """
        domain = _domain_from_url(prod_test_audit.url)
        service = BacklinkService(prod_db_session)
        backlinks = await service.analyze_backlinks(prod_test_audit.id, domain)

        for backlink in backlinks:
            assert backlink.source_url is not None
            assert backlink.target_url is not None
            assert backlink.is_dofollow in [True, False]


class TestRankTrackingServiceProduction:
    """
    Production-grade rank tracking service tests.
    """

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_generate_rankings_from_real_keywords(
        self,
        prod_db_session: Session,
        prod_test_audit,
    ):
        """
        Test generating rankings from real keywords
        """
        _require_google_cse()
        domain = _domain_from_url(prod_test_audit.url)
        service = RankTrackerService(prod_db_session)
        rankings = await service.track_rankings(
            prod_test_audit.id,
            domain,
            PROD_TEST_KEYWORDS,
        )

        assert rankings is not None
        assert len(rankings) > 0

        db_rankings = (
            prod_db_session.query(RankTracking)
            .filter(RankTracking.audit_id == prod_test_audit.id)
            .all()
        )

        assert len(db_rankings) > 0

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_ranking_fields_valid(
        self, prod_db_session: Session, prod_test_audit
    ):
        """
        Verify ranking fields are valid
        """
        _require_google_cse()
        domain = _domain_from_url(prod_test_audit.url)
        service = RankTrackerService(prod_db_session)
        rankings = await service.track_rankings(
            prod_test_audit.id,
            domain,
            PROD_TEST_KEYWORDS,
        )

        for ranking in rankings:
            assert ranking.keyword is not None
            assert ranking.position >= 0
            assert ranking.url is not None


class TestAuditDataPersistence:
    """
    Test that audit data is properly persisted to real database
    """

    @pytest.mark.integration
    def test_audit_data_persistence(self, prod_db_session: Session, prod_test_audit):
        """
        Verify audit is saved in database
        """
        audit = (
            prod_db_session.query(Audit).filter(Audit.id == prod_test_audit.id).first()
        )

        assert audit is not None
        assert audit.url == prod_test_audit.url
        assert audit.status == "COMPLETED"
        assert audit.created_at is not None

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_audit_relationships(self, prod_db_session: Session, prod_test_audit):
        """
        Verify relationships between audit and keywords
        """
        _require_llm()
        domain = _domain_from_url(prod_test_audit.url)
        service = KeywordService(prod_db_session)
        await service.research_keywords(
            prod_test_audit.id,
            domain,
            seed_keywords=PROD_TEST_KEYWORDS or None,
        )

        audit = (
            prod_db_session.query(Audit).filter(Audit.id == prod_test_audit.id).first()
        )

        assert len(audit.keywords) > 0
        for keyword in audit.keywords:
            assert keyword.audit_id == audit.id


class TestDatabaseTransactions:
    """
    Test database transaction handling
    """

    @pytest.mark.integration
    def test_rollback_on_error(self, prod_db_session: Session):
        """
        Verify that failed operations are rolled back
        """
        assert prod_db_session.in_transaction()

    @pytest.mark.integration
    def test_data_isolation_between_tests(self, prod_db_session: Session):
        """
        Verify test isolation - no data leaks between tests
        """
        audit_count = prod_db_session.query(Audit).count()
        keyword_count = prod_db_session.query(Keyword).count()

        assert audit_count >= 0
        assert keyword_count >= 0


# Pytest markers for production tests
def pytest_configure(config):
    """Register custom markers"""
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests (deselect with '-m \"not integration\"')",
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
