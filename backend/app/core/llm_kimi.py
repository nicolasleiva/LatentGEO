"""
LLM Service - Abstracción para múltiples providers
"""
from openai import OpenAI
from ..core.config import settings
from ..core.logger import get_logger

logger = get_logger(__name__)


def get_llm_function():
    """
    Retorna función que ejecuta prompts con KIMI (NVIDIA NIM)
    Gemini queda comentado como fallback
    """
    if settings.NVIDIA_API_KEY:
        async def kimi_function(system_prompt: str, user_prompt: str) -> str:
            try:
                client = OpenAI(
                    base_url="https://integrate.api.nvidia.com/v1",
                    api_key=settings.NVIDIA_API_KEY
                )
                
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
                
                completion = client.chat.completions.create(
                    model="moonshotai/kimi-k2-instruct-0905",
                    messages=messages,
                    temperature=0,
                    top_p=0.9,
                    max_tokens=40096,
                    stream=False
                )
                
                return completion.choices[0].message.content.strip()
            except Exception as e:
                logger.error(f"Error with KIMI: {e}")
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
