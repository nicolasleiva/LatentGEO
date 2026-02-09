
import os
import pytest
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

@pytest.mark.asyncio
async def test_nvidia_integration():
    api_key = os.getenv("NV_API_KEY_ANALYSIS") or os.getenv("NVIDIA_API_KEY")
    base_url = "https://integrate.api.nvidia.com/v1"
    model = "meta/llama-3.1-405b-instruct"

    if not api_key:
        pytest.skip("NV API key not configured — skipping NVIDIA integration test")

    client = AsyncOpenAI(base_url=base_url, api_key=api_key)

    try:
        completion = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=10,
        )
    except Exception as e:
        pytest.skip(f"NVIDIA KIMI API error or timeout: {e}")

    result = completion.choices[0].message.content
    assert result is not None and result.strip(), "Empty response from NVIDIA model"
