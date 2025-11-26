from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from typing import List
from ...core.database import get_db
from ...services.rank_tracker_service import RankTrackerService
from ...schemas import RankTrackingResponse

router = APIRouter()

@router.post("/track/{audit_id}", response_model=List[RankTrackingResponse])
async def track_rankings(
    audit_id: int, 
    domain: str, 
    keywords: List[str] = Body(...),
    db: Session = Depends(get_db)
):
    service = RankTrackerService(db)
    return await service.track_rankings(audit_id, domain, keywords)

@router.get("/{audit_id}", response_model=List[RankTrackingResponse])
def get_rankings(audit_id: int, db: Session = Depends(get_db)):
    service = RankTrackerService(db)
    return service.get_rankings(audit_id)
