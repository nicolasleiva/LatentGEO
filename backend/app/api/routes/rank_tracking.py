from fastapi import APIRouter, Depends, HTTPException, Body, Query
from sqlalchemy.orm import Session
from typing import List
from ...core.database import get_db
from ...core.auth import AuthUser, get_current_user
from ...core.access_control import ensure_audit_access
from ...services.audit_service import AuditService
from ...services.rank_tracker_service import RankTrackerService
from ...schemas import RankTrackingResponse

router = APIRouter(prefix="/rank-tracking", tags=["rank-tracking"])

@router.post("/track/{audit_id}", response_model=List[RankTrackingResponse])
async def track_rankings(
    audit_id: int, 
    domain: str = Query(..., description="Domain to track rankings for"),
    keywords: List[str] = Body(...),
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    ensure_audit_access(AuditService.get_audit(db, audit_id), current_user)
    service = RankTrackerService(db)
    return await service.track_rankings(audit_id, domain, keywords)

@router.get("/{audit_id}", response_model=List[RankTrackingResponse])
def get_rankings(
    audit_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    ensure_audit_access(AuditService.get_audit(db, audit_id), current_user)
    service = RankTrackerService(db)
    return service.get_rankings(audit_id)
