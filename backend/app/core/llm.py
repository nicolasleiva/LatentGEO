"""
LLM related functions - Redirigido a KIMI
"""

from ..core.llm_kimi import get_llm_function as kimi_get_llm_function
from ..core.logger import get_logger

logger = get_logger(__name__)


# Configurar LLM disponibles (Exclusivo KIMI)
def get_llm_function_proxy():
    """
    Retorna la función que ejecuta prompts con KIMI.
    """
    return kimi_get_llm_function()


# Mantener compatibilidad con importaciones existentes
get_llm_function = get_llm_function_proxy
