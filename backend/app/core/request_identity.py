"""
Helpers for request identity resolution.
"""

from fastapi import Request


def get_client_ip(request: Request) -> str:
    """
    Returns the client IP resolved by ASGI/ProxyHeaders middleware.

    Security note:
    - Do not parse X-Forwarded-For manually here.
    - Proxy trust is configured at middleware/server level.
    """
    if request.client and request.client.host:
        return request.client.host
    return "unknown"
