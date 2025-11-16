#!/usr/bin/env python3
"""Test directo de PageSpeed API"""
import asyncio
import sys
sys.path.insert(0, 'backend')

from app.services.pagespeed_service import PageSpeedService
from app.core.config import settings

async def test():
    print("Testing PageSpeed API...")
    print(f"API Key: {settings.GOOGLE_PAGESPEED_API_KEY[:10]}...{settings.GOOGLE_PAGESPEED_API_KEY[-4:]}")
    print(f"URL: https://codegpt.co/\n")
    
    result = await PageSpeedService.analyze_url(
        "https://codegpt.co/",
        settings.GOOGLE_PAGESPEED_API_KEY,
        "mobile"
    )
    
    if "error" in result:
        print(f"[X] ERROR: {result['error']}")
    else:
        print(f"[OK] Performance Score: {result.get('performance_score')}")
        print(f"[OK] LCP: {result.get('core_web_vitals', {}).get('lcp')}ms")
        print(f"[OK] Keys: {list(result.keys())}")

if __name__ == "__main__":
    asyncio.run(test())
