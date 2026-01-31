"""
Esquemas Pydantic con validadores de seguridad - Production Ready
"""
import re
import html
from typing import Optional, List
from urllib.parse import urlparse
from pydantic import BaseModel, Field, field_validator, model_validator
from app.core.security import validate_url, validate_api_key, validate_email


class URLInput(BaseModel):
    """Validate URLs with SSRF prevention"""
    url: str = Field(..., min_length=10, max_length=2048)
    
    @field_validator('url')
    @classmethod
    def validate_url_field(cls, v):
        if not validate_url(v):
            raise ValueError('URL inválida o no permitida (posible SSRF)')
        
        # Additional checks
        parsed = urlparse(v)
        
        # Block internal IP ranges
        if parsed.hostname:
            hostname = parsed.hostname.lower()
            
            # Block localhost variations
            blocked_hostnames = [
                'localhost', '127.0.0.1', '0.0.0.0',
                '[::1]', '::1', '[0:0:0:0:0:0:0:1]'
            ]
            if hostname in blocked_hostnames:
                raise ValueError('URLs internas no permitidas')
            
            # Block internal IP ranges
            if hostname.startswith(('192.168.', '10.', '172.16.', '172.17.',
                                   '172.18.', '172.19.', '172.20.', '172.21.',
                                   '172.22.', '172.23.', '172.24.', '172.25.',
                                   '172.26.', '172.27.', '172.28.', '172.29.',
                                   '172.30.', '172.31.')):
                raise ValueError('URLs de red interna no permitidas')
            
            # Block cloud metadata endpoints
            metadata_endpoints = [
                '169.254.169.254',  # AWS/GCP/Azure metadata
                'metadata.google.internal',
                'metadata.google',
                '100.100.100.200'  # Alibaba Cloud metadata
            ]
            if hostname in metadata_endpoints:
                raise ValueError('URLs de metadata de cloud no permitidas')
        
        return v


class APIKeyInput(BaseModel):
    """Validate API keys with format checking"""
    api_key: str = Field(..., min_length=20, max_length=500)
    
    @field_validator('api_key')
    @classmethod
    def validate_api_key_field(cls, v):
        if not validate_api_key(v):
            raise ValueError('API Key inválida')
        
        # Check for common placeholder values
        placeholder_patterns = [
            r'^sk-[x]{10,}$',  # sk-xxxxxxxxxxxx
            r'^test[_-]?key',  # testkey, test-key
            r'^your[_-]?api[_-]?key',  # your-api-key
            r'^api[_-]?key[_-]?here',  # api-key-here
            r'^xxx+$',  # xxxxxxxx
            r'^placeholder',
            r'^changeme',
            r'^TODO',
        ]
        
        for pattern in placeholder_patterns:
            if re.match(pattern, v, re.IGNORECASE):
                raise ValueError('API Key parece ser un placeholder')
        
        return v


class EmailInput(BaseModel):
    """Validate emails with format and domain checking"""
    email: str = Field(..., min_length=5, max_length=255)
    
    @field_validator('email')
    @classmethod
    def validate_email_field(cls, v):
        if not validate_email(v):
            raise ValueError('Email inválido')
        
        # Normalize to lowercase
        v = v.lower().strip()
        
        # Block disposable email domains (sample list)
        disposable_domains = [
            'mailinator.com', 'guerrillamail.com', '10minutemail.com',
            'trashmail.com', 'tempmail.com', 'throwaway.email',
            'maildrop.cc', 'getnada.com'
        ]
        
        domain = v.split('@')[-1]
        if domain in disposable_domains:
            raise ValueError('Emails desechables no permitidos')
        
        return v


class PasswordInput(BaseModel):
    """Validate passwords with strength requirements"""
    password: str = Field(..., min_length=8, max_length=128)
    
    @field_validator('password')
    @classmethod
    def validate_password_field(cls, v):
        if not any(c.isupper() for c in v):
            raise ValueError('Debe contener al menos una mayúscula')
        if not any(c.islower() for c in v):
            raise ValueError('Debe contener al menos una minúscula')
        if not any(c.isdigit() for c in v):
            raise ValueError('Debe contener al menos un número')
        if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in v):
            raise ValueError('Debe contener al menos un carácter especial')
        
        # Check for common weak passwords
        weak_passwords = [
            'password', 'qwerty', '123456', 'admin',
            'letmein', 'welcome', 'monkey', 'master'
        ]
        
        # Clean password for weaker version check (remove common symbols/numbers if at the end)
        clean_v = re.sub(r'[!@#$%^&*()_+\-=\[\]{}|;:,.<>?0-9]+$', '', v.lower())
        
        if v.lower() in weak_passwords or clean_v in weak_passwords:
            raise ValueError('Contraseña demasiado común')
        
        return v


