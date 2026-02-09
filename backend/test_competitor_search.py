#!/usr/bin/env python3
"""
Test simple para verificar la búsqueda de competidores
"""

import sys
import os
import asyncio

# Load .env from parent directory
from dotenv import load_dotenv

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
env_path = os.path.join(parent_dir, ".env")
load_dotenv(env_path)

sys.path.append(current_dir)

from app.core.config import settings
from app.services.pipeline_service import PipelineService


async def test_competitor_search():
    print("=" * 60)
    print("TEST: Búsqueda de Competidores")
    print("=" * 60)

    # Verificar configuración
    print(f"\n1. Verificando configuración:")
    print(
        f"   GOOGLE_API_KEY: {'CONFIGURADA' if settings.GOOGLE_API_KEY else 'NO CONFIGURADA'}"
    )
    print(
        f"   GOOGLE_PAGESPEED_API_KEY: {'CONFIGURADA' if settings.GOOGLE_PAGESPEED_API_KEY else 'NO CONFIGURADA'}"
    )
    print(f"   CSE_ID: {settings.CSE_ID if settings.CSE_ID else 'NO CONFIGURADO'}")

    if not settings.GOOGLE_API_KEY:
        print("\n   ERROR: GOOGLE_API_KEY no está configurada!")
        print("   La búsqueda de competidores no funcionará sin esta clave.")
        return

    if not settings.CSE_ID:
        print("\n   ERROR: CSE_ID no está configurado!")
        print("   Se necesita el ID del Custom Search Engine.")
        return

    # Probar búsqueda directa
    print(f"\n2. Probando búsqueda de Google:")
    query = "farmacia online argentina"
    print(f"   Query: {query}")

    try:
        results = await PipelineService.run_google_search(
            query=query,
            api_key=settings.GOOGLE_API_KEY,
            cx_id=settings.CSE_ID,
            num_results=10,
        )

        if "error" in results:
            print(f"\n   ERROR en búsqueda: {results['error']}")
            return

        items = results.get("items", [])
        print(f"   Resultados encontrados: {len(items)}")

        if items:
            print(f"\n   Primeros 5 resultados:")
            for i, item in enumerate(items[:5], 1):
                print(f"   {i}. {item.get('title', 'N/A')}")
                print(f"      URL: {item.get('link', 'N/A')}")
        else:
            print("\n   No se encontraron resultados!")

    except Exception as e:
        print(f"\n   ERROR: {e}")
        import traceback

        traceback.print_exc()
        return

    # Probar filtrado de competidores
    print(f"\n3. Probando filtrado de competidores:")
    target_domain = "farmalife.com.ar"
    competitor_urls = PipelineService.filter_competitor_urls(
        items, target_domain, limit=5
    )
    print(f"   Dominio objetivo: {target_domain}")
    print(f"   Competidores encontrados: {len(competitor_urls)}")

    if competitor_urls:
        print(f"\n   URLs de competidores:")
        for i, url in enumerate(competitor_urls, 1):
            print(f"   {i}. {url}")
    else:
        print("\n   No se encontraron competidores!")
        print("   Esto puede deberse a:")
        print("   - Los resultados son de sitios no relacionados")
        print("   - Los resultados son de redes sociales, noticias, etc.")
        print("   - El filtro está siendo muy restrictivo")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(test_competitor_search())
