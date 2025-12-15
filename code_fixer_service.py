from app.core.llm_client import call_gemini_api
from app.core.logger import get_logger
from typing import Dict, Any, Optional

logger = get_logger(__name__)

class CodeFixerService:

    @staticmethod
    async def generate_fixed_code(
        original_code: str,
        file_path: str,
        audit_context: Dict[str, Any]
    ) -> Optional[str]:
        """
        Usa un LLM para generar el código corregido basado en el contexto de la auditoría.
        """
        
        # Simplificamos el fix_plan para que sea más fácil de procesar por el LLM
        simplified_plan = [
            f"- {item['priority']}: {item['description']}" for item in audit_context.get("fix_plan", [])
        ]
        
        system_prompt = f"""
Eres un experto desarrollador de software especializado en SEO técnico y optimización web.
Tu tarea es corregir el siguiente archivo de código basado en un plan de corrección de una auditoría SEO.

**Instrucciones:**
1.  Analiza el 'Plan de Corrección' y el 'Código Original'.
2.  Aplica las correcciones directamente en el código.
3.  **Responde ÚNICAMENTE con el código completo y corregido del archivo.** No incluyas explicaciones, comentarios adicionales, ni uses bloques de código markdown (```). Tu salida debe ser el contenido puro del archivo.
4.  Si el plan de corrección no aplica a este archivo, devuelve el código original sin cambios.
"""
        
        user_prompt = f"""
**Plan de Corrección:**
{chr(10).join(simplified_plan)}

**Ruta del Archivo:** {file_path}

**Código Original:**
{original_code}
"""
        try:
            fixed_code = await call_gemini_api(system_prompt, user_prompt)
            return fixed_code
        except Exception as e:
            logger.error(f"Error generating fixed code for {file_path}: {e}")
            return None