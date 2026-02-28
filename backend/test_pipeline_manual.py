import asyncio
import os
import sys
from unittest.mock import MagicMock
from urllib.parse import urlparse

# Añadir el path del backend para poder importar app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

import logging

logging.basicConfig(level=logging.INFO)
from app.core.config import settings
from app.services.pipeline_service import PipelineService


def _normalize_host(hostname) -> str:
    return (hostname or "").strip().lower().rstrip(".")


async def test_manual_pipeline():
    print("Testing Pipeline Filtering Logic...")

    # Mock search items
    mock_search_items = [
        {
            "link": "https://www.facebook.com/competitor",
            "title": "Competitor on Facebook",
        },
        {"link": "https://www.competitor1.com/", "title": "Real Competitor 1"},
        {"link": "https://blog.competitor1.com/", "title": "Blog of Competitor 1"},
        {
            "link": "https://www.competitor2.com/services",
            "title": "Real Competitor 2 Services",
        },
        {
            "link": "https://www.top10reviews.com/best-coding-bootcamps",
            "title": "Top 10 Reviews",
        },
        {"link": "https://www.competitor3.com/", "title": "Real Competitor 3"},
        {"link": "https://www.reddit.com/r/coding", "title": "Reddit Thread"},
    ]

    ps = PipelineService()
    filtered = ps.filter_competitor_urls(mock_search_items, "mycompany.com")

    print(f"Filtered URLs: {filtered}")

    filtered_hosts = {_normalize_host(urlparse(url).hostname) for url in filtered}
    expected_hosts = {"www.competitor1.com", "www.competitor2.com", "www.competitor3.com"}
    missing_hosts = expected_hosts - filtered_hosts
    assert not missing_hosts
    assert len(filtered) == 3

    print("Filter Test Passed!")

    # Test Agent 1 call (if possible)
    # We won't call the actual LLM here to save costs, but we can see if logs are present in the code.


if __name__ == "__main__":
    asyncio.run(test_manual_pipeline())
