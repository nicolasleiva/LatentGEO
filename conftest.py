"""
Pytest configuration and fixtures for auditor_geo tests
"""
import pytest
import sys
from pathlib import Path
import asyncio

# Set proper event loop policy for Windows
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from app.services.keywords_service import KeywordsService


@pytest.fixture(scope="function")
def keywords():
    """Fixture that provides generated keywords for testing"""
    target_audit = {
        "url": "https://example.com",
        "structure": {
            "h1_check": {
                "details": {
                    "example": "Best AI Coding Assistant",
                    "count": 1
                }
            }
        }
    }
    return KeywordsService.generate_keywords_from_audit(target_audit, "https://example.com")
