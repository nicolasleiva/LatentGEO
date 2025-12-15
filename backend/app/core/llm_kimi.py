"""
LLM Service - Abstracción para múltiples providers
"""
from openai import OpenAI
from ..core.config import settings
from ..core.logger import get_logger

logger = get_logger(__name__)


def get_llm_function():
    """
    Retorna función que ejecuta prompts con KIMI K2 Thinking (NVIDIA NIM)
    Usa el modelo configurado en settings para análisis y reportes
    """
    api_key = settings.NV_API_KEY_ANALYSIS or settings.NVIDIA_API_KEY or settings.NV_API_KEY
    
    if api_key:
        async def kimi_function(system_prompt: str, user_prompt: str) -> str:
            try:
                client = OpenAI(
                    base_url=settings.NV_BASE_URL,
                    api_key=api_key
                )
                
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
                
                # Usar KIMI K2 Thinking para análisis (mejor razonamiento)
                completion = client.chat.completions.create(
                    model=settings.NV_MODEL_ANALYSIS,  # moonshotai/kimi-k2-thinking
                    messages=messages,
                    temperature=1,  # Recomendado para kimi-k2-thinking
                    top_p=0.9,
                    max_tokens=settings.NV_MAX_TOKENS,  # 16384
                    stream=False
                )
                
                return completion.choices[0].message.content.strip()
            except Exception as e:
                logger.error(f"Error with KIMI K2 Thinking: {e}")
                raise

        return kimi_function
    
    # GEMINI FALLBACK (comentado pero disponible)
    # elif settings.GEMINI_API_KEY:
    #     from google import genai
    #     async def gemini_function(system_prompt: str, user_prompt: str) -> str:
    #         try:
    #             client = genai.Client(api_key=settings.GEMINI_API_KEY)
    #             prompt_text = system_prompt.strip() + "\n\nJSON de entrada:\n" + user_prompt.strip()
    #             
    #             response = client.models.generate_content(
    #                 model=settings.GEMINI_MODEL,
    #                 contents=prompt_text
    #             )
    #             return response.text.strip()
    #         except Exception as e:
    #             logger.error(f"Error with Gemini: {e}")
    #             raise
    #     return gemini_function
    
    else:
        logger.warning("No LLM API key configured. Using fallback.")
        async def fallback_function(system_prompt: str, user_prompt: str) -> str:
            return "No LLM available - fallback response"
        return fallback_function
