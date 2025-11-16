from google import genai
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

async def call_gemini_api(name: str, system_prompt: str, user_message: str) -> str:
    """
    Calls the Gemini API with the given system prompt and user message.

    Args:
        name: A name for the agent/call (for logging purposes).
        system_prompt: The system-level instructions for the LLM.
        user_message: The user's input/message for the LLM.

    Returns:
        The generated text response from the LLM.
    """
    if not settings.GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY no está configurada. No se puede llamar a la API de Gemini.")
        return "Error: GEMINI_API_KEY no configurada."

    try:
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        full_message = f"{system_prompt}\n\n{user_message}"

        logger.info(f"Calling Gemini API for {name} with model {settings.GEMINI_MODEL}")
        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=full_message
        )
        
        logger.info(f"Gemini API call for {name} successful.")
        return response.text.strip()

    except Exception as e:
        logger.exception(f"Error al llamar a la API de Gemini para {name}: {e}")
        return f"Error al llamar a la API de Gemini: {str(e)}"
