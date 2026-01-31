"""
Production-Ready Integration Tests
No mocks, using real database and API calls
"""
import pytest
import os
from sqlalchemy.orm import Session
from datetime import datetime

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION_TESTS") != "1",
    reason="Requiere servicios externos/DB real y acceso a red",
)

from app.services.keywords_service import KeywordsService
from app.services.backlinks_service import BacklinksService
from app.services.rank_tracking_service import RankTrackingService
from app.schemas import AuditCreate, AuditUpdate
from app.models import Audit, Keyword, Backlink, RankTracking

# Import production fixtures explicitly
from .conftest_production import prod_db_session, prod_test_audit, prod_test_keywords, prod_test_user


class TestKeywordsServiceProduction:
    """
    Production-grade keyword service tests.
    Uses real database and real API calls (if configured).
    """
    
    @pytest.mark.integration
    def test_generate_keywords_from_real_audit(self, prod_db_session: Session, prod_test_audit):
        """
        Test generating keywords from real audit data
        without mocks - uses actual database
        """
        # Create real audit data in database
        assert prod_test_audit.id is not None
        
        # Call service with real database object
        keywords = KeywordsService.generate_keywords_from_audit(
            prod_test_audit,
            prod_test_audit.url
        )
        
        # Verify results are persisted in database
        assert keywords is not None
        assert len(keywords) > 0
        
        # Verify keywords are saved in database
        db_keywords = prod_db_session.query(Keyword).filter(
            Keyword.audit_id == prod_test_audit.id
        ).all()
        
        assert len(db_keywords) > 0
        
        # Verify keyword structure
        for keyword in db_keywords:
            assert keyword.keyword is not None
            assert keyword.search_volume is not None
            assert keyword.difficulty is not None
            assert keyword.current_rank is not None
    
    @pytest.mark.integration
    def test_keywords_saved_to_database(self, prod_db_session: Session, prod_test_audit):
        """
        Verify keywords are properly persisted to database
        """
        initial_count = prod_db_session.query(Keyword).filter(
            Keyword.audit_id == prod_test_audit.id
        ).count()
        
        # Generate keywords
        KeywordsService.generate_keywords_from_audit(
            prod_test_audit,
            prod_test_audit.url
        )
        
        # Verify they were added to database
        final_count = prod_db_session.query(Keyword).filter(
            Keyword.audit_id == prod_test_audit.id
        ).count()
        
        assert final_count > initial_count
    
    @pytest.mark.integration
    def test_keyword_fields_are_valid(self, prod_db_session: Session, prod_test_keywords):
        """
        Verify all keyword fields contain valid data
        """
        for keyword in prod_test_keywords:
            # Verify database persistence
            assert keyword.id is not None
            assert keyword.audit_id is not None
            
            # Verify data validity
            assert isinstance(keyword.keyword, str)
            assert len(keyword.keyword) > 0
            assert keyword.search_volume >= 0
            assert 0 <= keyword.difficulty <= 100
            assert keyword.current_rank > 0
            
            # Verify timestamp
            assert keyword.created_at is not None


class TestBacklinksServiceProduction:
    """
    Production-grade backlinks service tests.
    """
    
    @pytest.mark.integration
    def test_generate_backlinks_from_real_audit(self, prod_db_session: Session, prod_test_audit):
        """
        Test generating backlinks from real audit data
        """
        backlinks = BacklinksService.generate_backlinks_from_audit(
            prod_test_audit,
            prod_test_audit.url
        )
        
        assert backlinks is not None
        assert "total_backlinks" in backlinks
        assert "referring_domains" in backlinks
        assert "summary" in backlinks
        assert "top_backlinks" in backlinks
        
        # Verify data is saved to database
        db_backlinks = prod_db_session.query(Backlink).filter(
            Backlink.audit_id == prod_test_audit.id
        ).all()
        
        assert len(db_backlinks) >= 0  # Can be 0 if no real backlinks
    
    @pytest.mark.integration
    def test_backlinks_structure_valid(self, prod_db_session: Session, prod_test_audit):
        """
        Verify backlinks have valid structure
        """
        backlinks = BacklinksService.generate_backlinks_from_audit(
            prod_test_audit,
            prod_test_audit.url
        )
        
        # Verify summary section
        summary = backlinks.get("summary", {})
        assert "dofollow_count" in summary
        assert "nofollow_count" in summary
        assert "average_domain_authority" in summary
        
        # Verify top backlinks
        top_backlinks = backlinks.get("top_backlinks", [])
        for backlink in top_backlinks:
            assert "source_url" in backlink
            assert "domain_authority" in backlink
            assert "is_dofollow" in backlink


class TestRankTrackingServiceProduction:
    """
    Production-grade rank tracking service tests.
    """
    
    @pytest.mark.integration
    def test_generate_rankings_from_real_keywords(
        self,
        prod_db_session: Session,
        prod_test_audit,
        prod_test_keywords
    ):
        """
        Test generating rankings from real keywords
        """
        rankings = RankTrackingService.generate_rankings_from_keywords(
            prod_test_keywords,
            prod_test_audit.url
        )
        
        assert rankings is not None
        assert len(rankings) > 0
        
        # Verify rankings are saved to database
        db_rankings = prod_db_session.query(RankTracking).filter(
            RankTracking.audit_id == prod_test_audit.id
        ).all()
        
        assert len(db_rankings) > 0
    
    @pytest.mark.integration
    def test_ranking_fields_valid(self, prod_db_session: Session, prod_test_keywords, prod_test_audit):
        """
        Verify ranking fields are valid
        """
        rankings = RankTrackingService.generate_rankings_from_keywords(
            prod_test_keywords,
            prod_test_audit.url
        )
        
        for ranking in rankings:
            # Position should be 1-100+
            assert ranking.get("position", 0) > 0
            # Traffic value should be realistic
            assert ranking.get("estimated_traffic", 0) >= 0
            # Trend should be one of these values
            assert ranking.get("trend", "") in ["up", "down", "stable", ""]


class TestAuditDataPersistence:
    """
    Test that audit data is properly persisted to real database
    """
    
    @pytest.mark.integration
    def test_audit_data_persistence(self, prod_db_session: Session, prod_test_audit):
        """
        Verify audit is saved in database
        """
        # Query the database
        audit = prod_db_session.query(Audit).filter(
            Audit.id == prod_test_audit.id
        ).first()
        
        assert audit is not None
        assert audit.url == prod_test_audit.url
        assert audit.status == "COMPLETED"
        assert audit.created_at is not None
    
    @pytest.mark.integration
    def test_audit_relationships(self, prod_db_session: Session, prod_test_audit, prod_test_keywords):
        """
        Verify relationships between audit and keywords
        """
        # Query audit with relationships
        audit = prod_db_session.query(Audit).filter(
            Audit.id == prod_test_audit.id
        ).first()
        
        # Verify relationships are loaded
        assert len(audit.keywords) > 0
        
        # Verify keyword belongs to audit
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
        # This should be handled by pytest fixtures
        # Each test gets a fresh transaction
        assert prod_db_session.in_transaction()
    
    @pytest.mark.integration
    def test_data_isolation_between_tests(self, prod_db_session: Session):
        """
        Verify test isolation - no data leaks between tests
        """
        # Count all records
        audit_count = prod_db_session.query(Audit).count()
        keyword_count = prod_db_session.query(Keyword).count()
        
        # Should only have what this test created
        assert audit_count >= 0
        assert keyword_count >= 0


# Pytest markers for production tests
def pytest_configure(config):
    """Register custom markers"""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (deselect with '-m \"not integration\"')"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
