import json

import redis
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

# Conexión persistente a Redis
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)


def publish_audit_update(audit_id: int, data: dict):
    """Publica una actualización de auditoría en el canal de Redis."""
    try:
        channel = f"audit_updates_{audit_id}"
        redis_client.publish(channel, json.dumps(data))
    except Exception as e:
        logger.error(f"Error publishing to Redis: {e}")
