"""
Funciones de seguridad para la aplicación
"""

import ipaddress
import re
from urllib.parse import urlparse


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

        hostname = (parsed.hostname or "").lower()
        if not hostname:
            return False
    except Exception:
        return False

    # Prevenir SSRF: hostnames sensibles y endpoints metadata
    blocked_hostnames = {
        "localhost",
        "metadata.google.internal",
        "169.254.169.254",
    }
    if hostname in blocked_hostnames:
        return False
    if hostname.endswith(".internal") or hostname.endswith(".local"):
        return False

    # Bloqueo por IP privada/loopback/link-local/unspecified/reserved
    try:
        ip = ipaddress.ip_address(hostname.strip("[]"))
    except ValueError:
        # Hostname textual: bloquear patrones de redes internas evidentes.
        if re.match(r"^(127\.|10\.|192\.168\.|172\.(1[6-9]|2\d|3[0-1])\.)", hostname):
            return False
    else:
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_unspecified
            or ip.is_reserved
            or ip.is_multicast
        ):
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
