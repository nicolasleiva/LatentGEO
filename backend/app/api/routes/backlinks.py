from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List
from ...core.database import get_db
from ...services.backlink_service import BacklinkService
from ...schemas import BacklinkResponse

router = APIRouter(prefix="/backlinks", tags=["backlinks"])

@router.post("/analyze/{audit_id}", response_model=List[BacklinkResponse])
async def analyze_backlinks(
    audit_id: int, 
    domain: str = Query(..., description="Domain to analyze"),
    db: Session = Depends(get_db)
):
    """Analyze backlinks for a given audit and domain"""
    service = BacklinkService(db)
    return await service.analyze_backlinks(audit_id, domain)

@router.get("/{audit_id}", response_model=List[BacklinkResponse])
def get_backlinks(audit_id: int, db: Session = Depends(get_db)):
    """Get stored backlinks for an audit"""
    service = BacklinkService(db)
    return service.get_backlinks(audit_id)
