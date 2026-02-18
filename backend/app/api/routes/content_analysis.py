from typing import Dict, List

from fastapi import APIRouter, HTTPException, Query

from ...services.crawler_service import CrawlerService
from ...services.duplicate_content_service import DuplicateContentService
from ...services.keyword_gap_service import KeywordGapService

router = APIRouter(prefix="/content", tags=["content"])


@router.post("/duplicates")
async def find_duplicates(
    pages: List[Dict], threshold: float = Query(0.85, ge=0.0, le=1.0)
):
    """Encuentra contenido duplicado entre páginas"""
    return {"duplicates": DuplicateContentService.find_duplicates(pages, threshold)}


@router.post("/keywords/extract")
async def extract_keywords(html: str, top_n: int = Query(50, ge=1, le=200)):
    """Extrae keywords de HTML"""
    return {"keywords": KeywordGapService.extract_keywords(html, top_n)}


@router.post("/keywords/gap")
async def analyze_keyword_gap(
    your_keywords: List[Dict], competitor_keywords: List[Dict]
):
    """Analiza gap de keywords"""
    return KeywordGapService.analyze_gap(your_keywords, competitor_keywords)


@router.get("/keywords/compare")
async def compare_keywords(your_url: str, competitor_url: str):
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
