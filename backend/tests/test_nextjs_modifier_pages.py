
import pytest
import sys
import os
from unittest.mock import MagicMock, patch

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from app.integrations.github.nextjs_modifier import NextJsModifier

def test_pages_router_metadata_fix_invokes_comprehensive_fixes():
    """
    Test that metadata fixes for Pages Router (non-App Router) 
    are handled by the comprehensive JSX transformation phase.
    """
    content = """
import Head from 'next/head';

export default function Home() {
  return (
    <div>
      <Head>
        <title>Old Title</title>
      </Head>
      <h1>Welcome</h1>
    </div>
  );
}
"""
    fixes = [
        {"type": "title", "value": "New Optimized Title"},
        {"type": "meta_description", "value": "New Optimized Description"}
    ]
    file_path = "pages/index.tsx" # Pages router path
    
    modifier = NextJsModifier()
    
    # Mock _apply_comprehensive_jsx_fixes to see if it's called
    with patch.object(NextJsModifier, '_apply_comprehensive_jsx_fixes') as mock_comprehensive:
        mock_comprehensive.return_value = "Modified Content"
        
        result = modifier._apply_fixes_internal(content, fixes, file_path)
        
        # Verify that _apply_comprehensive_jsx_fixes was called
        # because metadata_fixes should NOT have been handled by Phase 1 (App Router specific)
        mock_comprehensive.assert_called_once()
        
        # Verify the fixes passed to it include the metadata fixes
        args, kwargs = mock_comprehensive.call_args
        passed_fixes = args[1]
        fix_types = [f['type'] for f in passed_fixes]
        assert "title" in fix_types
        assert "meta_description" in fix_types
        assert result == "Modified Content"

def test_app_router_metadata_fix_uses_phase1():
    """
    Test that metadata fixes for App Router ARE handled by Phase 1
    and then metadata_fixes list is emptied for Phase 2.
    """
    content = """
export const metadata = {
  title: "Old Title",
  description: "Old Description"
}

export default function Page() {
  return <h1>App Router Page</h1>
}
"""
    fixes = [
        {"type": "title", "value": "New Title"},
        {"type": "h1", "value": "New H1"} # Structural fix to trigger Phase 2
    ]
    file_path = "app/page.tsx" # App router path
    
    modifier = NextJsModifier()
    
    with patch.object(NextJsModifier, '_update_metadata_with_kimi') as mock_phase1:
        with patch.object(NextJsModifier, '_apply_comprehensive_jsx_fixes') as mock_phase2:
            mock_phase1.return_value = "Phase 1 Content"
            mock_phase2.return_value = "Phase 2 Content"
            
            result = modifier._apply_fixes_internal(content, fixes, file_path)
            
            # Phase 1 should be called for title
            mock_phase1.assert_called_once()
            
            # Phase 2 should be called for h1
            mock_phase2.assert_called_once()
            
            # Verify Phase 2 only got the structural fix (h1), not the title
            args, kwargs = mock_phase2.call_args
            passed_fixes = args[1]
            fix_types = [f['type'] for f in passed_fixes]
            assert "h1" in fix_types
            assert "title" not in fix_types
            assert result == "Phase 2 Content"
