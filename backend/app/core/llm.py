"""
LLM related functions
"""
from ..core.config import settings
from ..core.logger import get_logger
from google import genai

logger = get_logger(__name__)


# Configurar LLM disponibles
def get_llm_function():
    """
    Retorna una función que ejecuta prompts con el LLM disponible.
    Prioridad: Gemini > OpenAI > Fallback
    """
    if settings.GEMINI_API_KEY:
        async def gemini_function(system_prompt: str, user_prompt: str) -> str:
            try:
                client = genai.Client(api_key=settings.GEMINI_API_KEY)
                prompt_text = system_prompt.strip() + "\n\nJSON de entrada:\n" + user_prompt.strip()
                
                response = client.models.generate_content(
                    model=settings.GEMINI_MODEL,
                    contents=prompt_text
                )
                return response.text.strip()
            except Exception as e:
                logger.error(f"Error with Gemini: {e}")
                raise

        return gemini_function
    else:
        logger.warning("No LLM API key configured. Using fallback.")

        async def fallback_function(system_prompt: str, user_prompt: str) -> str:
            # Fallback: retorna un análisis simple sin LLM
            return "No LLM available - fallback response"

        return fallback_function
