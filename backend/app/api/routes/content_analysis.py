from typing import Any, Dict, List

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from ...core.auth import AuthUser, get_current_user
from ...services.crawler_service import CrawlerService
from ...services.duplicate_content_service import DuplicateContentService
from ...services.keyword_gap_service import KeywordGapService

router = APIRouter(prefix="/content", tags=["content"])


@router.post("/duplicates")
async def find_duplicates(
    pages: List[Dict],
    threshold: float = Query(0.85, ge=0.0, le=1.0),
    _current_user: AuthUser = Depends(get_current_user),
):
    """Encuentra contenido duplicado entre páginas"""
    return {"duplicates": DuplicateContentService.find_duplicates(pages, threshold)}


@router.post("/keywords/extract")
async def extract_keywords(
    payload: Any = Body(default=None),
    html: str | None = Query(default=None),
    top_n: int = Query(50, ge=1, le=200),
    _current_user: AuthUser = Depends(get_current_user),
):
    """Extrae keywords de HTML"""
    body_html: str | None = None
    body_top_n: int | None = None

    if isinstance(payload, str):
        body_html = payload
    elif isinstance(payload, dict):
        candidate = payload.get("html")
        body_html = str(candidate) if candidate is not None else None
        if payload.get("top_n") is not None:
            try:
                body_top_n = int(payload["top_n"])
            except (TypeError, ValueError) as exc:
                raise HTTPException(status_code=422, detail="top_n must be an integer") from exc

    resolved_html = (body_html or html or "").strip()
    if not resolved_html:
        raise HTTPException(status_code=422, detail="html is required")

    resolved_top_n = body_top_n if body_top_n is not None else top_n
    if resolved_top_n < 1 or resolved_top_n > 200:
        raise HTTPException(status_code=422, detail="top_n must be between 1 and 200")

    return {
        "keywords": KeywordGapService.extract_keywords(
            resolved_html,
            resolved_top_n,
        )
    }


@router.post("/keywords/gap")
async def analyze_keyword_gap(
    your_keywords: List[Dict],
    competitor_keywords: List[Dict],
    _current_user: AuthUser = Depends(get_current_user),
):
    """Analiza gap de keywords"""
    return KeywordGapService.analyze_gap(your_keywords, competitor_keywords)


@router.get("/keywords/compare")
async def compare_keywords(
    your_url: str,
    competitor_url: str,
    _current_user: AuthUser = Depends(get_current_user),
):
    """Compara keywords entre dos URLs"""
    your_html = await CrawlerService.get_page_content(your_url)
    comp_html = await CrawlerService.get_page_content(competitor_url)

    if not your_html or not comp_html:
        raise HTTPException(400, "No se pudo obtener el contenido")

    your_kw = KeywordGapService.extract_keywords(your_html)
    comp_kw = KeywordGapService.extract_keywords(comp_html)

    gap = KeywordGapService.analyze_gap(your_kw, comp_kw)

    return {
        "your_keywords": your_kw[:20],
        "competitor_keywords": comp_kw[:20],
        "gap_analysis": gap,
    }
