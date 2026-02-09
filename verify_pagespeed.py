
import asyncio
import os
import sys
from unittest.mock import MagicMock

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

async def test_pagespeed():
    from app.services.pagespeed_service import PageSpeedService
    from app.core.config import settings
    
    # We can't easily read .env, but we can see settings
    print(f"ENABLE_PAGESPEED: {settings.ENABLE_PAGESPEED}")
    print(f"PAGESPEED API KEY exists: {bool(settings.GOOGLE_PAGESPEED_API_KEY)}")
    
    url = "https://www.google.com"
    if not settings.GOOGLE_PAGESPEED_API_KEY:
        print("SKIP: No API key found in current environment.")
        return

    print(f"Testing PageSpeed for {url}...")
    try:
        data = await PageSpeedService.analyze_both_strategies(url, settings.GOOGLE_PAGESPEED_API_KEY)
        print(f"SUCCESS! Got data for strategies: {list(data.keys())}")
        if "mobile" in data:
            print(f"Mobile Score: {data['mobile'].get('performance_score')}")
    except Exception as e:
        print(f"FAILED: {e}")

if __name__ == "__main__":
    asyncio.run(test_pagespeed())
