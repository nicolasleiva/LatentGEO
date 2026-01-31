
import pytest
import sys
import os
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from app.integrations.github.service import GitHubService
from app.models.github import GitHubConnection, GitHubRepository, GitHubPullRequest
from app.models import Audit

@pytest.mark.asyncio
async def test_create_pr_with_fixes_resets_branch():
    """
    Test that create_pr_with_fixes calls client.create_branch 
    which handles the branch reset.
    """
    mock_db = MagicMock()
    service = GitHubService(mock_db)
    
    connection_id = "conn_123"
    repo_id = "repo_123"
    audit_id = 1
    fixes = [{"type": "title", "value": "New Title"}]
    
    # Mock database objects
    mock_connection = MagicMock(spec=GitHubConnection)
    mock_connection.access_token = "encrypted_token"
    mock_connection.is_active = True
    
    mock_repo = MagicMock(spec=GitHubRepository)
    mock_repo.full_name = "owner/repo"
    mock_repo.default_branch = "main"
    mock_repo.site_type = "nextjs"
    
    mock_audit = MagicMock(spec=Audit)
    mock_audit.id = audit_id
    mock_audit.keywords = []
    mock_audit.pagespeed_data = None
    mock_audit.target_audit = None
    mock_audit.ai_content_suggestions = []
    
    # Setup DB mocks
    mock_db.query.return_value.filter.return_value.first.side_effect = [
        mock_connection, # get_valid_client
        mock_repo,       # create_pr_with_fixes
        mock_audit       # create_pr_with_fixes
    ]
    
    # Mock GitHubClient
    mock_client = MagicMock()
    mock_gh_repo = MagicMock()
    mock_client.get_repo.return_value = mock_gh_repo
    mock_client.find_page_files.return_value = ["pages/index.tsx"]
    mock_client.get_file_content.return_value = "original content"
    mock_client.create_pull_request.return_value = {
        "github_pr_id": "pr_123",
        "pr_number": 1,
        "html_url": "https://github.com/owner/repo/pull/1"
    }
    
    # Mock CodeModifierService and PRGeneratorService
    with patch("app.integrations.github.service.GitHubOAuth.decrypt_token", return_value="decrypted_token"), \
         patch("app.integrations.github.service.GitHubClient", return_value=mock_client), \
         patch("app.integrations.github.service.PRGeneratorService") as mock_pr_gen, \
         patch("app.integrations.github.service.CodeModifierService") as mock_code_mod:
        
        mock_pr_gen.generate_branch_name.return_value = "seo-fix-1"
        mock_code_mod.apply_fixes.return_value = "modified content"
        
        await service.create_pr_with_fixes(connection_id, repo_id, audit_id, fixes)
        
        # Verify branch creation/reset was called
        mock_client.create_branch.assert_called_once_with(mock_gh_repo, "seo-fix-1", "main")
        
        # Verify file update was called
        mock_client.update_file.assert_called_once()
        
        # Verify PR creation was called
        mock_client.create_pull_request.assert_called_once()
