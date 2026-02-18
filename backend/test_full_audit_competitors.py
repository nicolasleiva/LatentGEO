#!/usr/bin/env python3
"""
Test completo: auditoría de farmalife con competidores
"""

import asyncio
import os
import sys

# Load .env
from dotenv import load_dotenv

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
env_path = os.path.join(parent_dir, ".env")
load_dotenv(env_path)

# Override DATABASE_URL
os.environ["DATABASE_URL"] = "sqlite:///./test_farmalife_full.db"
os.environ["MAX_CRAWL_PAGES"] = "10"  # Reducir para hacerlo más rápido
os.environ["MAX_AUDIT_PAGES"] = "10"

sys.path.append(current_dir)

import logging

logging.basicConfig(level=logging.INFO, format="%(message)s")

from app.core.config import settings
from app.core.database import SessionLocal, init_db
from app.models import Audit, AuditStatus, Competitor
from app.services.audit_local_service import AuditLocalService
from app.services.audit_service import AuditService
from app.services.pipeline_service import PipelineService


async def run_full_audit_with_competitors():
    print("=" * 70)
    print("AUDITORÍA COMPLETA CON COMPETIDORES - FARMAlIFE")
    print("=" * 70)

    # Inicializar DB
    await init_db()

    db = SessionLocal()
    try:
        url = "https://www.farmalife.com.ar/"

        # Crear auditoría
        print(f"\n1. Creando auditoría para: {url}")
        audit = Audit(url=url, domain="farmalife.com.ar", status=AuditStatus.PENDING)
        db.add(audit)
        db.commit()
        db.refresh(audit)
        print(f"   Audit ID: {audit.id}")

        # Actualizar estado a RUNNING
        audit.status = AuditStatus.RUNNING
        db.commit()
        print(f"   Estado: {audit.status.value}")

        # Ejecutar auditoría local del target
        print(f"\n2. Auditando target...")
        target_audit = await run_local_audit_with_crawl(url)
        print(f"   Páginas auditadas: {target_audit.get('audited_pages_count', 0)}")

        # Buscar competidores
        print(f"\n3. Buscando competidores...")
        competitor_urls = await find_competitors(url)
        print(f"   Encontrados: {len(competitor_urls)}")
        for i, comp_url in enumerate(competitor_urls[:3], 1):
            print(f"   {i}. {comp_url}")

        # Auditar competidores
        print(f"\n4. Auditando competidores...")
        competitor_audits = await audit_competitors(
            competitor_urls[:3]
        )  # Solo 3 para hacerlo rápido
        print(f"   Completados: {len(competitor_audits)}")

        # Guardar resultados
        print(f"\n5. Guardando resultados...")
        audit.target_audit = target_audit
        audit.competitor_audits = competitor_audits
        audit.status = AuditStatus.COMPLETED
        db.commit()

        # Guardar competidores en tabla Competitor
        for comp_data in competitor_audits:
            if isinstance(comp_data, dict) and comp_data.get("url"):
                from app.services.audit_service import CompetitorService

                CompetitorService.add_competitor(
                    db=db,
                    audit_id=audit.id,
                    url=comp_data.get("url"),
                    geo_score=0,
                    audit_data=comp_data,
                )

        print(f"   Competidores guardados en BD")

        # Verificar
        print(f"\n6. VERIFICACIÓN:")
        audit = db.query(Audit).filter(Audit.id == audit.id).first()
        print(f"   Estado: {audit.status.value}")
        print(
            f"   Competitor_audits: {len(audit.competitor_audits) if audit.competitor_audits else 0}"
        )

        comps = db.query(Competitor).filter(Competitor.audit_id == audit.id).all()
        print(f"   Tabla Competitor: {len(comps)} registros")

        # Probar endpoint
        print(f"\n7. PRUEBA DEL ENDPOINT:")
        from app.api.routes.audits import get_competitors

        try:
            result = get_competitors(audit.id, 10, db)
            print(f"   Endpoint retorna: {len(result)} competidores")
            for i, comp in enumerate(result, 1):
                print(
                    f"   {i}. {comp.get('domain', 'N/A')} - GEO: {comp.get('geo_score', 'N/A')}"
                )
        except Exception as e:
            print(f"   Error: {e}")

        print("\n" + "=" * 70)
        print("AUDITORÍA COMPLETADA EXITOSAMENTE")
        print(f"URL: http://localhost:3000/audits/{audit.id}")
        print("=" * 70)

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback

        traceback.print_exc()
    finally:
        db.close()


async def run_local_audit_with_crawl(url: str) -> dict:
    """Ejecutar auditoría local del target con crawling"""
    from app.services.crawler_service import crawl_site

    # Crawl
    crawled_urls = await crawl_site(
        base_url=url,
        max_pages=int(os.getenv("MAX_CRAWL_PAGES", "10")),
        allow_subdomains=False,
    )

    # Auditar primera página como representativa
    base_audit, _ = await AuditLocalService.run_local_audit(url)

    return {
        "url": url,
        "domain": "farmalife.com.ar",
        "audited_pages_count": len(crawled_urls),
        "audited_page_paths": crawled_urls[:10],
        "base_audit": base_audit,
        "crawled_at": "2024-01-01T00:00:00Z",
    }


async def find_competitors(target_url: str) -> list:
    """Buscar competidores usando Google Search"""
    # Buscar por categoría
    queries = [
        "farmacia online argentina",
        "dermocosmetica online argentina",
        "perfumeria online argentina",
    ]

    all_items = []
    for query in queries[:1]:  # Solo primera query para hacerlo rápido
        results = await PipelineService.run_google_search(
            query=query,
            api_key=settings.GOOGLE_API_KEY,
            cx_id=settings.CSE_ID,
            num_results=10,
        )
        if "error" not in results:
            all_items.extend(results.get("items", []))

    # Filtrar competidores
    from urllib.parse import urlparse

    target_domain = urlparse(target_url).netloc.replace("www.", "")
    competitor_urls = PipelineService.filter_competitor_urls(
        all_items, target_domain, limit=5
    )

    return competitor_urls


async def audit_competitors(urls: list) -> list:
    """Auditar lista de competidores"""
    service = PipelineService()

    async def audit_fn(url: str) -> dict:
        audit_data, _ = await AuditLocalService.run_local_audit(url)
        return audit_data

    return await service.generate_competitor_audits(
        competitor_urls=urls, audit_local_function=audit_fn
    )


if __name__ == "__main__":
    asyncio.run(run_full_audit_with_competitors())
