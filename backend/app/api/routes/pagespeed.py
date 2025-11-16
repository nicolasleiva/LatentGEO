from fastapi import APIRouter, Query
from typing import Optional
from ...services.pagespeed_service import PageSpeedService
from ...core.config import settings

router = APIRouter(prefix="/api/pagespeed", tags=["pagespeed"])

@router.get("/analyze")
async def analyze_pagespeed(
    url: str = Query(..., description="URL to analyze"),
    strategy: str = Query("mobile", description="mobile or desktop")
):
    return await PageSpeedService.analyze_url(url, settings.GOOGLE_PAGESPEED_API_KEY, strategy)

@router.get("/compare")
async def compare_strategies(
    url: str = Query(..., description="URL to analyze")
):
    import asyncio
    mobile = await PageSpeedService.analyze_url(url, settings.GOOGLE_PAGESPEED_API_KEY, "mobile")
    await asyncio.sleep(3)
    desktop = await PageSpeedService.analyze_url(url, settings.GOOGLE_PAGESPEED_API_KEY, "desktop")
    return {"mobile": mobile, "desktop": desktop}
