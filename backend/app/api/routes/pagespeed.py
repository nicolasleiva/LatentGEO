import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from ...core.auth import AuthUser, get_current_user
from ...core.config import settings
from ...services.pagespeed_service import PageSpeedService

router = APIRouter(prefix="/pagespeed", tags=["pagespeed"])
logger = logging.getLogger(__name__)


def _map_pagespeed_exception(exc: Exception) -> HTTPException:
    if isinstance(exc, ValueError):
        logger.warning("PageSpeed requested while provider is unavailable: %s", exc)
        return HTTPException(
            status_code=503,
            detail="PageSpeed is unavailable because the provider is not configured.",
        )
    if isinstance(exc, TimeoutError):
        logger.warning("PageSpeed provider timed out: %s", exc)
        return HTTPException(
            status_code=504,
            detail="PageSpeed provider timed out before returning a result.",
        )

    logger.exception("Unexpected PageSpeed failure.")
    return HTTPException(
        status_code=502,
        detail="PageSpeed analysis failed due to an upstream provider error.",
    )


@router.get("/analyze")
async def analyze_pagespeed(
    url: str = Query(..., description="URL to analyze"),
    strategy: str = Query("mobile", description="mobile or desktop"),
    _current_user: AuthUser = Depends(get_current_user),
):
    try:
        return await PageSpeedService.analyze_url(
            url, settings.GOOGLE_PAGESPEED_API_KEY, strategy
        )
    except Exception as exc:
        raise _map_pagespeed_exception(exc) from exc


@router.get("/compare")
async def compare_strategies(
    url: str = Query(..., description="URL to analyze"),
    _current_user: AuthUser = Depends(get_current_user),
):
    import asyncio

    try:
        mobile = await PageSpeedService.analyze_url(
            url, settings.GOOGLE_PAGESPEED_API_KEY, "mobile"
        )
        sleep_time = 0.5 if settings.GOOGLE_PAGESPEED_API_KEY else 3
        await asyncio.sleep(sleep_time)
        desktop = await PageSpeedService.analyze_url(
            url, settings.GOOGLE_PAGESPEED_API_KEY, "desktop"
        )
        return {"mobile": mobile, "desktop": desktop}
    except Exception as exc:
        raise _map_pagespeed_exception(exc) from exc
