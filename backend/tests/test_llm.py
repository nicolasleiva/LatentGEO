#!/usr/bin/env python3
"""
Pruebas para el LLM KIMI. Estas pruebas son de integración y se saltan si
no hay credenciales configuradas en el entorno.
"""
import os

import pytest
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
STRICT_TEST_MODE = os.getenv("STRICT_TEST_MODE") == "1"


@pytest.mark.integration
@pytest.mark.live
def test_kimi_integration():
    NVIDIA_API_KEY = (
        os.getenv("NV_API_KEY_ANALYSIS")
        or os.getenv("NVIDIA_API_KEY")
        or os.getenv("NV_API_KEY")
    )
    KIMI_MODEL = os.getenv("NV_MODEL_ANALYSIS", "moonshotai/kimi-k2-instruct-0905")

    if not NVIDIA_API_KEY:
        if STRICT_TEST_MODE:
            pytest.fail("NV API key not configured in strict mode.")
        pytest.skip("NV API key not configured — skipping KIMI integration test")

    client = OpenAI(
        base_url="https://integrate.api.nvidia.com/v1", api_key=NVIDIA_API_KEY
    )
    test_prompt = "Responde con un JSON que diga {'status': 'ok'}"

    try:
        completion = client.chat.completions.create(
            model=KIMI_MODEL,
            messages=[{"role": "user", "content": test_prompt}],
            temperature=0.6,
            top_p=0.9,
            max_tokens=100,
            stream=False,
        )
    except Exception as e:
        if STRICT_TEST_MODE:
            pytest.fail(f"KIMI API error or timeout in strict mode: {e}")
        pytest.skip(f"KIMI API error or timeout: {e}")

    result = completion.choices[0].message.content.strip().lower()
    assert "ok" in result, f"Respuesta inesperada del modelo: {result}"