class HTMLContent(BaseModel):
    """Sanitize HTML content to prevent XSS"""
    content: str = Field(..., max_length=50000)
    allow_basic_formatting: bool = Field(default=True)
    
    @field_validator('content')
    @classmethod
    def sanitize_html(cls, v):
        # Remove script tags and their contents
        v = re.sub(r'<script[^>]*>.*?</script>', '', v, flags=re.DOTALL | re.IGNORECASE)
        
        # Remove event handlers
        v = re.sub(r'\s+on\w+\s*=\s*["\'][^"\']*["\']', '', v, flags=re.IGNORECASE)
        v = re.sub(r'\s+on\w+\s*=\s*[^\s>]+', '', v, flags=re.IGNORECASE)
        
        # Remove javascript: urls
        v = re.sub(r'javascript:', '', v, flags=re.IGNORECASE)
        v = re.sub(r'vbscript:', '', v, flags=re.IGNORECASE)
        v = re.sub(r'data:text/html', '', v, flags=re.IGNORECASE)
        
        # Remove style tags (can be used for CSS injection)
        v = re.sub(r'<style[^>]*>.*?</style>', '', v, flags=re.DOTALL | re.IGNORECASE)
        
        # Remove iframe, embed, object tags
        v = re.sub(r'<iframe[^>]*>.*?</iframe>', '', v, flags=re.DOTALL | re.IGNORECASE)
        v = re.sub(r'<embed[^>]*/?>', '', v, flags=re.IGNORECASE)
        v = re.sub(r'<object[^>]*>.*?</object>', '', v, flags=re.DOTALL | re.IGNORECASE)
        
        return v.strip()


class WebhookURLInput(BaseModel):
    """Validate webhook destination URLs"""
    url: str = Field(..., min_length=10, max_length=2048)
    secret: Optional[str] = Field(None, min_length=16, max_length=256)
    
    @field_validator('url')
    @classmethod
    def validate_webhook_url(cls, v):
        parsed = urlparse(v)
        
        # Must be HTTPS in production (allow HTTP for localhost in dev)
        allowed_schemes = ['https']
        if parsed.hostname in ['localhost', '127.0.0.1']:
            allowed_schemes.append('http')
        
        if parsed.scheme not in allowed_schemes:
            raise ValueError('Webhook URL debe usar HTTPS')
        
        # Validate URL format
        if not validate_url(v):
            raise ValueError('Webhook URL inválida')
        
        return v


class AuditRequestInput(BaseModel):
    """Validate audit request input with security checks"""
    url: str = Field(..., min_length=10, max_length=2048)
    max_pages: int = Field(default=100, ge=1, le=500)
    language: str = Field(default="es", pattern=r'^(es|en|pt|fr|de)$')
    competitors: Optional[List[str]] = Field(default=None, max_length=10)
    market: Optional[str] = Field(default=None, max_length=50)
    
    @field_validator('url')
    @classmethod
    def validate_audit_url(cls, v):
        if not validate_url(v):
            raise ValueError('URL inválida para auditoría')
        return v
    
    @field_validator('competitors')
    @classmethod
    def validate_competitors(cls, v):
        if v is None:
            return v
        
        validated = []
        for url in v:
            if not validate_url(url):
                raise ValueError(f'URL de competidor inválida: {url}')
            validated.append(url)
        
        return validated
    
    @field_validator('market')
    @classmethod
    def validate_market_field(cls, v):
        return validate_market(v)

def validate_market(v: Optional[str]) -> Optional[str]:
    """Standalone market validator for use in other schemas"""
    if v is None:
        return v
    # Sanitize market input
    v = re.sub(r'[<>"\'&]', '', v)
    return html.escape(v.strip()[:50])


class SearchQueryInput(BaseModel):
    """Validate search query input"""
    query: str = Field(..., min_length=1, max_length=500)
    
    @field_validator('query')
    @classmethod
    def sanitize_query(cls, v):
        # Remove potentially dangerous characters
        v = re.sub(r'[<>"\'&\\]', '', v)
        
        # Remove control characters
        v = re.sub(r'[\x00-\x1F\x7F]', '', v)
        
        return v.strip()

