import hashlib
import uuid
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...core.access_control import (
    ensure_audit_access,
    ensure_connection_access,
    is_connection_owned_by_user,
)
from ...core.auth import AuthUser, get_current_user
from ...core.oauth_state import build_oauth_state, validate_oauth_state
from ...core.database import get_db
from ...integrations.hubspot.auth import HubSpotAuth
from ...integrations.hubspot.service import HubSpotService
from ...models import AIContentSuggestion, Audit, AuditedPage
from ...models.hubspot import HubSpotChange, HubSpotConnection, HubSpotPage

router = APIRouter(prefix="/hubspot", tags=["hubspot"])


class ConnectRequest(BaseModel):
    code: str
    state: Optional[str] = None


class ConnectResponse(BaseModel):
    url: str
    state: str


class ApplyChangeRequest(BaseModel):
    connection_id: str
    page_id: str
    field: str
    new_value: str
    audit_id: Optional[int] = None


@router.get("/auth-url", response_model=ConnectResponse)
def get_auth_url(current_user: AuthUser = Depends(get_current_user)):
    """Obtiene la URL para iniciar la autenticación con HubSpot"""
    state = build_oauth_state("hubspot", current_user)
    return {"url": HubSpotAuth.get_authorization_url(state=state), "state": state}


def _get_owned_connection(
    db: Session, connection_id: str, current_user: AuthUser
) -> HubSpotConnection:
    connection = (
        db.query(HubSpotConnection)
        .filter(
            HubSpotConnection.id == connection_id,
            HubSpotConnection.is_active.is_(True),
        )
        .first()
    )
    return ensure_connection_access(
        connection,
        current_user,
        db,
        resource_label="conexión de HubSpot",
    )


