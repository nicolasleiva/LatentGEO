from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.logger import get_logger

logger = get_logger(__name__)


def _collect_candidate_fetch_times(pagespeed_data: dict[str, Any]) -> list[str]:
    candidate_fetch_times: list[str] = []

    for strategy in ("mobile", "desktop"):
        payload = pagespeed_data.get(strategy)
        if not isinstance(payload, dict) or not payload or payload.get("error"):
            continue

        metadata = payload.get("metadata")
        if not isinstance(metadata, dict):
            if metadata is not None:
                logger.warning(
                    "PageSpeed metadata for %s is not a mapping: %s",
                    strategy,
                    type(metadata),
                )
            continue

        fetch_time = metadata.get("fetch_time")
        if isinstance(fetch_time, str) and fetch_time.strip():
            candidate_fetch_times.append(fetch_time.strip())
            continue
        if fetch_time is not None:
            logger.warning(
                "PageSpeed fetch_time for %s is not a string: %s",
                strategy,
                type(fetch_time),
            )

    return candidate_fetch_times


def is_pagespeed_stale(
    pagespeed_data: dict[str, Any] | None,
    *,
    max_age_hours: int = 24,
) -> bool:
    """Return True when PageSpeed data is missing, invalid, or older than the allowed age."""
    if not isinstance(pagespeed_data, dict) or not pagespeed_data:
        return True

    candidate_fetch_times = _collect_candidate_fetch_times(pagespeed_data)
    if not candidate_fetch_times:
        return True

    try:
        fetch_datetimes: list[datetime] = []
        for fetch_time in candidate_fetch_times:
            if fetch_time.endswith("Z"):
                fetch_datetime = datetime.fromisoformat(
                    fetch_time.replace("Z", "+00:00")
                )
            else:
                fetch_datetime = datetime.fromisoformat(fetch_time)

            if fetch_datetime.tzinfo is None:
                fetch_datetime = fetch_datetime.replace(tzinfo=timezone.utc)
            fetch_datetimes.append(fetch_datetime)
        if not fetch_datetimes:
            return True

        now = datetime.now(timezone.utc)
        age = now - max(fetch_datetimes)
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
