import httpx
import asyncio
from typing import List, Dict, Optional, Any
from datetime import datetime
from ...core.config import settings

class HubSpotClient:
    """Cliente para interactuar con la API de HubSpot"""
    
    BASE_URL = "https://api.hubapi.com"
    
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            },
            timeout=30.0
        )
    
    async def get_all_pages(self, limit: int = 100) -> List[Dict]:
        """
        Obtiene todas las páginas del portal de HubSpot (CMS Pages)
        """
        pages = []
        after = None
        
        while True:
            url = "/cms/v3/pages/site-pages"
            params = {"limit": limit}
            
            if after:
                params["after"] = after
            
            try:
                response = await self.client.get(url, params=params)
                
                # Handle token expiration or other errors gracefully
                if response.status_code == 401:
                    raise Exception("HubSpot Access Token Expired")
                
                response.raise_for_status()
                data = response.json()
                
                pages.extend(data.get("results", []))
                
                paging = data.get("paging", {})
                after = paging.get("next", {}).get("after")
                
                if not after:
                    break
                    
            except httpx.HTTPStatusError as e:
                print(f"Error fetching HubSpot pages: {e}")
                raise
            except Exception as e:
                print(f"Unexpected error: {e}")
                raise
        
        return pages
    
    async def get_page(self, page_id: str) -> Dict:
        """Obtiene una página específica por ID"""
        url = f"/cms/v3/pages/site-pages/{page_id}"
        response = await self.client.get(url)
        response.raise_for_status()
        return response.json()
    
    async def update_page(self, page_id: str, data: Dict) -> bool:
        """
        Actualiza una página en HubSpot
        
        Args:
            page_id: ID de la página
            data: Diccionario con los campos a actualizar (ej: {"htmlTitle": "New Title"})
        """
        url = f"/cms/v3/pages/site-pages/{page_id}"
        
        try:
            response = await self.client.patch(url, json=data)
            response.raise_for_status()
            return True
        except httpx.HTTPStatusError as e:
            print(f"Error updating HubSpot page {page_id}: {e.response.text}")
            return False
    
    async def close(self):
        await self.client.aclose()
