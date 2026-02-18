from fastapi import APIRouter, Depends, HTTPException, Body, Query
from sqlalchemy.orm import Session
from typing import List
from ...core.database import get_db
from ...core.auth import AuthUser, get_current_user
from ...core.access_control import ensure_audit_access
from ...services.audit_service import AuditService
from ...services.llm_visibility_service import LLMVisibilityService
from ...core.llm_kimi import KimiUnavailableError, KimiGenerationError
from ...schemas import LLMVisibilityResponse

router = APIRouter(prefix="/llm-visibility", tags=["llm-visibility"])

@router.post("/check/{audit_id}", response_model=List[LLMVisibilityResponse])
async def check_visibility(
    audit_id: int, 
    brand_name: str = Query(..., description="Brand name to check visibility for"),
    queries: List[str] = Body(...),
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    try:
        ensure_audit_access(AuditService.get_audit(db, audit_id), current_user)
        service = LLMVisibilityService(db)
        return await service.check_visibility(audit_id, brand_name, queries)
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

@router.get("/{audit_id}", response_model=List[LLMVisibilityResponse])
def get_visibility(
    audit_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    ensure_audit_access(AuditService.get_audit(db, audit_id), current_user)
    service = LLMVisibilityService(db)
    return service.get_visibility(audit_id)
