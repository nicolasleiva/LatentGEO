"""
HubSpot Integration - Quick Start Example
Ejemplo de implementación básica del cliente de HubSpot
"""

import os
from datetime import datetime
from typing import Dict, List, Optional

import httpx
from pydantic import BaseModel


class HubSpotPage(BaseModel):
    """Modelo de una página de HubSpot"""

    id: str
    name: str
    url: str
    title: Optional[str] = None
    meta_description: Optional[str] = None
    html_title: Optional[str] = None
    published_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class HubSpotClient:
    """Cliente para interactuar con la API de HubSpot"""

    BASE_URL = "https://api.hubapi.com"

    def __init__(self, access_token: str):
        self.access_token = access_token
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    async def get_all_pages(self, limit: int = 100) -> List[HubSpotPage]:
        """
        Obtiene todas las páginas del portal de HubSpot

        Returns:
            Lista de páginas de HubSpot
        """
        pages = []
        after = None

        while True:
            # API endpoint para páginas (CMS v3)
            url = "/cms/v3/pages/site-pages"
            params = {"limit": limit}

            if after:
                params["after"] = after

            response = await self.client.get(url, params=params)
            response.raise_for_status()

            data = response.json()

            # Convertir resultados a modelos
            for page_data in data.get("results", []):
                page = HubSpotPage(
                    id=page_data.get("id"),
                    name=page_data.get("name"),
                    url=page_data.get("url"),
                    title=page_data.get("htmlTitle"),
                    meta_description=page_data.get("metaDescription"),
                    published_at=page_data.get("publishDate"),
                    updated_at=page_data.get("updated"),
                )
                pages.append(page)

            # Verificar si hay más páginas
            paging = data.get("paging", {})
            after = paging.get("next", {}).get("after")

            if not after:
                break

        return pages

    async def get_page(self, page_id: str) -> HubSpotPage:
        """
        Obtiene una página específica por ID

        Args:
            page_id: ID de la página en HubSpot

        Returns:
            Página de HubSpot
        """
        url = f"/cms/v3/pages/site-pages/{page_id}"
        response = await self.client.get(url)
        response.raise_for_status()

        data = response.json()
        return HubSpotPage(
            id=data.get("id"),
            name=data.get("name"),
            url=data.get("url"),
            title=data.get("htmlTitle"),
            meta_description=data.get("metaDescription"),
            html_title=data.get("htmlTitle"),
            published_at=data.get("publishDate"),
            updated_at=data.get("updated"),
        )

    async def update_page_meta(
        self,
        page_id: str,
        html_title: Optional[str] = None,
        meta_description: Optional[str] = None,
    ) -> bool:
        """
        Actualiza los meta tags de una página

        Args:
            page_id: ID de la página
            html_title: Nuevo título HTML (opcional)
            meta_description: Nueva meta description (opcional)

        Returns:
            True si la actualización fue exitosa
        """
        url = f"/cms/v3/pages/site-pages/{page_id}"

        # Construir payload con los campos a actualizar
        payload = {}
        if html_title is not None:
            payload["htmlTitle"] = html_title
        if meta_description is not None:
            payload["metaDescription"] = meta_description

        if not payload:
            return False

        response = await self.client.patch(url, json=payload)
        response.raise_for_status()

        return True

    async def update_page_content(self, page_id: str, widgets: Dict) -> bool:
        """
        Actualiza el contenido (widgets) de una página

        Args:
            page_id: ID de la página
            widgets: Diccionario con los widgets a actualizar

        Returns:
            True si la actualización fue exitosa
        """
        url = f"/cms/v3/pages/site-pages/{page_id}"

        payload = {"widgets": widgets}

        response = await self.client.patch(url, json=payload)
        response.raise_for_status()

        return True

    async def close(self):
        """Cierra el cliente HTTP"""
        await self.client.aclose()


# ============================================================================
# EJEMPLO DE USO
# ============================================================================


async def example_usage():
    """Ejemplo de cómo usar el cliente de HubSpot"""

    # 1. Inicializar cliente con access token
    token = "your-hubspot-access-token-here"  # nosec B105
    client = HubSpotClient(access_token=token)

    try:
        # 2. Obtener todas las páginas
        print("📄 Obteniendo páginas de HubSpot...")
        pages = await client.get_all_pages()
        print(f"✅ Encontradas {len(pages)} páginas")

        # 3. Analizar cada página
        for page in pages[:5]:  # Solo las primeras 5
            print(f"\n📍 Página: {page.name}")
            print(f"   URL: {page.url}")
            print(f"   Título: {page.title}")
            print(f"   Meta: {page.meta_description}")

            # 4. EJEMPLO: Detectar meta description faltante
            if not page.meta_description or len(page.meta_description) < 50:
                print("   ⚠️  Meta description faltante o muy corta")

                # 5. Generar nueva meta description (aquí usarías tu LLM)
                new_meta = (
                    f"Descubre {page.name} - Información completa y optimizada para SEO"
                )

                print(f"   💡 Sugerencia: {new_meta}")

                # 6. APLICAR CAMBIO (comentado para seguridad)
                # await client.update_page_meta(
                #     page_id=page.id,
                #     meta_description=new_meta
                # )
                # print(f"   ✅ Meta description actualizada!")

        # 7. Ejemplo de actualización de una página específica
        page_id = pages[0].id if pages else None
        if page_id:
            print(f"\n🔧 Actualizando página {page_id}...")

            success = await client.update_page_meta(
                page_id=page_id,
                html_title="Nuevo Título Optimizado SEO",
                meta_description="Nueva descripción optimizada para motores de búsqueda con keywords relevantes",
            )

            if success:
                print("✅ Página actualizada exitosamente!")

    finally:
        # 8. Cerrar cliente
        await client.close()


