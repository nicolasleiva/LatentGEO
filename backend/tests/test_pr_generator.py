import os
import sys

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from app.integrations.github.pr_generator import PRGeneratorService


def test_generate_pr_body_handles_structured_values():
    audit_data = {
        "id": 35,
        "total_pages": 1,
        "critical_issues": 0,
        "high_issues": 0,
        "medium_issues": 0,
    }
    fixes = [
        {"type": "schema"},
        {"type": "add_author_metadata"},
    ]
    file_changes = {
        "app/page.tsx": [
            {
                "type": "schema",
                "before": "",
                "after": {"@context": "https://schema.org", "@type": "WebPage"},
            },
            {
                "type": "add_author_metadata",
                "before": "",
                "after": [{"q": "What is this?", "a": "Answer"}],
            },
        ]
    }

    body = PRGeneratorService.generate_pr_body(audit_data, fixes, file_changes)

    assert "app/page.tsx" in body
    assert "@context" in body
