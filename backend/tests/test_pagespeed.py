import asyncio
import sys
sys.path.insert(0, 'backend')

from backend.app.services.pagespeed_service import PageSpeedService

async def test():
    API_KEY = "AIzaSyCOj-uXcsYu94q-HY3SynXgevgLWlEuYD4"
    URL = "https://www.codegpt.co/"
    
    print(f"Testing PageSpeed for: {URL}")
    print("=" * 50)
    
    print("\n[1/2] Analyzing MOBILE...")
    mobile = await PageSpeedService.analyze_url(URL, API_KEY, "mobile")
    print(f"Mobile Performance: {mobile.get('performance_score')}")
    print(f"Mobile LCP: {mobile.get('core_web_vitals', {}).get('lcp')} ms")
    
    print("\n[2/2] Analyzing DESKTOP...")
    await asyncio.sleep(3)
    desktop = await PageSpeedService.analyze_url(URL, API_KEY, "desktop")
    print(f"Desktop Performance: {desktop.get('performance_score')}")
    print(f"Desktop LCP: {desktop.get('core_web_vitals', {}).get('lcp')} ms")
    
    print("\n" + "=" * 50)
    print("✓ Test completed!")

if __name__ == "__main__":
    asyncio.run(test())
