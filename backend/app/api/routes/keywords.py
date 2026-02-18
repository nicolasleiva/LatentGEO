from fastapi import APIRouter, Depends, HTTPException, Body, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from ...core.database import get_db
from ...core.auth import AuthUser, get_current_user
from ...core.access_control import ensure_audit_access
from ...services.audit_service import AuditService
from ...services.keyword_service import KeywordService
from ...core.llm_kimi import KimiUnavailableError, KimiGenerationError
from ...schemas import KeywordResponse

router = APIRouter(prefix="/keywords", tags=["keywords"])

@router.post("/research/{audit_id}", response_model=List[KeywordResponse])
async def research_keywords(
    audit_id: int, 
    domain: str = Query(..., description="Domain to research keywords for"),
    seed_keywords: Optional[List[str]] = Body(None),
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    try:
        ensure_audit_access(AuditService.get_audit(db, audit_id), current_user)
        service = KeywordService(db)
        return await service.research_keywords(audit_id, domain, seed_keywords)
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

@router.get("/{audit_id}", response_model=List[KeywordResponse])
def get_keywords(
    audit_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    ensure_audit_access(AuditService.get_audit(db, audit_id), current_user)
    service = KeywordService(db)
    return service.get_keywords(audit_id)
