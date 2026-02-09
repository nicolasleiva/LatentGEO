
import os
import pytest
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

@pytest.mark.asyncio
async def test_kimi_integration():
    api_key = os.getenv("NV_API_KEY_ANALYSIS") or os.getenv("NVIDIA_API_KEY")
    base_url = "https://integrate.api.nvidia.com/v1"
    model = "moonshotai/kimi-k2-instruct-0905"

    if not api_key:
        pytest.skip("NV API key not configured — skipping KIMI integration test")

    client = AsyncOpenAI(base_url=base_url, api_key=api_key)

    try:
        completion = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say hello!"}
            ],
            temperature=0.5,
            top_p=1,
            max_tokens=100,
        )
    except Exception as e:
        pytest.skip(f"KIMI API error or timeout: {e}")

    result = completion.choices[0].message.content
    assert result is not None and result.strip(), "Empty response from KIMI model"
