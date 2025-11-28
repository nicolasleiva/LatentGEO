"""
Test rápido de Kimi/NVIDIA API
"""
import asyncio
import sys
import os

# Agregar path para imports
sys.path.insert(0, '/app')

from openai import AsyncOpenAI
from app.core.config import settings

async def test_kimi():
    print("🧪 Iniciando prueba de Kimi/NVIDIA API...\n")
    
    # 1. Verificar configuración
    api_key = settings.NVIDIA_API_KEY or settings.NV_API_KEY
    print(f"✅ API Key configurada: {'Sí' if api_key else 'No'}")
    print(f"✅ Base URL: {settings.NV_BASE_URL}")
    print(f"✅ Modelo: {settings.NV_MODEL}")
    print(f"✅ Max Tokens: {settings.NV_MAX_TOKENS}\n")
    
    if not api_key:
        print("❌ ERROR: No se encontró NVIDIA_API_KEY en el .env")
        return False
    
    # 2. Crear cliente
    try:
        client = AsyncOpenAI(
            api_key=api_key,
            base_url=settings.NV_BASE_URL
        )
        print("✅ Cliente de Kimi creado correctamente\n")
    except Exception as e:
        print(f"❌ Error creando cliente: {e}")
        return False
    
    # 3. Hacer prueba simple
    print("🚀 Enviando prompt de prueba a Kimi...\n")
    
    prompt = """
    Eres un experto en SEO y GEO (Generative Engine Optimization).
    
    Genera 3 sugerencias breves para optimizar un blog sobre "inteligencia artificial" 
    para que sea citado por ChatGPT y otros LLMs.
    
    Responde en formato JSON con esta estructura:
    {
        "suggestions": [
            {
                "title": "Título de la sugerencia",
                "description": "Descripción breve",
                "priority": "high"
            }
        ]
    }
    
    Responde únicamente con el JSON, sin texto adicional.
    """
    
    try:
        response = await client.chat.completions.create(
            model=settings.NV_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1000
        )
        
        content = response.choices[0].message.content
        
        print("=" * 60)
        print("✅ ¡Respuesta recibida de Kimi!")
        print("=" * 60)
        print(content)
        print("=" * 60)
        print(f"\n📊 Tokens usados: {response.usage.total_tokens}")
        print(f"⏱️  Modelo: {response.model}")
        print(f"🎯 Finish reason: {response.choices[0].finish_reason}\n")
        
        return True
        
    except Exception as e:
        print(f"❌ Error al llamar a Kimi API: {e}")
        print(f"   Tipo de error: {type(e).__name__}")
        return False

if __name__ == "__main__":
    result = asyncio.run(test_kimi())
    
    if result:
        print("\n✅ ¡PRUEBA EXITOSA! Kimi está funcionando correctamente.")
        sys.exit(0)
    else:
        print("\n❌ PRUEBA FALLIDA. Revisa la configuración.")
        sys.exit(1)
