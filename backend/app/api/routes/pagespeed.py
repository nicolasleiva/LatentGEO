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


def _raise_for_pagespeed_payload(payload: object) -> None:
    if not isinstance(payload, dict):
        return
    error = payload.get("error")
    if not isinstance(error, str) or not error.strip():
        return

    status_code = payload.get("status_code")
    provider_message = payload.get("provider_message")
    detail = (
        provider_message.strip()
        if isinstance(provider_message, str) and provider_message.strip()
        else error.strip()
    )
    normalized_error = error.strip().lower()

    if normalized_error == "timeout":
        raise HTTPException(
            status_code=504,
            detail=detail or "PageSpeed provider timed out before returning a result.",
        )
    if normalized_error.startswith("api error:"):
        raise HTTPException(
            status_code=(
                int(status_code)
                if isinstance(status_code, int) and 400 <= status_code <= 599
                else 502
            ),
            detail=detail,
        )
    raise HTTPException(
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
        payload = await PageSpeedService.analyze_url(
            url, settings.GOOGLE_PAGESPEED_API_KEY, strategy
        )
        _raise_for_pagespeed_payload(payload)
        return payload
    except HTTPException:
        raise
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
        _raise_for_pagespeed_payload(mobile)
        sleep_time = 0.5 if settings.GOOGLE_PAGESPEED_API_KEY else 3
        await asyncio.sleep(sleep_time)
        desktop = await PageSpeedService.analyze_url(
            url, settings.GOOGLE_PAGESPEED_API_KEY, "desktop"
        )
        _raise_for_pagespeed_payload(desktop)
        return {"mobile": mobile, "desktop": desktop}
    except HTTPException:
        raise
    except Exception as exc:
        raise _map_pagespeed_exception(exc) from exc
