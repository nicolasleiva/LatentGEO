"""
Test standalone para verificar APIs reales.
Este script no requiere la base de datos.
"""

import asyncio
import os
import sys

# Añadir backend al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Cargar .env desde la raiz del proyecto ANTES de importar config
from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
if os.path.exists(env_path):
    print(f"Cargando .env desde: {env_path}")
    load_dotenv(env_path, override=True)
else:
    print(f"[ADVERTENCIA] No se encontro .env en: {env_path}")

# Configurar variables de entorno antes de importar app
os.environ["DATABASE_URL"] = os.getenv("DATABASE_URL", "sqlite:///./test.db")
os.environ["ENVIRONMENT"] = os.getenv("ENVIRONMENT", "test")

from app.core.config import settings


async def test_pagespeed_api():
    """Test PageSpeed API real"""
    from app.services.pagespeed_service import PageSpeedService

    print("\n" + "=" * 60)
    print("TEST: PageSpeed API")
    print("=" * 60)

    # Verificar API key
    if not settings.GOOGLE_PAGESPEED_API_KEY:
        print("[FAIL] GOOGLE_PAGESPEED_API_KEY no está configurada")
        print(f"   Valor actual: {settings.GOOGLE_PAGESPEED_API_KEY}")
        return False

    print(f"[OK] API Key configurada: {settings.GOOGLE_PAGESPEED_API_KEY[:25]}...")

    # Test API real
    try:
        url = "https://www.google.com"
        print(f"\nLlamando a PageSpeed API para: {url}")

        result = await PageSpeedService.analyze_url(
            url=url, api_key=settings.GOOGLE_PAGESPEED_API_KEY, strategy="mobile"
        )

        if "error" in result:
            print(f"[FAIL] Error en respuesta: {result['error']}")
            return False

        print("[OK] Respuesta recibida")
        print(f"  - URL: {result.get('url')}")
        print(f"  - Performance Score: {result.get('performance_score')}")
        print(f"  - Accessibility Score: {result.get('accessibility_score')}")
        print(f"  - SEO Score: {result.get('seo_score')}")
        print(f"  - Best Practices Score: {result.get('best_practices_score')}")
        print(f"  - Core Web Vitals: {result.get('core_web_vitals', {})}")

        # Verificar estructura
        required_fields = [
            "performance_score",
            "accessibility_score",
            "seo_score",
            "best_practices_score",
            "core_web_vitals",
        ]
        for field in required_fields:
            if field not in result:
                print(f"[FAIL] Falta campo: {field}")
                return False

        print("\n[PASS] PageSpeed API funciona correctamente")
        return True

    except Exception as e:
        print(f"[FAIL] Error: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_nvidia_api():
    """Test NVIDIA API para keywords"""
    print("\n" + "=" * 60)
    print("TEST: NVIDIA/Kimi API")
    print("=" * 60)

    api_key = settings.NVIDIA_API_KEY or settings.NV_API_KEY

    if not api_key:
        print("[FAIL] NVIDIA_API_KEY no está configurada")
        print(f"   NVIDIA_API_KEY: {settings.NVIDIA_API_KEY}")
        print(f"   NV_API_KEY: {settings.NV_API_KEY}")
        return False

    print(f"[OK] API Key configurada: {api_key[:25]}...")

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=api_key, base_url=settings.NV_BASE_URL)

        print("\nLlamando a NVIDIA API...")
        response = await client.chat.completions.create(
            model=settings.NV_MODEL,
            messages=[{"role": "user", "content": "Say 'API test successful'"}],
            temperature=0.0,
            max_tokens=50,
        )

        content = response.choices[0].message.content
        print(f"[OK] Respuesta recibida: {content}")

        print("\n[PASS] NVIDIA API funciona correctamente")
        return True

    except Exception as e:
        print(f"[FAIL] Error: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_keyword_service():
    """Test Keyword Service con API real"""
    print("\n" + "=" * 60)
    print("TEST: Keyword Service")
    print("=" * 60)

    from app.models import Base
    from app.services.keyword_service import KeywordService
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    # Crear DB en memoria
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        service = KeywordService(db)

        if not service.client:
            print("[FAIL] KeywordService no tiene cliente NVIDIA configurado")
            return False

        print("[OK] KeywordService inicializado con API NVIDIA")

        # Test generación de keywords
        print("\nGenerando keywords para 'google.com'...")
        result = await service.research_keywords(
            audit_id=999,  # ID ficticio para test
            domain="google.com",
            seed_keywords=["search", "technology"],
        )

        print(f"[OK] Recibidas {len(result)} keywords")

        if result:
            print("\nPrimeras 5 keywords:")
            for i, kw in enumerate(result[:5], 1):
                print(
                    f"  {i}. {kw.term} (vol: {kw.volume}, diff: {kw.difficulty}, intent: {kw.intent})"
                )

        print("\n[PASS] Keyword Service funciona correctamente")
        return True

    except Exception as e:
        print(f"[FAIL] Error: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        db.close()


def verify_env_variables():
    """Verifica que todas las variables de entorno están configuradas"""
    print("\n" + "=" * 60)
    print("VERIFICACIÓN DE VARIABLES DE ENTORNO")
    print("=" * 60)

    vars_to_check = [
        ("GOOGLE_PAGESPEED_API_KEY", settings.GOOGLE_PAGESPEED_API_KEY),
        ("GOOGLE_API_KEY", settings.GOOGLE_API_KEY),
        ("CSE_ID", settings.CSE_ID),
        ("NVIDIA_API_KEY", settings.NVIDIA_API_KEY),
        ("NV_API_KEY", settings.NV_API_KEY),
    ]

    all_ok = True
    for name, value in vars_to_check:
        if value:
            masked = value[:20] + "..." if len(value) > 20 else value
            print(f"[OK] {name}: {masked}")
        else:
            print(f"[FAIL] {name}: NO CONFIGURADO")
            all_ok = False

    return all_ok


async def main():
    """Ejecuta todos los tests"""
    print("\n" + "=" * 60)
    print("TEST DE SERVICIOS GEO CON APIs REALES")
    print("=" * 60)

    # Verificar variables
    env_ok = verify_env_variables()

    if not env_ok:
        print("\n[WARN]  Algunas variables no están configuradas")
        print("   Revisando archivo .env...")

        # Intentar cargar manualmente
        env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
        if os.path.exists(env_path):
            print(f"   Archivo .env encontrado en: {env_path}")
            with open(env_path) as f:
                lines = f.readlines()
                print(f"   Contiene {len(lines)} líneas")
        else:
            print(f"   [FAIL] No se encontró archivo .env en: {env_path}")

    results = []

    # Test PageSpeed
    results.append(("PageSpeed", await test_pagespeed_api()))

    # Test NVIDIA
    results.append(("NVIDIA", await test_nvidia_api()))

    # Test Keyword Service
    results.append(("Keyword Service", await test_keyword_service()))

    # Resumen
    print("\n" + "=" * 60)
    print("RESUMEN DE TESTS")
    print("=" * 60)

    for name, passed in results:
        status = "[PASS] PASS" if passed else "[FAIL] FAIL"
        print(f"{status}: {name}")

    total = len(results)
    passed = sum(1 for _, p in results if p)

    print(f"\nTotal: {passed}/{total} tests pasaron")

    if passed == total:
        print("\n🎉 Todos los servicios funcionan correctamente!")
    else:
        print("\n[WARN]  Algunos servicios fallaron. Revisa los errores arriba.")

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
