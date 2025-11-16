#!/usr/bin/env python3
"""
Script de prueba (CORREGIDO) para verificar que el LLM funciona correctamente
"""
import os
import google.generativeai as genai  # <--- Importación estándar
from dotenv import load_dotenv
import traceback

load_dotenv()

def test_gemini():  # <--- 1. Eliminado 'async'
    """Prueba la conexión con Gemini"""
    try:
        GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
        # Usamos el modelo que definiste, quitando el prefijo 'models/'
        # La biblioteca moderna lo añade automáticamente.
        model_name_env = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite") # Ajustado a un modelo estándar
    
        if not GEMINI_API_KEY:
            print("❌ GEMINI_API_KEY no está configurada")
            return False
        
        print(f"✅ GEMINI_API_KEY encontrada")
        print(f"📦 Modelo (según .env): {model_name_env}")
        
        # --- INICIO DE CORRECCIÓN PRINCIPAL ---
        
        # 2. Configurar la API key globalmente
        genai.configure(api_key=GEMINI_API_KEY)
        print("✅ Cliente Gemini configurado")
        
        # 3. Crear una instancia del modelo
        model = genai.GenerativeModel(model_name_env)
        print(f"✅ Modelo {model_name_env} cargado")
        
        # --- FIN DE CORRECCIÓN PRINCIPAL ---
        
        # Preparar prompt de prueba (el tuyo está perfecto)
        test_prompt = """Eres un asistente útil. Responde en formato JSON.

JSON de entrada:
{"test": "Hola, ¿funciona el LLM?"}

Responde con: {"status": "ok", "message": "Sí, funciono correctamente"}"""
        
        print(f"🚀 Enviando prueba al modelo...")
        
        # 4. Generar contenido (forma síncrona simple)
        response = model.generate_content(test_prompt)
        
        # 5. Extraer texto (forma simple)
        result = response.text.strip()
        
        print(f"✅ Respuesta recibida:")
        print(f"{'='*60}")
        print(result)
        print(f"{'='*60}")
        
        # Pequeña validación
        if '"status": "ok"' in result:
            return True
        else:
            print("⚠️ La respuesta no fue el JSON esperado.")
            return False
        
    except ImportError as e:
        print(f"❌ Error de importación: {e}")
        print("💡 Instala: pip install google-generativeai")
        return False
    except Exception as e:
        print(f"❌ Error durante la ejecución:")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🧪 Probando conexión con Gemini LLM...")
    print("="*60)
    
    # 6. Llamada síncrona normal
    success = test_gemini() 
    
    print("="*60)
    if success:
        print("✅ ¡Prueba exitosa! El LLM funciona correctamente.")
    else:
        print("❌ La prueba falló. Revisa los errores arriba.")