from __future__ import annotations

import sys
import time

from sqlalchemy.exc import OperationalError

from app.core.config import settings
from app.core.database import run_migrations_to_head
from app.core.logger import get_logger

logger = get_logger(__name__)


def main() -> int:
    retries = max(1, int(getattr(settings, "DB_RETRIES", 5)))
    retry_delay = max(1, int(getattr(settings, "DB_RETRY_DELAY", 3)))
    last_error: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            revision = run_migrations_to_head()
            logger.info(
                "Database migrations completed successfully at revision %s.",
                revision,
            )
            return 0
        except OperationalError as exc:
            last_error = exc
            logger.warning(
                "Migration attempt %s/%s failed due to transient DB connectivity: %s",
                attempt,
                retries,
                exc,
            )
        except Exception as exc:
            last_error = exc
            logger.warning(
                "Migration attempt %s/%s failed: %s",
                attempt,
                retries,
                exc,
            )

        if attempt < retries:
            time.sleep(retry_delay)

    logger.error("Database migrations failed after %s attempts.", retries)
    if last_error is not None:
        logger.error("Last migration error: %s", last_error)
    return 1


if __name__ == "__main__":
    sys.exit(main())
