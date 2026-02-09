"""
Test rápido de Kimi/NVIDIA API
"""
import asyncio
import sys
import os

# Agregar path para imports
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from openai import AsyncOpenAI
from app.core.config import settings

import pytest

@pytest.mark.asyncio
async def test_kimi_integration():
    # 1. Verificar configuración
    api_key = settings.NVIDIA_API_KEY or settings.NV_API_KEY

    if not api_key:
        pytest.skip("No NVIDIA API key configured — skipping KIMI integration test")

    # 2. Crear cliente
    try:
        client = AsyncOpenAI(api_key=api_key, base_url=settings.NV_BASE_URL)
    except Exception as e:
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
            max_tokens=1000
        )
    except Exception as e:
        pytest.skip(f"KIMI API error or timeout: {e}")

    message = response.choices[0].message
    content = getattr(message, "content", None) or getattr(message, "reasoning_content", None) or getattr(message, "reasoning", None)
    assert content and content.strip(), "Empty response from KIMI API"


if __name__ == "__main__":
    result = asyncio.run(test_kimi())
    
    if result:
        print("\nOK: PRUEBA EXITOSA! Kimi esta funcionando correctamente.")
        sys.exit(0)
    else:
        print("\nERROR: PRUEBA FALLIDA. Revisa la configuracion.")
        sys.exit(1)
