from typing import Any, Dict, List

from app.core.auth import AuthUser, get_current_user
from app.core.logger import get_logger
from app.services.content_editor_service import ContentEditorService
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/tools/content-editor", tags=["content-editor"])
service = ContentEditorService()
logger = get_logger(__name__)


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
async def analyze_content(
    request: AnalyzeRequest,
    _current_user: AuthUser = Depends(get_current_user),
):
    try:
        result = await service.analyze_content(request.text, request.keyword)
        return result
    except Exception:
        logger.exception("Content editor analyze failed")
        raise HTTPException(status_code=500, detail="Internal server error")
