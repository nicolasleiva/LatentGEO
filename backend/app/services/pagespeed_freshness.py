from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.logger import get_logger

logger = get_logger(__name__)


def is_pagespeed_stale(
    pagespeed_data: dict[str, Any] | None,
    *,
    max_age_hours: int = 24,
) -> bool:
    """Return True when PageSpeed data is missing, invalid, or older than the allowed age."""
    if not pagespeed_data:
        return True

    mobile_data = pagespeed_data.get("mobile", {})
    if not mobile_data or "error" in mobile_data:
        return True

    fetch_time = mobile_data.get("metadata", {}).get("fetch_time")
    if not fetch_time or not isinstance(fetch_time, str):
        if fetch_time is not None:
            logger.warning("PageSpeed fetch_time is not a string: %s", type(fetch_time))
        return True

    try:
        if fetch_time.endswith("Z"):
            fetch_datetime = datetime.fromisoformat(fetch_time.replace("Z", "+00:00"))
        else:
            fetch_datetime = datetime.fromisoformat(fetch_time)

        if fetch_datetime.tzinfo is None:
            fetch_datetime = fetch_datetime.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        age = now - fetch_datetime
        is_stale = age > timedelta(hours=max_age_hours)
        logger.info(
            "PageSpeed data age: %.1f hours, stale: %s",
            age.total_seconds() / 3600,
            is_stale,
        )
        return is_stale
    except Exception as exc:
        logger.warning("Error checking PageSpeed staleness: %s", exc)
        return True
