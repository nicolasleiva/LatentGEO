
import pytest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from unittest.mock import MagicMock
from app.integrations.github.service import GitHubService
from app.models import Audit

@pytest.fixture
def mock_db():
    return MagicMock()

def test_map_issue_to_fix_type(mock_db):
    service = GitHubService(mock_db)
    
    # Test valid mappings
    assert service._map_issue_to_fix_type("Missing meta description") == "meta_description"
    assert service._map_issue_to_fix_type("Title tag is too long") == "title"
    
    # Test new mappings
    assert service._map_issue_to_fix_type("Add more content") == "content_improvement"
    assert service._map_issue_to_fix_type("Keyword density low") == "content_improvement"

    # Test unmappable
    assert service._map_issue_to_fix_type("Update server") == "other"

    # Test issue_code mappings
    assert service._map_issue_to_fix_type("", "H1_MISSING") == "h1"
    assert service._map_issue_to_fix_type("", "H1_HIERARCHY_SKIP") == "structure"
    assert service._map_issue_to_fix_type("", "SCHEMA_MISSING") == "schema"
    assert service._map_issue_to_fix_type("", "PRODUCT_SCHEMA_MISSING") == "schema"
    assert service._map_issue_to_fix_type("", "AUTHOR_MISSING") == "add_author_metadata"
    assert service._map_issue_to_fix_type("", "FAQ_MISSING") == "add_faq_section"
    assert service._map_issue_to_fix_type("", "LONG_PARAGRAPH") == "add_lists_tables"
    assert service._map_issue_to_fix_type("", "PRODUCT_CONTENT_GAP") == "content_enhancement"

def test_prepare_fixes_from_audit_valid_fixes(mock_db):
    service = GitHubService(mock_db)
    
    audit = MagicMock(spec=Audit)
    audit.id = 1
    audit.fix_plan = [
        {"issue": "Missing meta description", "priority": "HIGH"},
        {"issue": "Title tag missing", "priority": "HIGH"}
    ]
    
    fixes = service.prepare_fixes_from_audit(audit)
    
    assert len(fixes) == 2
    assert fixes[0]["type"] == "meta_description"
    assert fixes[1]["type"] == "title"

def test_prepare_fixes_from_audit_fallback(mock_db):
    service = GitHubService(mock_db)
    
    audit = MagicMock(spec=Audit)
    audit.id = 2
    audit.fix_plan = [{"issue": "Unmappable Issue", "priority": "HIGH"}]
    
    # "Unmappable Issue" maps to "other", so it gets filtered out.
    # Logic should fall back to default fixes.
    
    fixes = service.prepare_fixes_from_audit(audit)
    
    assert len(fixes) == 4 # The default set has 4 items
    assert fixes[0]["type"] == "title"
    assert fixes[0]["description"] == "Optimize page title for SEO and Click-Through Rate"

def test_prepare_fixes_from_audit_content_fixes(mock_db):
    service = GitHubService(mock_db)
    
    audit = MagicMock(spec=Audit)
    audit.id = 3
    audit.fix_plan = [{"issue": "Content is too short", "priority": "MEDIUM"}]

    fixes = service.prepare_fixes_from_audit(audit)
    
    assert len(fixes) == 1
    assert fixes[0]["type"] == "content_improvement"

def test_prepare_fixes_from_audit_no_plan(mock_db):
    service = GitHubService(mock_db)
    
    audit = MagicMock(spec=Audit)
    audit.id = 4
    audit.fix_plan = None
    
    fixes = service.prepare_fixes_from_audit(audit)
    
    assert len(fixes) == 4 # Defaults
