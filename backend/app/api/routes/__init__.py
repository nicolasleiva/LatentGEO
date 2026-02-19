"""
API Routes - Production Ready
All routes are imported with error handling to prevent single module failures from breaking the app.
"""

from app.core.logger import get_logger

# Core routes (always available)
from . import analytics, audits, health, pagespeed, realtime, reports, search, sse

logger = get_logger(__name__)

# Feature routes (may have optional dependencies)
try:
    from . import content_analysis
except ImportError as e:
    content_analysis = None
    logger.warning(f"content_analysis module not available: {e}")

try:
    from . import geo
except ImportError as e:
    geo = None
    logger.warning(f"geo module not available: {e}")

try:
    from . import hubspot
except ImportError as e:
    hubspot = None
    logger.warning(f"hubspot module not available: {e}")

try:
    from . import github
except ImportError as e:
    github = None
    logger.warning(f"github module not available: {e}")

try:
    from . import webhooks
except ImportError as e:
    webhooks = None
    logger.warning(f"webhooks module not available: {e}")

# Import GEO tools separately to avoid one failure affecting all
try:
    from . import backlinks
except ImportError as e:
    backlinks = None
    logger.warning(f"backlinks module not available: {e}")

try:
    from . import keywords
except ImportError as e:
    keywords = None
    logger.warning(f"keywords module not available: {e}")

try:
    from . import rank_tracking
except ImportError as e:
    rank_tracking = None
    logger.warning(f"rank_tracking module not available: {e}")

try:
    from . import llm_visibility
except ImportError as e:
    llm_visibility = None
    logger.warning(f"llm_visibility module not available: {e}")

try:
    from . import ai_content
except ImportError as e:
    ai_content = None
    logger.warning(f"ai_content module not available: {e}")

try:
    from . import content_editor
except ImportError as e:
    content_editor = None
    logger.warning(f"content_editor module not available: {e}")

__all__ = [
    "audits",
    "reports",
    "analytics",
    "health",
    "search",
    "pagespeed",
    "realtime",
    "sse",
    "content_analysis",
    "geo",
    "hubspot",
    "github",
    "webhooks",
    "backlinks",
    "keywords",
    "rank_tracking",
    "llm_visibility",
    "ai_content",
    "content_editor",
]
