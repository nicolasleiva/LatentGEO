from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List, Optional, Dict
import uuid

from ...models.hubspot import HubSpotConnection, HubSpotPage, HubSpotChange, ChangeStatus
from ...models import Audit
from .client import HubSpotClient
from .auth import HubSpotAuth

class HubSpotService:
    
    def __init__(self, db: Session):
        self.db = db

    async def create_or_update_connection(self, token_data: Dict, portal_id: str) -> HubSpotConnection:
        """Crea o actualiza una conexión de HubSpot"""
        
        # Buscar conexión existente por portal_id
        connection = self.db.query(HubSpotConnection).filter(
            HubSpotConnection.portal_id == portal_id
        ).first()
        
        expires_in = token_data.get("expires_in", 1800)
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        
        encrypted_access_token = HubSpotAuth.encrypt_token(token_data["access_token"])
        encrypted_refresh_token = HubSpotAuth.encrypt_token(token_data["refresh_token"])
        
        if connection:
            connection.access_token = encrypted_access_token
            connection.refresh_token = encrypted_refresh_token
            connection.expires_at = expires_at
            connection.updated_at = datetime.utcnow()
        else:
            connection = HubSpotConnection(
                portal_id=portal_id,
                access_token=encrypted_access_token,
                refresh_token=encrypted_refresh_token,
                expires_at=expires_at,
                scopes=",".join(HubSpotAuth.SCOPES)
            )
            self.db.add(connection)
        
        self.db.commit()
        self.db.refresh(connection)
        return connection

    async def get_valid_client(self, connection_id: str) -> HubSpotClient:
        """Obtiene un cliente de HubSpot con token válido"""
        connection = self.db.query(HubSpotConnection).filter(
            HubSpotConnection.id == connection_id
        ).first()
        
        if not connection:
            raise ValueError("Connection not found")
            
        # Check if token is expired or about to expire (buffer of 5 mins)
        if connection.expires_at < datetime.utcnow() + timedelta(minutes=5):
            # Refresh token
            refresh_token = HubSpotAuth.decrypt_token(connection.refresh_token)
            new_tokens = await HubSpotAuth.refresh_token(refresh_token)
            
            # Update connection
            connection.access_token = HubSpotAuth.encrypt_token(new_tokens["access_token"])
            connection.refresh_token = HubSpotAuth.encrypt_token(new_tokens["refresh_token"])
            connection.expires_at = datetime.utcnow() + timedelta(seconds=new_tokens["expires_in"])
            self.db.commit()
            
        access_token = HubSpotAuth.decrypt_token(connection.access_token)
        return HubSpotClient(access_token)

    async def sync_pages(self, connection_id: str) -> List[HubSpotPage]:
        """Sincroniza las páginas de HubSpot con la base de datos local"""
        client = await self.get_valid_client(connection_id)
        
        # Fetch pages from HubSpot
        hubspot_pages = await client.get_all_pages()
        
        synced_pages = []
        for hp in hubspot_pages:
            # Buscar si ya existe
            page = self.db.query(HubSpotPage).filter(
                HubSpotPage.connection_id == connection_id,
                HubSpotPage.hubspot_id == hp["id"]
            ).first()
            
            if not page:
                page = HubSpotPage(
                    connection_id=connection_id,
                    hubspot_id=hp["id"]
                )
                self.db.add(page)
            
            # Actualizar datos
            page.url = hp.get("url", "")
            page.title = hp.get("name", "") # Internal name
            page.html_title = hp.get("htmlTitle", "")
            page.meta_description = hp.get("metaDescription", "")
            
            # Handle timestamps safely
            updated_ts = hp.get("updated")
            if updated_ts:
                # HubSpot returns timestamps in milliseconds usually, sometimes ISO strings
                # Assuming ISO string or timestamp. If timestamp, convert.
                # For simplicity, let's assume it might need parsing if it's a string
                pass 
                
            page.last_synced_at = datetime.utcnow()
            synced_pages.append(page)
        
        self.db.commit()
        return synced_pages

    async def apply_change(self, connection_id: str, page_id: str, field: str, new_value: str, audit_id: Optional[int] = None) -> HubSpotChange:
        """Aplica un cambio a una página de HubSpot"""
        client = await self.get_valid_client(connection_id)
        
        # Get local page to verify
        page = self.db.query(HubSpotPage).filter(
            HubSpotPage.connection_id == connection_id,
            HubSpotPage.hubspot_id == page_id
        ).first()
        
        if not page:
            raise ValueError(f"Page {page_id} not found in local DB. Please sync first.")
        
        # Get current value for rollback
        current_value = ""
        if field == "meta_description":
            current_value = page.meta_description
        elif field == "html_title":
            current_value = page.html_title
            
        # Create change record
        change = HubSpotChange(
            page_id=page.id,
            audit_id=audit_id,
            field=field,
            old_value=current_value,
            new_value=new_value,
            status=ChangeStatus.PENDING
        )
        self.db.add(change)
        self.db.commit()
        
        # Apply to HubSpot
        hubspot_field_map = {
            "meta_description": "metaDescription",
            "html_title": "htmlTitle"
        }
        
        if field not in hubspot_field_map:
             change.status = ChangeStatus.FAILED
             change.error_message = f"Field {field} not supported"
             self.db.commit()
             return change

        api_field = hubspot_field_map[field]
        
        success = await client.update_page(page_id, {api_field: new_value})
        
        if success:
            change.status = ChangeStatus.APPLIED
            change.applied_at = datetime.utcnow()
            
            # Update local page model
            if field == "meta_description":
                page.meta_description = new_value
            elif field == "html_title":
                page.html_title = new_value
                
        else:
            change.status = ChangeStatus.FAILED
            change.error_message = "Failed to update in HubSpot API"
            
        self.db.commit()
        self.db.refresh(change)
        return change
