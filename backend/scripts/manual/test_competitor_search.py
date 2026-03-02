#!/usr/bin/env python3
"""
Test simple para verificar la búsqueda de competidores
"""

import asyncio
import os
import sys

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
        f"   SERPER_API_KEY: {'CONFIGURADA' if settings.SERPER_API_KEY else 'NO CONFIGURADA'}"
    )
    print(
        f"   GOOGLE_PAGESPEED_API_KEY: {'CONFIGURADA' if settings.GOOGLE_PAGESPEED_API_KEY else 'NO CONFIGURADA'}"
    )

    if not settings.SERPER_API_KEY:
        print("\n   ERROR: SERPER_API_KEY no está configurada!")
        print("   La búsqueda de competidores no funcionará sin esta clave.")
        return 1

    # Probar búsqueda directa
    print(f"\n2. Probando búsqueda de Serper:")
    query = "farmacia online argentina"
    print(f"   Query: {query}")

    try:
        results = await PipelineService.run_serper_search(
            query=query,
            api_key=settings.SERPER_API_KEY,
            num_results=10,
        )

        if "error" in results:
            print(f"\n   ERROR en búsqueda: {results['error']}")
            return 1

        items = results.get("items", [])
        print(f"   Resultados encontrados: {len(items)}")

        if items:
            print(f"\n   Primeros 5 resultados:")
            for i, item in enumerate(items[:5], 1):
                print(f"   {i}. {item.get('title', 'N/A')}")
                print(f"      URL: {item.get('link', 'N/A')}")
        else:
            print("\n   ERROR: no se encontraron resultados en Serper.")
            return 1

    except Exception as e:
        print(f"\n   ERROR: {e}")
        import traceback

        traceback.print_exc()
        return 1

    # Probar filtrado de competidores
    print(f"\n3. Probando filtrado de competidores:")
    target_domain = "farmalife.com.ar"
    competitor_urls = PipelineService.filter_competitor_urls(
        items,
        target_domain,
        limit=5,
        core_terms=["farmacia", "online", "salud", "medicamentos", "dermocosmetica"],
        anchor_terms=["farmacia", "perfumeria", "dermocosmetica"],
    )
    print(f"   Dominio objetivo: {target_domain}")
    print(f"   Competidores encontrados: {len(competitor_urls)}")

    if competitor_urls:
        print(f"\n   URLs de competidores:")
        for i, url in enumerate(competitor_urls, 1):
            print(f"   {i}. {url}")
    else:
        print("\n   ERROR: no se encontraron competidores procesables.")
        return 1

    print("\n" + "=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(test_competitor_search()))
