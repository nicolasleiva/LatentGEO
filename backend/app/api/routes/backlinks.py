from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...core.access_control import ensure_audit_access
from ...core.auth import AuthUser, get_current_user
from ...core.database import get_db
from ...schemas import BacklinkResponse
from ...services.audit_service import AuditService
from ...services.backlink_service import BacklinkService

router = APIRouter(prefix="/backlinks", tags=["backlinks"])


@router.post("/analyze/{audit_id}", response_model=List[BacklinkResponse])
async def analyze_backlinks(
    audit_id: int,
    domain: str = Query(..., description="Domain to analyze"),
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """Analyze backlinks for a given audit and domain"""
    ensure_audit_access(AuditService.get_audit(db, audit_id), current_user)
    service = BacklinkService(db)
    return await service.analyze_backlinks(audit_id, domain)


@router.get("/{audit_id}", response_model=List[BacklinkResponse])
def get_backlinks(
    audit_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """Get stored backlinks for an audit"""
    ensure_audit_access(AuditService.get_audit(db, audit_id), current_user)
    service = BacklinkService(db)
    return service.get_backlinks(audit_id)
