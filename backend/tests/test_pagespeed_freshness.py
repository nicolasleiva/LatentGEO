from datetime import datetime, timedelta, timezone

from app.services.pagespeed_freshness import is_pagespeed_stale


def _fetch_time(hours_ago: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()


def test_is_pagespeed_stale_accepts_desktop_only_payload():
    payload = {
        "desktop": {
            "metadata": {
                "fetch_time": _fetch_time(1),
            }
        }
    }

    assert is_pagespeed_stale(payload, max_age_hours=24) is False


def test_is_pagespeed_stale_ignores_malformed_strategy_payloads():
    payload = {
        "mobile": ["malformed"],
        "desktop": {
            "metadata": {
                "fetch_time": _fetch_time(2),
            }
        },
    }

    assert is_pagespeed_stale(payload, max_age_hours=24) is False


def test_is_pagespeed_stale_uses_oldest_valid_strategy_timestamp():
    payload = {
        "mobile": {
            "metadata": {
                "fetch_time": _fetch_time(2),
            }
        },
        "desktop": {
            "metadata": {
                "fetch_time": _fetch_time(30),
            }
        },
    }

    assert is_pagespeed_stale(payload, max_age_hours=24) is True
