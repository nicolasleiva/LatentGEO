from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from typing import List
from ...core.database import get_db
from ...services.ai_content_service import AIContentService
from ...schemas import AIContentSuggestionResponse

router = APIRouter()

@router.post("/generate/{audit_id}", response_model=List[AIContentSuggestionResponse])
async def generate_suggestions(
    audit_id: int, 
    domain: str, 
    topics: List[str] = Body(...),
    db: Session = Depends(get_db)
):
    service = AIContentService(db)
    return await service.generate_suggestions(audit_id, domain, topics)

@router.get("/{audit_id}", response_model=List[AIContentSuggestionResponse])
def get_suggestions(audit_id: int, db: Session = Depends(get_db)):
    service = AIContentService(db)
    return service.get_suggestions(audit_id)
