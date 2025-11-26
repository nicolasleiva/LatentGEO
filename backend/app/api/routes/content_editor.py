from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from app.services.content_editor_service import ContentEditorService

router = APIRouter()
service = ContentEditorService()

class AnalyzeRequest(BaseModel):
    text: str
    keyword: str

class AnalyzeResponse(BaseModel):
    score: int
    summary: str
    pillars: Dict[str, Any]
    suggestions: List[Dict[str, str]]
    missing_entities: List[str]

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_content(request: AnalyzeRequest):
    try:
        result = await service.analyze_content(request.text, request.keyword)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
