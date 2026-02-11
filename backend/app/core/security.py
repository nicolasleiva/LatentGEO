"""
Funciones de seguridad para la aplicación
"""

import os
import re
from urllib.parse import urlparse
from typing import Optional


def normalize_url(url: str) -> str:
    """
    Normaliza una URL a formato completo con esquema HTTP/HTTPS.

    Convierte:
    - dominio.com → https://www.dominio.com
    - www.dominio.com → https://www.dominio.com
    - http://dominio.com → https://www.dominio.com
    - https://dominio.com → https://www.dominio.com

    Args:
        url: URL a normalizar

    Returns:
        URL normalizada con https:// y www.
    """
    if not url:
        return ""

    url = url.strip().lower()

    parsed = urlparse(url)
    if not parsed.scheme:
        parsed = urlparse(f"https://{url}")

    scheme = (parsed.scheme or "https").lower()
    if scheme not in ("http", "https"):
        scheme = "https"

    netloc = (parsed.netloc or "").lower()
    path = parsed.path or ""

    normalized = parsed._replace(scheme=scheme, netloc=netloc).geturl()

    # Asegurar que termine en / para dominios base
    if not path:
        normalized = normalized.rstrip("/") + "/"

    return normalized


def validate_url(url: str) -> bool:
    """Validar URL y prevenir SSRF. Acepta URLs con o sin https://"""
    try:
        # Primero normalizar la URL
        normalized = normalize_url(url)
        if not normalized:
            return False

        parsed = urlparse(normalized)
        if not parsed.scheme or not parsed.netloc:
            return False
    except Exception:
        return False

    # Prevenir SSRF
    blocked_hosts = [
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        "192.168",
        "10.0",
        "172.16",
        "metadata.google.internal",
        "169.254.169.254",
    ]

    for blocked in blocked_hosts:
        if blocked in normalized.lower():
            return False

    # Solo HTTP/HTTPS
    if not normalized.lower().startswith(("http://", "https://")):
        return False

    return True


def validate_api_key(api_key: str) -> bool:
    """Validar API key"""
    if not re.match(r"^[a-zA-Z0-9\-_]+$", api_key):
        return False
    return len(api_key) >= 20 and len(api_key) <= 500


def sanitize_input(input_str: str, max_length: int = 1000) -> str:
    """Sanitizar entrada de usuario"""
    # Limitar longitud
    sanitized = input_str[:max_length]

    # Remover caracteres de control
    sanitized = re.sub(r"[\x00-\x1F\x7F]", "", sanitized)

    # Remover scripts
    sanitized = re.sub(r"<script[^>]*>.*?</script>", "", sanitized, flags=re.IGNORECASE)

    return sanitized.strip()


def validate_email(email: str) -> bool:
    """Validar email"""
    pattern = r"^[^\s@]+@[^\s@]+\.[^\s@]+$"
    return bool(re.match(pattern, email)) and len(email) <= 255
