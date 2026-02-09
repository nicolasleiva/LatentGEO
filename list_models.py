
import os
import asyncio
import aiohttp
from dotenv import load_dotenv

load_dotenv()

async def list_models():
    api_key = os.getenv("NV_API_KEY_ANALYSIS") or os.getenv("NVIDIA_API_KEY")
    base_url = "https://integrate.api.nvidia.com/v1"
    
    if not api_key:
        print("Error: No API key found")
        return

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{base_url}/models", headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    models = [m['id'] for m in data.get('data', [])]
                    print("Available models:")
                    for m in sorted(models):
                        if "kimi" in m.lower():
                            print(f"- {m}")
                        elif "moonshot" in m.lower():
                            print(f"- {m}")
                    
                    if not any("kimi" in m.lower() or "moonshot" in m.lower() for m in models):
                        print("No Kimi/Moonshot models found. First 5 models:")
                        for m in models[:5]:
                            print(f"- {m}")
                else:
                    print(f"Error: {resp.status} - {await resp.text()}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(list_models())