# ============================================================================
# INTEGRACIÓN CON TU SISTEMA ACTUAL
# ============================================================================


class HubSpotAuditService:
    """Servicio para auditar páginas de HubSpot usando tu pipeline actual"""

    def __init__(self, hubspot_client: HubSpotClient, audit_service):
        self.hubspot_client = hubspot_client
        self.audit_service = audit_service

    async def audit_hubspot_portal(self, user_id: str, connection_id: str):
        """
        Audita todas las páginas de un portal de HubSpot

        Flow:
        1. Obtener páginas de HubSpot
        2. Crear auditoría en tu sistema
        3. Ejecutar pipeline de auditoría para cada URL
        4. Generar recomendaciones específicas para HubSpot
        5. Permitir aplicar cambios directamente
        """

        # 1. Obtener páginas
        pages = await self.hubspot_client.get_all_pages()

        # 2. Crear auditoría
        audit = await self.audit_service.create_audit(
            user_id=user_id,
            source="hubspot",
            metadata={"connection_id": connection_id, "total_pages": len(pages)},
        )

        # 3. Auditar cada página
        results = []
        for page in pages:
            # Usar tu pipeline existente
            page_audit = await self.audit_service.run_audit(
                url=page.url, audit_id=audit.id
            )

            # Guardar referencia a página de HubSpot
            results.append(
                {
                    "hubspot_page_id": page.id,
                    "audit_result": page_audit,
                    "can_auto_fix": self._can_auto_fix(page_audit),
                }
            )

        return {
            "audit_id": audit.id,
            "pages_audited": len(results),
            "auto_fixable": sum(1 for r in results if r["can_auto_fix"]),
            "results": results,
        }

    def _can_auto_fix(self, audit_result) -> bool:
        """Determina si los issues pueden ser auto-corregidos"""
        auto_fixable_issues = [
            "missing_meta_description",
            "short_meta_description",
            "missing_alt_text",
            "duplicate_h1",
        ]

        issues = audit_result.get("issues", [])
        return any(issue["type"] in auto_fixable_issues for issue in issues)

    async def apply_recommendations(self, audit_id: str, recommendations: List[Dict]):
        """
        Aplica recomendaciones directamente a HubSpot

        Args:
            audit_id: ID de la auditoría
            recommendations: Lista de recomendaciones a aplicar
        """
        applied = []
        failed = []

        for rec in recommendations:
            try:
                page_id = rec["hubspot_page_id"]
                field = rec["field"]  # "meta_description", "html_title", etc.
                new_value = rec["new_value"]

                # Aplicar según el tipo de campo
                if field in ["html_title", "meta_description"]:
                    success = await self.hubspot_client.update_page_meta(
                        page_id=page_id, **{field: new_value}
                    )

                    if success:
                        applied.append(rec)
                    else:
                        failed.append(rec)

            except Exception as e:
                print(f"Error aplicando recomendación: {e}")
                failed.append(rec)

        return {
            "applied": len(applied),
            "failed": len(failed),
            "details": {"applied": applied, "failed": failed},
        }


# ============================================================================
# OAUTH FLOW (Simplificado)
# ============================================================================


class HubSpotOAuth:
    """Maneja el flujo OAuth con HubSpot"""

    CLIENT_ID = os.getenv("HUBSPOT_CLIENT_ID", "")
    CLIENT_SECRET = os.getenv("HUBSPOT_CLIENT_SECRET", "")
    REDIRECT_URI = os.getenv(
        "HUBSPOT_REDIRECT_URI", "https://your-app.com/integrations/hubspot/callback"
    )

    SCOPES = [
        "content",
        "cms.pages.write",
        "cms.pages.read",
    ]

    @classmethod
    def get_authorization_url(cls) -> str:
        """Genera URL para iniciar OAuth"""
        scopes = " ".join(cls.SCOPES)
        return (
            f"https://app.hubspot.com/oauth/authorize"
            f"?client_id={cls.CLIENT_ID}"
            f"&redirect_uri={cls.REDIRECT_URI}"
            f"&scope={scopes}"
        )

    @classmethod
    async def exchange_code(cls, code: str) -> Dict:
        """Intercambia código por access token"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.hubapi.com/oauth/v1/token",
                data={
                    "grant_type": "authorization_code",
                    "client_id": cls.CLIENT_ID,
                    "client_secret": cls.CLIENT_SECRET,
                    "redirect_uri": cls.REDIRECT_URI,
                    "code": code,
                },
            )
            response.raise_for_status()
            return response.json()

    @classmethod
    async def refresh_token(cls, refresh_token: str) -> Dict:
        """Refresca el access token"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.hubapi.com/oauth/v1/token",
                data={
                    "grant_type": "refresh_token",
                    "client_id": cls.CLIENT_ID,
                    "client_secret": cls.CLIENT_SECRET,
                    "refresh_token": refresh_token,
                },
            )
            response.raise_for_status()
            return response.json()


if __name__ == "__main__":
    print("🚀 HubSpot Integration - Quick Start")
    print("=" * 50)
    print("\nEste ejemplo muestra cómo:")
    print("1. Conectar con HubSpot")
    print("2. Obtener páginas")
    print("3. Auditarlas con tu sistema")
    print("4. Aplicar cambios automáticamente")
    print("\n" + "=" * 50)

    # asyncio.run(example_usage())
    print("\n⚠️  Para ejecutar, descomenta la línea anterior y agrega tu token")
