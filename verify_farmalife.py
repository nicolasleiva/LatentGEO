
import asyncio
import os
import sys
from unittest.mock import MagicMock

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

async def test_pagespeed():
    from app.services.pagespeed_service import PageSpeedService
    from app.core.config import settings
    
    url = "https://www.farmalife.com.ar/"
    print(f"Testing PageSpeed for {url}...")
    try:
        data = await PageSpeedService.analyze_both_strategies(url, settings.GOOGLE_PAGESPEED_API_KEY)
        print(f"SUCCESS! Got data for strategies: {list(data.keys())}")
        for strategy in data:
            if data[strategy]:
                print(f"{strategy.capitalize()} Score: {data[strategy].get('performance_score')}")
                print(f"{strategy.capitalize()} Vitals: {data[strategy].get('core_web_vitals')}")
            else:
                print(f"{strategy.capitalize()} DATA IS EMPTY/NONE")
    except Exception as e:
        print(f"FAILED: {e}")

if __name__ == "__main__":
    asyncio.run(test_pagespeed())
