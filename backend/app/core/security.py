"""
Funciones de seguridad para la aplicación
"""
import os
import re
from urllib.parse import urlparse
from typing import Optional

def validate_url(url: str) -> bool:
    """Validar URL y prevenir SSRF"""
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return False
    except Exception:
        return False
    
    # Prevenir SSRF
    blocked_hosts = [
        'localhost', '127.0.0.1', '0.0.0.0',
        '192.168', '10.0', '172.16',
        'metadata.google.internal',
        '169.254.169.254',
    ]
    
    for blocked in blocked_hosts:
        if blocked in url.lower():
            return False
    
    # Solo HTTP/HTTPS
    if not url.lower().startswith(('http://', 'https://')):
        return False
    
    return True

def validate_api_key(api_key: str) -> bool:
    """Validar API key"""
    if not re.match(r'^[a-zA-Z0-9\-_]+$', api_key):
        return False
    return len(api_key) >= 20 and len(api_key) <= 500

def sanitize_input(input_str: str, max_length: int = 1000) -> str:
    """Sanitizar entrada de usuario"""
    # Limitar longitud
    sanitized = input_str[:max_length]
    
    # Remover caracteres de control
    sanitized = re.sub(r'[\x00-\x1F\x7F]', '', sanitized)
    
    # Remover scripts
    sanitized = re.sub(r'<script[^>]*>.*?</script>', '', sanitized, flags=re.IGNORECASE)
    
    return sanitized.strip()

def validate_email(email: str) -> bool:
    """Validar email"""
    pattern = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
    return bool(re.match(pattern, email)) and len(email) <= 255
