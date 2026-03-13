import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from ...core.auth import AuthUser, get_current_user
from ...core.config import settings
from ...services.pagespeed_service import PageSpeedService

router = APIRouter(prefix="/pagespeed", tags=["pagespeed"])
logger = logging.getLogger(__name__)

_PAGESPEED_TIMEOUT_DETAIL = "PageSpeed provider timed out before returning a result."
_PAGESPEED_UPSTREAM_DETAIL = (
    "PageSpeed provider returned an error while processing the request."
)
_PAGESPEED_GENERIC_DETAIL = (
    "PageSpeed analysis failed due to an upstream provider error."
)


_PAGESPEED_SENSITIVE_KEYS = {
    "error",
    "message",
    "public_message",
    "provider_message",
    "stack",
    "stack_trace",
    "trace",
    "traceback",
    "exception",
    "exc_info",
}


def _sanitize_pagespeed_payload(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, nested_value in value.items():
            if str(key).strip().lower() in _PAGESPEED_SENSITIVE_KEYS:
                continue
            sanitized[key] = _sanitize_pagespeed_payload(nested_value)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_pagespeed_payload(item) for item in value]
    return value


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
            detail=_PAGESPEED_TIMEOUT_DETAIL,
        )

    logger.exception("Unexpected PageSpeed failure.")
    return HTTPException(
        status_code=502,
        detail=_PAGESPEED_GENERIC_DETAIL,
    )


def _raise_for_pagespeed_payload(payload: object) -> None:
    if not isinstance(payload, dict):
        return
    error = payload.get("error")
    if not isinstance(error, str) or not error.strip():
        return

    status_code = payload.get("status_code")
    normalized_error = error.strip().lower()

    if normalized_error == "timeout":
        raise HTTPException(
            status_code=504,
            detail=_PAGESPEED_TIMEOUT_DETAIL,
        )
    if normalized_error.startswith("api error:"):
        raise HTTPException(
            status_code=(
                int(status_code)
                if isinstance(status_code, int) and 400 <= status_code <= 599
                else 502
            ),
            detail=_PAGESPEED_UPSTREAM_DETAIL,
        )
    raise HTTPException(
        status_code=502,
        detail=_PAGESPEED_GENERIC_DETAIL,
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
        return _sanitize_pagespeed_payload(payload)
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
        return {
            "mobile": _sanitize_pagespeed_payload(mobile),
            "desktop": _sanitize_pagespeed_payload(desktop),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise _map_pagespeed_exception(exc) from exc