@router.post("/callback")
async def oauth_callback(
    request: ConnectRequest,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """Maneja el callback de OAuth y crea la conexión"""
    try:
        validate_oauth_state(request.state or "", "hubspot", current_user)

        # 1. Exchange code for tokens
        token_data = await HubSpotAuth.exchange_code(request.code)

        # 2. Get portal ID from token response or fetch from API
        # HubSpot includes hub_id in the token response
        portal_id = (
            token_data.get("hub_id") or token_data.get("hub_domain") or "default_portal"
        )

        # If not in token, fetch from account info endpoint
        if portal_id == "default_portal":
            from ...integrations.hubspot.client import HubSpotClient

            temp_client = HubSpotClient(token_data["access_token"])
            try:
                # Try to get account info
                account_info = await temp_client.client.get("/account-info/v3/details")
                if account_info.status_code == 200:
                    data = account_info.json()
                    portal_id = str(data.get("portalId", "default_portal"))
            except Exception:
                # If fails, use a hash of the access token as unique identifier
                portal_id = hashlib.sha256(
                    token_data["access_token"].encode()
                ).hexdigest()[:16]
            finally:
                await temp_client.close()

        service = HubSpotService(db)
        connection = await service.create_or_update_connection(
            token_data=token_data,
            portal_id=portal_id,
            owner_user_id=current_user.user_id,
            owner_email=current_user.email,
        )

        return {
            "status": "success",
            "connection_id": connection.id,
            "portal_id": portal_id,
        }

    except HTTPException:
        raise
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/connections")
def get_connections(
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """Lista conexiones activas de HubSpot"""
    all_connections = (
        db.query(HubSpotConnection).filter(HubSpotConnection.is_active.is_(True)).all()
    )
    connections = []
    for connection in all_connections:
        if is_connection_owned_by_user(connection, current_user):
            connections.append(connection)
            continue

        # Legacy rows only in DEBUG are auto-claimed.
        if (
            not connection.owner_user_id
            and not connection.owner_email
            and current_user
        ):
            try:
                claimed = ensure_connection_access(
                    connection,
                    current_user,
                    db,
                    resource_label="conexión de HubSpot",
                )
                connections.append(claimed)
            except HTTPException:
                # Skip non-owned rows in production.
                continue

    return [
        {
            "id": c.id,
            "portal_id": c.portal_id,
            "created_at": c.created_at,
            "is_active": c.is_active,
        }
        for c in connections
    ]


@router.post("/sync/{connection_id}")
async def sync_pages(
    connection_id: str,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """Sincroniza las páginas de una conexión"""
    service = HubSpotService(db)
    try:
        _get_owned_connection(db, connection_id, current_user)
        pages = await service.sync_pages(connection_id)
        return {"status": "success", "synced_count": len(pages)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pages/{connection_id}")
def get_pages(
    connection_id: str,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """Obtiene las páginas sincronizadas"""
    _get_owned_connection(db, connection_id, current_user)
    pages = (
        db.query(HubSpotPage).filter(HubSpotPage.connection_id == connection_id).all()
    )
    return pages


class BatchApplyRequest(BaseModel):
    audit_id: int
    recommendations: List[Dict]


def _get_owned_audit(db: Session, audit_id: int, current_user: AuthUser):
    audit = db.query(Audit).filter(Audit.id == audit_id).first()
    return ensure_audit_access(audit, current_user)


@router.get("/recommendations/{audit_id}")
def get_recommendations(
    audit_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """Obtiene recomendaciones de HubSpot basadas en una auditoría"""

    # 1. Obtener auditoría y páginas
    _get_owned_audit(db, audit_id, current_user)

    pages = db.query(AuditedPage).filter(AuditedPage.audit_id == audit_id).all()

    recommendations = []

    for page in pages:
        # Buscar página de HubSpot correspondiente por URL
        # Nota: Esto asume que la URL auditada coincide con la URL de HubSpot
        # En un caso real, podríamos necesitar un mapeo más robusto
        hubspot_pages = db.query(HubSpotPage).filter(HubSpotPage.url == page.url).all()
        hubspot_page = None
        for candidate in hubspot_pages:
            connection = (
                db.query(HubSpotConnection)
                .filter(HubSpotConnection.id == candidate.connection_id)
                .first()
            )
            if connection and is_connection_owned_by_user(connection, current_user):
                hubspot_page = candidate
                break

        if not hubspot_page:
            continue

        # Analizar issues y generar recomendaciones
        # Esto es una simplificación. En realidad, mapearíamos issues específicos a campos de HubSpot.

        # Ejemplo: Meta Description Faltante
        if page.audit_data and "meta_description" in page.audit_data:
            meta = page.audit_data["meta_description"]
            if not meta or len(meta) < 10:
                # Buscar si hay sugerencia de IA
                suggestion = (
                    db.query(AIContentSuggestion)
                    .filter(
                        AIContentSuggestion.audit_id == audit_id,
                        AIContentSuggestion.page_url == page.url,
                        AIContentSuggestion.topic == "meta_description",
                    )
                    .first()
                )

                rec_value = (
                    suggestion.content_outline.get("text")
                    if suggestion and suggestion.content_outline
                    else "Please write a meta description."
                )

                recommendations.append(
                    {
                        "id": str(uuid.uuid4()),
                        "hubspot_page_id": hubspot_page.hubspot_id,
                        "page_url": page.url,
                        "page_title": hubspot_page.title or page.url,
                        "field": "meta_description",
                        "current_value": hubspot_page.meta_description,
                        "recommended_value": rec_value,
                        "priority": "high",
                        "auto_fixable": True,
                        "issue_type": "Missing Meta Description",
                    }
                )

        # Ejemplo: Title Tag
        if page.audit_data and "title" in page.audit_data:
            title = page.audit_data["title"]
            if not title or len(title) < 10:
                recommendations.append(
                    {
                        "id": str(uuid.uuid4()),
                        "hubspot_page_id": hubspot_page.hubspot_id,
                        "page_url": page.url,
                        "page_title": hubspot_page.title or page.url,
                        "field": "html_title",
                        "current_value": hubspot_page.html_title,
                        "recommended_value": "Optimized Title",  # Placeholder logic
                        "priority": "medium",
                        "auto_fixable": True,
                        "issue_type": "Poor Title",
                    }
                )

    return {"recommendations": recommendations}


@router.post("/apply-recommendations")
async def batch_apply_recommendations(
    request: BatchApplyRequest,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """Aplica un lote de recomendaciones"""
    _get_owned_audit(db, request.audit_id, current_user)
    service = HubSpotService(db)

    # Necesitamos encontrar la conexión ID asociada a estas páginas.
    # Asumimos que todas pertenecen a la misma conexión por ahora o la buscamos por página.

    results = {"applied": [], "failed": []}
    applied_count = 0

    for rec in request.recommendations:
        try:
            # Buscar la página para obtener connection_id
            page = (
                db.query(HubSpotPage)
                .filter(HubSpotPage.hubspot_id == rec["hubspot_page_id"])
                .first()
            )
            if not page:
                results["failed"].append(
                    {"page_id": rec["hubspot_page_id"], "error": "Page not found"}
                )
                continue

            try:
                _get_owned_connection(db, page.connection_id, current_user)
            except HTTPException as forbidden:
                results["failed"].append(
                    {
                        "page_id": rec["hubspot_page_id"],
                        "error": forbidden.detail,
                        "field": rec.get("field", "unknown"),
                    }
                )
                continue

            change = await service.apply_change(
                connection_id=page.connection_id,
                page_id=rec["hubspot_page_id"],
                field=rec["field"],
                new_value=rec["recommended_value"],
                audit_id=request.audit_id,
            )

            if change.status == "applied":
                results["applied"].append(
                    {
                        "page_id": rec["hubspot_page_id"],
                        "success": True,
                        "field": rec["field"],
                    }
                )
                applied_count += 1
            else:
                results["failed"].append(
                    {
                        "page_id": rec["hubspot_page_id"],
                        "error": change.error_message,
                        "field": rec["field"],
                    }
                )

        except Exception as e:
            results["failed"].append(
                {
                    "page_id": rec.get("hubspot_page_id"),
                    "error": str(e),
                    "field": rec.get("field", "unknown"),
                }
            )

    return {
        "status": "completed",
        "applied": applied_count,
        "failed": len(results["failed"]),
        "details": results,
    }


@router.post("/rollback/{change_id}")
async def rollback_change(
    change_id: str,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """Revierte un cambio aplicado"""
    service = HubSpotService(db)

    # Obtener el cambio
    change = db.query(HubSpotChange).filter(HubSpotChange.id == change_id).first()
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")

    _get_owned_connection(db, change.page.connection_id, current_user)

    if change.status != "applied":
        raise HTTPException(
            status_code=400, detail="Cannot rollback a change that is not applied"
        )

    try:
        # Aplicar el valor antiguo
        # Usamos apply_change pero invirtiendo valores y marcando como rollback
        # Pero para ser más limpios, deberíamos tener un método específico o usar apply_change con cuidado.
        # Vamos a usar apply_change para que cree un NUEVO registro de cambio que sea la reversión.
        # O podemos actualizar el estado del actual.
        # El plan decía "Rollback mechanism".
        # Lo mejor es aplicar el old_value como un nuevo cambio.

        new_change = await service.apply_change(
            connection_id=change.page.connection_id,
            page_id=change.page.hubspot_id,
            field=change.field,
            new_value=change.old_value,
            audit_id=change.audit_id,
        )

        if new_change.status == "applied":
            change.status = "rolled_back"
            db.commit()
            return {"status": "success", "new_change_id": new_change.id}
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to rollback: {new_change.error_message}",
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
