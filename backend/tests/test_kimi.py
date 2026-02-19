"""
Test rápido de Kimi/NVIDIA API
"""
import os

import pytest
from app.core.config import settings
from openai import AsyncOpenAI

STRICT_TEST_MODE = os.getenv("STRICT_TEST_MODE") == "1"


@pytest.mark.integration
@pytest.mark.live
@pytest.mark.asyncio
async def test_kimi_integration():
    # 1. Verificar configuración
    api_key = settings.NVIDIA_API_KEY or settings.NV_API_KEY

    if not api_key:
        if STRICT_TEST_MODE:
            pytest.fail("No NVIDIA API key configured in strict mode.")
        pytest.skip("No NVIDIA API key configured — skipping KIMI integration test")

    # 2. Crear cliente
    try:
        client = AsyncOpenAI(api_key=api_key, base_url=settings.NV_BASE_URL)
    except Exception as e:
        if STRICT_TEST_MODE:
            pytest.fail(f"Could not construct KIMI client in strict mode: {e}")
        pytest.skip(f"Could not construct KIMI client: {e}")

    # 3. Hacer prueba simple
    prompt = """
    Eres un experto en SEO y GEO (Generative Engine Optimization).

    Genera 3 sugerencias breves para optimizar un blog sobre "inteligencia artificial" 
    para que sea citado por ChatGPT y otros LLMs.

    Responde en formato JSON con esta estructura:
    {
        "suggestions": [
            {
                "title": "Título de la sugerencia",
                "description": "Descripción breve",
                "priority": "high"
            }
        ]
    }

    Responde únicamente con el JSON, sin texto adicional.
    """

    try:
        response = await client.chat.completions.create(
            model=settings.NV_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=1000,
        )
    except Exception as e:
        if STRICT_TEST_MODE:
            pytest.fail(f"KIMI API error or timeout in strict mode: {e}")
        pytest.skip(f"KIMI API error or timeout: {e}")

    message = response.choices[0].message
    content = (
        getattr(message, "content", None)
        or getattr(message, "reasoning_content", None)
        or getattr(message, "reasoning", None)
    )
    assert content and content.strip(), "Empty response from KIMI API"
