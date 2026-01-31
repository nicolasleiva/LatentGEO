from openai import AsyncOpenAI
import logging
import json
from app.core.config import settings

logger = logging.getLogger(__name__)

async def call_kimi_api(name: str, system_prompt: str, user_message: str) -> str:
    """
    Calls the Kimi API with the given system prompt and user message.
    """
    api_key = settings.NV_API_KEY_ANALYSIS or settings.NVIDIA_API_KEY or settings.NV_API_KEY
    
    if not api_key:
        logger.error("NVIDIA API key no está configurada. No se puede llamar a KIMI.")
        return "Error: API key no configurada."

    try:
        client = AsyncOpenAI(
            base_url=settings.NV_BASE_URL,
            api_key=api_key,
            timeout=300.0
        )

        logger.info(f"Calling KIMI API for {name} with model {settings.NV_MODEL_ANALYSIS}")
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        completion = await client.chat.completions.create(
            model=settings.NV_MODEL_ANALYSIS,
            messages=messages,
            temperature=0.6,
            top_p=0.9,
            max_tokens=settings.NV_MAX_TOKENS,
            stream=False
        )
        
        content = completion.choices[0].message.content
        logger.info(f"KIMI API call for {name} successful.")
        return content.strip() if content else ""

    except Exception as e:
        logger.exception(f"Error al llamar a la API de KIMI para {name}: {e}")
        return f"Error al llamar a la API de KIMI: {str(e)}"

# Mantener compatibilidad temporal si es necesario
async def call_gemini_api(name: str, system_prompt: str, user_message: str) -> str:
    logger.warning(f"call_gemini_api called for {name}, but Gemini is disabled. Using KIMI instead.")
    return await call_kimi_api(name, system_prompt, user_message)
