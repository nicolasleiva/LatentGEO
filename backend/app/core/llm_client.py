import google.generativeai as genai
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
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(settings.GEMINI_MODEL)

        # Combine system prompt and user message for the model
        # Gemini API often handles system prompts as part of the initial message or context
        # For simplicity, we'll prepend the system prompt to the user message.
        full_message = f"{system_prompt}\n\n{user_message}"

        logger.info(f"Calling Gemini API for {name} with model {settings.GEMINI_MODEL}")
        response = await model.generate_content_async(full_message)
        
        if response.text:
            logger.info(f"Gemini API call for {name} successful.")
            return response.text
        else:
            logger.warning(f"Gemini API call for {name} returned no text. Prompt: {full_message[:100]}...")
            return "Error: No se obtuvo respuesta de texto del LLM."

    except Exception as e:
        logger.exception(f"Error al llamar a la API de Gemini para {name}: {e}")
        return f"Error al llamar a la API de Gemini: {str(e)}"
