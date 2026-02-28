from fastapi import APIRouter, Depends, Query

from ...core.auth import AuthUser, get_current_user
from ...core.config import settings
from ...services.pagespeed_service import PageSpeedService

router = APIRouter(prefix="/pagespeed", tags=["pagespeed"])


@router.get("/analyze")
async def analyze_pagespeed(
    url: str = Query(..., description="URL to analyze"),
    strategy: str = Query("mobile", description="mobile or desktop"),
    _current_user: AuthUser = Depends(get_current_user),
):
    return await PageSpeedService.analyze_url(
        url, settings.GOOGLE_PAGESPEED_API_KEY, strategy
    )


@router.get("/compare")
async def compare_strategies(
    url: str = Query(..., description="URL to analyze"),
    _current_user: AuthUser = Depends(get_current_user),
):
    import asyncio

    mobile = await PageSpeedService.analyze_url(
        url, settings.GOOGLE_PAGESPEED_API_KEY, "mobile"
    )
    sleep_time = 0.5 if settings.GOOGLE_PAGESPEED_API_KEY else 3
    await asyncio.sleep(sleep_time)
    desktop = await PageSpeedService.analyze_url(
        url, settings.GOOGLE_PAGESPEED_API_KEY, "desktop"
    )
    return {"mobile": mobile, "desktop": desktop}
