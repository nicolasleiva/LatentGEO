#!/usr/bin/env python3
"""
Test para verificar el endpoint de competidores y el estado de auditoría
"""

import os
import sys
import asyncio

# Load .env
from dotenv import load_dotenv

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
env_path = os.path.join(parent_dir, ".env")
load_dotenv(env_path)

# Override DATABASE_URL
os.environ["DATABASE_URL"] = "sqlite:///./test_farmalife.db"

sys.path.append(current_dir)

import json
from app.core.database import SessionLocal
from app.models import Audit, AuditStatus, Competitor


def check_audit_and_competitors():
    print("=" * 70)
    print("VERIFICACIÓN: Estado de Auditoría y Competidores")
    print("=" * 70)

    db = SessionLocal()
    try:
        # Obtener auditoría de farmalife
        audit = db.query(Audit).first()

        if not audit:
            print("\n[ERROR] No se encontró ninguna auditoría")
            return

        print(f"\n1. AUDITORÍA:")
        print(f"   ID: {audit.id}")
        print(f"   URL: {audit.url}")
        print(f"   Status (enum): {audit.status}")
        print(
            f"   Status (value): {audit.status.value if hasattr(audit.status, 'value') else audit.status}"
        )
        print(f"   Status type: {type(audit.status)}")

        # Simular lo que retorna el API
        audit_dict = {
            "id": audit.id,
            "url": audit.url,
            "status": audit.status.value
            if hasattr(audit.status, "value")
            else str(audit.status),
            "domain": audit.domain,
        }
        print(f"\n   Status en API: {audit_dict['status']}")
        print(f"   Comparación con 'completed': {audit_dict['status'] == 'completed'}")

        # Verificar competitor_audits JSON
        print(f"\n2. COMPETIDOR_AUDITS (JSON):")
        if audit.competitor_audits:
            print(f"   Cantidad: {len(audit.competitor_audits)}")
            for i, comp in enumerate(audit.competitor_audits[:3], 1):
                print(f"   {i}. {comp.get('url', 'N/A')}")
        else:
            print(f"   Vacío: {audit.competitor_audits}")

        # Verificar tabla Competitor
        print(f"\n3. TABLA COMPETITOR:")
        competitors = db.query(Competitor).filter(Competitor.audit_id == audit.id).all()
        print(f"   Registros: {len(competitors)}")
        for comp in competitors:
            print(f"   - {comp.url} (GEO: {comp.geo_score})")

        # Verificar el endpoint
        print(f"\n4. PRUEBA DEL ENDPOINT /api/audits/{audit.id}/competitors:")
        from app.api.routes.audits import get_competitors
        from fastapi import HTTPException

        try:
            result = get_competitors(audit.id, 10, db)
            print(f"   Resultado: {len(result)} competidores")
            for i, comp in enumerate(result[:3], 1):
                print(
                    f"   {i}. {comp.get('url', 'N/A')} - GEO: {comp.get('geo_score', 'N/A')}"
                )
        except HTTPException as e:
            print(f"   HTTPException: {e.status_code} - {e.detail}")
        except Exception as e:
            print(f"   Error: {e}")

        print("\n" + "=" * 70)

    finally:
        db.close()


if __name__ == "__main__":
    check_audit_and_competitors()
