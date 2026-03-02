#!/usr/bin/env python3
"""
Test específico para la generación de auditorías de competidores
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

# Override DATABASE_URL to use SQLite for local testing
os.environ["DATABASE_URL"] = "sqlite:///./test_competitors.db"

sys.path.append(current_dir)

from app.core.config import settings
from app.services.audit_local_service import AuditLocalService
from app.services.pipeline_service import PipelineService


async def test_competitor_audit_generation():
    print("=" * 70)
    print("TEST: Generacion de Auditorias de Competidores")
    print("=" * 70)

    # Lista de competidores para testear
    competitor_urls = [
        "https://www.farmaplus.com.ar/",
        "https://www.farmacity.com/",
    ]

    print(f"\nCompetidores a auditar: {len(competitor_urls)}")
    for url in competitor_urls:
        print(f"  - {url}")

    print(f"\nIniciando auditorias...")
    print("(Esto puede tardar varios minutos)\n")

    try:
        # Crear instancia del servicio
        service = PipelineService()

        # Funcion de auditoria local
        async def audit_local_service(url: str) -> dict:
            """Helper para auditar una URL localmente"""
            print(f"  -> Auditando: {url}")
            try:
                audit_data, _ = await AuditLocalService.run_local_audit(url)
                print(f"    [OK] Completado: {url}")
                return audit_data
            except Exception as e:
                print(f"    [ERROR] {e}")
                raise

        # Generar auditorias de competidores
        start_time = asyncio.get_event_loop().time()

        competitor_audits = await service.generate_competitor_audits(
            competitor_urls=competitor_urls, audit_local_function=audit_local_service
        )

        elapsed = asyncio.get_event_loop().time() - start_time

        print(f"\n" + "=" * 70)
        print(f"RESULTADOS ({elapsed:.1f} segundos)")
        print("=" * 70)

        print(f"\nAuditorias completadas: {len(competitor_audits)}")

        for i, audit in enumerate(competitor_audits, 1):
            url = audit.get("url", "N/A")
            error = audit.get("error")

            if error:
                print(f"\n{i}. {url}")
                print(f"   Status: ERROR")
                print(f"   Error: {error}")
            else:
                # Extraer metricas clave
                schema = audit.get("schema", {})
                structure = audit.get("structure", {})
                content = audit.get("content", {})

                schema_present = (
                    schema.get("schema_presence", {}).get("status") == "present"
                )
                semantic_score = structure.get("semantic_html", {}).get(
                    "score_percent", 0
                )
                h1_status = structure.get("h1_check", {}).get("status")
                conversational = content.get("conversational_tone", {}).get("score", 0)

                print(f"\n{i}. {url}")
                print(f"   Status: OK")
                print(f"   Schema: {'SI' if schema_present else 'NO'}")
                print(f"   Semantic HTML: {semantic_score}%")
                print(f"   H1: {h1_status}")
                print(f"   Conversational: {conversational}/5")

        # Verificar si hay errores
        errors = [a for a in competitor_audits if a.get("error")]
        if errors:
            print(
                f"\n[ADVERTENCIA] {len(errors)} de {len(competitor_audits)} auditorias fallaron"
            )
        else:
            print(f"\n[EXITO] Todas las auditorias completadas exitosamente")

    except Exception as e:
        print(f"\n[ERROR GENERAL] {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_competitor_audit_generation())
