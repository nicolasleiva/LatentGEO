from typing import List

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ...core.access_control import ensure_audit_access
from ...core.auth import AuthUser, get_current_user
from ...core.database import get_db
from ...core.llm_kimi import KimiGenerationError, KimiUnavailableError
from ...schemas import AIContentSuggestionResponse
from ...services.ai_content_service import AIContentService
from ...services.audit_service import AuditService

router = APIRouter(prefix="/ai-content", tags=["ai-content"])


@router.post("/generate/{audit_id}", response_model=List[AIContentSuggestionResponse])
async def generate_suggestions(
    audit_id: int,
    domain: str = Query(..., description="Domain to generate content for"),
    topics: List[str] = Body(...),
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    try:
        ensure_audit_access(AuditService.get_audit(db, audit_id), current_user)
        service = AIContentService(db)
        return await service.generate_suggestions(audit_id, domain, topics)
    except HTTPException:
        raise
    except KimiUnavailableError:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "KIMI_UNAVAILABLE",
                "message": "Kimi provider is not configured. Set NV_API_KEY_ANALYSIS or NVIDIA_API_KEY or NV_API_KEY.",
            },
        )
    except KimiGenerationError as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "code": "KIMI_GENERATION_FAILED",
                "message": str(exc),
            },
        )


@router.get("/{audit_id}", response_model=List[AIContentSuggestionResponse])
def get_suggestions(
    audit_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    ensure_audit_access(AuditService.get_audit(db, audit_id), current_user)
    service = AIContentService(db)
    return service.get_suggestions(audit_id)
