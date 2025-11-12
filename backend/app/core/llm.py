"""
LLM related functions
"""
from ..core.config import settings
from ..core.logger import get_logger
import google.generativeai as genai

logger = get_logger(__name__)


# Configurar LLM disponibles
def get_llm_function():
    """
    Retorna una función que ejecuta prompts con el LLM disponible.
    Prioridad: Gemini > OpenAI > Fallback
    """
    if settings.GEMINI_API_KEY:
        genai.configure(api_key=settings.GEMINI_API_KEY)

        async def gemini_function(system_prompt: str, user_prompt: str) -> str:
            try:
                model = genai.GenerativeModel(settings.GEMINI_MODEL)
                response = model.generate_content(
                    f"{system_prompt}\n\n{user_prompt}",
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.7,
                        max_output_tokens=8000,
                    ),
                )
                return response.text
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
