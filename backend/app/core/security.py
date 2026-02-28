"""
Funciones de seguridad para la aplicación
"""

import ipaddress
import re
import socket
from typing import Optional, Set, Union
from urllib.parse import urlparse

import bleach  # type: ignore[import-untyped]
from bs4 import BeautifulSoup

_DEFAULT_ALLOWED_OUTBOUND_PORTS: Set[int] = {80, 443}
_BLOCKED_HOSTNAMES = {
    "localhost",
    "metadata.google.internal",
    "metadata.google",
    "169.254.169.254",
    "100.100.100.200",
}
_BLOCKED_SUFFIXES = (".internal", ".local")
_SAFE_HTML_TAGS = [
    "p",
    "br",
    "ul",
    "ol",
    "li",
    "strong",
    "em",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "code",
    "pre",
    "a",
]
_SAFE_HTML_ATTRIBUTES = {"a": ["href", "title", "rel", "target"]}
_SAFE_HTML_PROTOCOLS = ["http", "https", "mailto"]
IPAddress = Union[ipaddress.IPv4Address, ipaddress.IPv6Address]


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


def normalize_outbound_url(url: str) -> str:
    """
    Normaliza URL para requests salientes.

    - Si no hay esquema, asume https://
    - Elimina fragment
    """
    if not url:
        return ""

    candidate = url.strip()
    parsed = urlparse(candidate)
    if not parsed.scheme:
        parsed = urlparse(f"https://{candidate}")

    if parsed.scheme.lower() not in ("http", "https"):
        return ""
    if not parsed.hostname:
        return ""

    return parsed._replace(fragment="").geturl()


def _is_blocked_ip(ip: IPAddress) -> bool:
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_unspecified
        or ip.is_reserved
        or ip.is_multicast
    )


def _resolve_host_ips(hostname: str, port: int) -> Set[IPAddress]:
    resolved_ips: Set[IPAddress] = set()
    for family, _, _, _, sockaddr in socket.getaddrinfo(
        hostname, port, type=socket.SOCK_STREAM
    ):
        ip_str = sockaddr[0]
        ip_obj = ipaddress.ip_address(ip_str)
        # family check retained for clarity in mixed stacks
        if family in (socket.AF_INET, socket.AF_INET6):
            resolved_ips.add(ip_obj)
    return resolved_ips


def is_safe_outbound_url(
    url: str, allowed_ports: Optional[Set[int]] = None, allow_http: bool = True
) -> bool:
    """
    Valida URL para requests salientes (SSRF hardening):
    - esquema permitido
    - sin userinfo
    - puertos permitidos
    - bloqueo de hosts internos/metadata
    - resolución DNS y bloqueo de IPs privadas/reservadas
    """
    normalized = normalize_outbound_url(url)
    if not normalized:
        return False

    try:
        parsed = urlparse(normalized)
        scheme = (parsed.scheme or "").lower()
        if scheme not in {"https", "http"}:
            return False
        if scheme == "http" and not allow_http:
            return False

        if parsed.username or parsed.password:
            return False

        hostname = (parsed.hostname or "").strip().lower()
        if not hostname:
            return False

        if hostname in _BLOCKED_HOSTNAMES:
            return False
        if hostname.endswith(_BLOCKED_SUFFIXES):
            return False

        port = parsed.port or (443 if scheme == "https" else 80)
        allowed = allowed_ports or _DEFAULT_ALLOWED_OUTBOUND_PORTS
        if port not in allowed:
            return False

        try:
            ip_obj = ipaddress.ip_address(hostname.strip("[]"))
        except ValueError:
            try:
                resolved_ips = _resolve_host_ips(hostname, port)
            except OSError:
                return False
            if not resolved_ips:
                return False
            if any(_is_blocked_ip(ip) for ip in resolved_ips):
                return False
        else:
            if _is_blocked_ip(ip_obj):
                return False

        return True
    except Exception:
        return False


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

    sanitized = sanitize_html_content(sanitized, max_length=max_length)

    return sanitized.strip()


def sanitize_html_content(input_html: str, max_length: int = 50000) -> str:
    """
    Sanitiza HTML con allowlist estricta.
    Usa parser para remover tags peligrosas y bleach para limpieza final.
    """
    if not input_html:
        return ""

    sanitized = str(input_html)[:max_length]
    soup = BeautifulSoup(sanitized, "html.parser")

    for tag in soup.find_all(
        ["script", "style", "iframe", "object", "embed", "svg", "math"]
    ):
        tag.decompose()

    for tag in soup.find_all(True):
        for attr_name in list(tag.attrs):
            if str(attr_name).lower().startswith("on"):
                del tag.attrs[attr_name]

    cleaned = bleach.clean(
        str(soup),
        tags=_SAFE_HTML_TAGS,
        attributes=_SAFE_HTML_ATTRIBUTES,
        protocols=_SAFE_HTML_PROTOCOLS,
        strip=True,
        strip_comments=True,
    )
    return cleaned.strip()


def validate_email(email: str) -> bool:
    """Validar email"""
    pattern = r"^[^\s@]+@[^\s@]+\.[^\s@]+$"
    return bool(re.match(pattern, email)) and len(email) <= 255
