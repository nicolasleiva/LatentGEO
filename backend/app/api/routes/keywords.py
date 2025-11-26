from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from typing import List, Optional
from ...core.database import get_db
from ...services.keyword_service import KeywordService
from ...schemas import KeywordResponse

router = APIRouter()

@router.post("/research/{audit_id}", response_model=List[KeywordResponse])
async def research_keywords(
    audit_id: int, 
    domain: str, 
    seed_keywords: Optional[List[str]] = Body(None),
    db: Session = Depends(get_db)
):
    service = KeywordService(db)
    return await service.research_keywords(audit_id, domain, seed_keywords)

@router.get("/{audit_id}", response_model=List[KeywordResponse])
def get_keywords(audit_id: int, db: Session = Depends(get_db)):
    service = KeywordService(db)
    return service.get_keywords(audit_id)
