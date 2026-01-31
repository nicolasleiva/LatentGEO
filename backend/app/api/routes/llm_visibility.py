from fastapi import APIRouter, Depends, HTTPException, Body, Query
from sqlalchemy.orm import Session
from typing import List
from ...core.database import get_db
from ...services.llm_visibility_service import LLMVisibilityService
from ...schemas import LLMVisibilityResponse

router = APIRouter(prefix="/llm-visibility", tags=["llm-visibility"])

@router.post("/check/{audit_id}", response_model=List[LLMVisibilityResponse])
async def check_visibility(
    audit_id: int, 
    brand_name: str = Query(..., description="Brand name to check visibility for"),
    queries: List[str] = Body(...),
    db: Session = Depends(get_db)
):
    service = LLMVisibilityService(db)
    return await service.check_visibility(audit_id, brand_name, queries)

@router.get("/{audit_id}", response_model=List[LLMVisibilityResponse])
def get_visibility(audit_id: int, db: Session = Depends(get_db)):
    service = LLMVisibilityService(db)
    return service.get_visibility(audit_id)
