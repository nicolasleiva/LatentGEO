"""
LLM Service - Abstracción para KIMI K2 (NVIDIA NIM)
Exclusivo para el proyecto según requerimientos.
"""
from openai import AsyncOpenAI
from ..core.config import settings
from ..core.logger import get_logger

logger = get_logger(__name__)

async def kimi_function(system_prompt: str, user_prompt: str, max_tokens: int | None = None) -> str:
    """
    Ejecuta prompts con KIMI K2 Thinking (NVIDIA NIM)
    Usa el modelo configurado en settings para análisis y reportes
    """
    api_key = settings.NV_API_KEY_ANALYSIS or settings.NVIDIA_API_KEY or settings.NV_API_KEY
    
    if not api_key:
        logger.error("No NVIDIA API key configured for KIMI")
        return "Error: No LLM API key configured."

    client = None
    try:
        # Use AsyncOpenAI for non-blocking I/O
        client = AsyncOpenAI(
            base_url=settings.NV_BASE_URL,
            api_key=api_key,
            timeout=300.0,
            max_retries=2
        )
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        # Usar KIMI K2 Standard para análisis
        max_tokens_value = max_tokens or settings.NV_MAX_TOKENS
        logger.info(
            f"Llamando a KIMI (Modelo: {settings.NV_MODEL_ANALYSIS}). Max tokens: {max_tokens_value}"
        )
        completion = await client.chat.completions.create(
            model=settings.NV_MODEL_ANALYSIS,  # moonshotai/kimi-k2.5
            messages=messages,
            temperature=0.0,
            top_p=1.0,
            max_tokens=max_tokens_value,
            stream=False
        )
        
        content = completion.choices[0].message.content
        if not content:
            raise ValueError("Empty response from LLM")
        return content.strip()
        
    except Exception as e:
        logger.error(f"Error with KIMI: {e}")
        raise e
    finally:
        if client is not None:
            try:
                await client.close()
            except RuntimeError as close_err:
                # Avoid crashing on shutdown when the event loop is already closed
                if "Event loop is closed" not in str(close_err):
                    logger.warning(f"Error closing KIMI client: {close_err}")

def get_llm_function():
    """
    Retorna la función principal de LLM (KIMI)
    """
    return kimi_function
