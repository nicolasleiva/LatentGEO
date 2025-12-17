# 💻 Ejemplos de Código - Mejoras de Seguridad

## 1. Backend - FastAPI Seguro

### 1.1 Configuración de Seguridad

**Archivo: `backend/app/core/security.py`**

```python
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address
import os
from typing import List

def get_cors_origins() -> List[str]:
    """Obtener orígenes CORS desde variables de entorno"""
    origins = os.getenv("CORS_ORIGINS", "http://localhost:3000")
    return [origin.strip() for origin in origins.split(",")]

def get_allowed_hosts() -> List[str]:
    """Obtener hosts permitidos desde variables de entorno"""
    hosts = os.getenv("ALLOWED_HOSTS", "localhost")
    return [host.strip() for host in hosts.split(",")]

def setup_security_middleware(app: FastAPI) -> FastAPI:
    """Configurar middleware de seguridad"""
    
    # 1. HTTPS Redirect (solo en producción)
    if os.getenv("ENVIRONMENT") == "production":
        app.add_middleware(HTTPSRedirectMiddleware)
    
    # 2. Trusted Hosts
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=get_allowed_hosts()
    )
    
    # 3. CORS - Restrictivo
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_cors_origins(),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        max_age=600,  # 10 minutos
    )
    
    return app

# Headers de seguridad
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
}

async def add_security_headers_middleware(request: Request, call_next):
    """Middleware para agregar headers de seguridad"""
    response = await call_next(request)
    for header, value in SECURITY_HEADERS.items():
        response.headers[header] = value
    return response
```

### 1.2 Rate Limiting

**Archivo: `backend/app/core/rate_limit.py`**

```python
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import os

limiter = Limiter(key_func=get_remote_address)

def setup_rate_limiting(app: FastAPI) -> FastAPI:
    """Configurar rate limiting"""
    
    app.state.limiter = limiter
    
    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Please try again later."}
        )
    
    return app

# Decoradores para usar en endpoints
def rate_limit_public():
    """Rate limit para endpoints públicos: 100 requests/hora"""
    return limiter.limit("100/hour")

def rate_limit_auth():
    """Rate limit para endpoints autenticados: 1000 requests/hora"""
    return limiter.limit("1000/hour")

def rate_limit_login():
    """Rate limit para login: 5 intentos/15 minutos"""
    return limiter.limit("5/15 minutes")
```

### 1.3 Validación de Entrada

**Archivo: `backend/app/schemas/validators.py`**

```python
from pydantic import BaseModel, Field, validator, HttpUrl
from typing import Optional
import re
from urllib.parse import urlparse

class URLInput(BaseModel):
    """Validar URLs de entrada"""
    url: str = Field(..., min_length=10, max_length=2048)
    
    @validator('url')
    def validate_url(cls, v):
        # Validar que sea una URL válida
        try:
            parsed = urlparse(v)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError('URL inválida')
        except Exception:
            raise ValueError('URL inválida')
        
        # Prevenir SSRF (Server-Side Request Forgery)
        blocked_hosts = [
            'localhost', '127.0.0.1', '0.0.0.0',
            '192.168', '10.0', '172.16',  # Private IPs
            'metadata.google.internal',  # GCP metadata
            '169.254.169.254',  # AWS metadata
        ]
        
        for blocked in blocked_hosts:
            if blocked in v.lower():
                raise ValueError('URL no permitida por razones de seguridad')
        
        # Validar protocolo
        if not v.lower().startswith(('http://', 'https://')):
            raise ValueError('Solo se permiten URLs HTTP/HTTPS')
        
        return v

class APIKeyInput(BaseModel):
    """Validar API keys de entrada"""
    api_key: str = Field(..., min_length=20, max_length=500)
    
    @validator('api_key')
    def validate_api_key(cls, v):
        # No permitir caracteres especiales peligrosos
        if not re.match(r'^[a-zA-Z0-9\-_]+$', v):
            raise ValueError('API Key contiene caracteres inválidos')
        return v

class EmailInput(BaseModel):
    """Validar emails de entrada"""
    email: str = Field(..., min_length=5, max_length=255)
    
    @validator('email')
    def validate_email(cls, v):
        # Validar formato de email
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, v):
            raise ValueError('Email inválido')
        return v.lower()

class PasswordInput(BaseModel):
    """Validar contraseñas de entrada"""
    password: str = Field(..., min_length=8, max_length=128)
    
    @validator('password')
    def validate_password(cls, v):
        # Validar fortaleza de contraseña
        if not any(c.isupper() for c in v):
            raise ValueError('La contraseña debe contener al menos una mayúscula')
        if not any(c.islower() for c in v):
            raise ValueError('La contraseña debe contener al menos una minúscula')
        if not any(c.isdigit() for c in v):
            raise ValueError('La contraseña debe contener al menos un número')
        if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in v):
            raise ValueError('La contraseña debe contener al menos un carácter especial')
        return v
```

### 1.4 Autenticación JWT

**Archivo: `backend/app/core/auth.py`**

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthCredentials
import jwt
import os
from datetime import datetime, timedelta
from typing import Optional

security = HTTPBearer()

def get_secret_key() -> str:
    """Obtener SECRET_KEY desde variables de entorno"""
    secret = os.getenv("SECRET_KEY")
    if not secret:
        raise ValueError("SECRET_KEY no configurada")
    return secret

def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None
) -> str:
    """Crear JWT token con expiración"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=1)
    
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    
    encoded_jwt = jwt.encode(
        to_encode,
        get_secret_key(),
        algorithm="HS256"
    )
    return encoded_jwt

def create_refresh_token(data: dict) -> str:
    """Crear refresh token con expiración de 7 días"""
    return create_access_token(data, expires_delta=timedelta(days=7))

async def verify_token(
    credentials: HTTPAuthCredentials = Depends(security)
) -> str:
    """Verificar JWT token"""
    token = credentials.credentials
    
    try:
        payload = jwt.decode(
            token,
            get_secret_key(),
            algorithms=["HS256"]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido"
            )
        return user_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido"
        )

async def verify_refresh_token(
    credentials: HTTPAuthCredentials = Depends(security)
) -> str:
    """Verificar refresh token"""
    return await verify_token(credentials)
```

### 1.5 Logging Seguro

**Archivo: `backend/app/core/logger.py`**

```python
import logging
import os
import json
from datetime import datetime
from typing import Any

class SensitiveDataFilter(logging.Filter):
    """Filtro para no loguear datos sensibles"""
    
    SENSITIVE_KEYS = [
        'password', 'token', 'secret', 'api_key', 'credential',
        'authorization', 'x-api-key', 'x-auth-token',
        'database_url', 'redis_url', 'encryption_key'
    ]
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Sanitizar mensaje de log"""
        message = record.getMessage()
        
        for key in self.SENSITIVE_KEYS:
            # Buscar en el mensaje
            if key.lower() in message.lower():
                # Reemplazar valor
                import re
                pattern = rf'{key}\s*[:=]\s*[^\s,}}\]]*'
                message = re.sub(
                    pattern,
                    f'{key}=***',
                    message,
                    flags=re.IGNORECASE
                )
        
        record.msg = message
        return True

class JSONFormatter(logging.Formatter):
    """Formatter para logs en formato JSON"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)

def get_logger(name: str) -> logging.Logger:
    """Obtener logger configurado"""
    logger = logging.getLogger(name)
    
    # Evitar duplicados
    if logger.handlers:
        return logger
    
    # Handler para stdout
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    handler.addFilter(SensitiveDataFilter())
    
    logger.addHandler(handler)
    logger.setLevel(os.getenv("LOG_LEVEL", "info").upper())
    
    return logger
```

### 1.6 Uso en main.py

**Archivo: `backend/app/main.py`**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .core.security import setup_security_middleware, add_security_headers_middleware
from .core.rate_limit import setup_rate_limiting
from .core.logger import get_logger

logger = get_logger(__name__)

app = FastAPI(
    title="Auditor GEO API",
    description="API para auditoría de sitios web",
    version="1.0.0"
)

# Aplicar middleware de seguridad
app = setup_security_middleware(app)
app = setup_rate_limiting(app)

# Agregar middleware de headers de seguridad
app.add_middleware(
    lambda app: lambda request: add_security_headers_middleware(request, app)
)

# Rutas
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok"}

@app.get("/api/audits")
async def get_audits(user_id: str = Depends(verify_token)):
    """Obtener auditorías del usuario"""
    logger.info(f"User {user_id} requested audits")
    return {"audits": []}
```

---

## 2. Frontend - Next.js Seguro

### 2.1 Headers de Seguridad

**Archivo: `frontend/next.config.mjs`**

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,
  poweredByHeader: false,
  
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff'
          },
          {
            key: 'X-Frame-Options',
            value: 'DENY'
          },
          {
            key: 'X-XSS-Protection',
            value: '1; mode=block'
          },
          {
            key: 'Strict-Transport-Security',
            value: 'max-age=31536000; includeSubDomains; preload'
          },
          {
            key: 'Content-Security-Policy',
            value: "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self'; connect-src 'self' https:; frame-ancestors 'none';"
          },
          {
            key: 'Referrer-Policy',
            value: 'strict-origin-when-cross-origin'
          },
          {
            key: 'Permissions-Policy',
            value: 'geolocation=(), microphone=(), camera=(), payment=()'
          }
        ]
      }
    ]
  },
  
  async redirects() {
    return [
      {
        source: '/api/:path*',
        destination: `${process.env.NEXT_PUBLIC_API_URL}/api/:path*`,
        permanent: false
      }
    ]
  }
};

export default nextConfig;
```

### 2.2 CSRF Protection

**Archivo: `frontend/lib/csrf.ts`**

```typescript
import { getCookie, setCookie } from 'cookies-next';

const CSRF_TOKEN_KEY = 'X-CSRF-Token';
const CSRF_COOKIE_NAME = 'csrf-token';

export async function getCSRFToken(): Promise<string> {
  // Intentar obtener del cookie
  let token = getCookie(CSRF_COOKIE_NAME) as string;
  
  if (!token) {
    // Solicitar nuevo token del servidor
    try {
      const response = await fetch('/api/csrf-token', {
        method: 'GET',
        credentials: 'include'
      });
      
      if (!response.ok) {
        throw new Error('Failed to get CSRF token');
      }
      
      const data = await response.json();
      token = data.token;
      
      // Guardar en cookie
      setCookie(CSRF_COOKIE_NAME, token, {
        httpOnly: true,
        secure: process.env.NODE_ENV === 'production',
        sameSite: 'lax',
        maxAge: 60 * 60 * 24 // 24 horas
      });
    } catch (error) {
      console.error('Error getting CSRF token:', error);
      throw error;
    }
  }
  
  return token;
}

export async function fetchWithCSRF(
  url: string,
  options: RequestInit = {}
): Promise<Response> {
  const token = await getCSRFToken();
  
  const headers = new Headers(options.headers || {});
  headers.set(CSRF_TOKEN_KEY, token);
  
  // Asegurar que se envíen cookies
  const fetchOptions: RequestInit = {
    ...options,
    headers,
    credentials: 'include'
  };
  
  return fetch(url, fetchOptions);
}

export async function postWithCSRF(
  url: string,
  data: any
): Promise<Response> {
  return fetchWithCSRF(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(data)
  });
}

export async function putWithCSRF(
  url: string,
  data: any
): Promise<Response> {
  return fetchWithCSRF(url, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(data)
  });
}

export async function deleteWithCSRF(url: string): Promise<Response> {
  return fetchWithCSRF(url, {
    method: 'DELETE'
  });
}
```

### 2.3 Sanitización de Entrada

**Archivo: `frontend/lib/sanitize.ts`**

```typescript
import DOMPurify from 'isomorphic-dompurify';

export function sanitizeHTML(dirty: string): string {
  return DOMPurify.sanitize(dirty, {
    ALLOWED_TAGS: ['b', 'i', 'em', 'strong', 'a', 'p', 'br', 'ul', 'ol', 'li'],
    ALLOWED_ATTR: ['href', 'target', 'rel'],
    KEEP_CONTENT: true
  });
}

export function sanitizeURL(url: string): string {
  try {
    const parsed = new URL(url);
    
    // Solo permitir http y https
    if (!['http:', 'https:'].includes(parsed.protocol)) {
      return '';
    }
    
    // Prevenir javascript: URLs
    if (url.toLowerCase().startsWith('javascript:')) {
      return '';
    }
    
    return url;
  } catch {
    return '';
  }
}

export function sanitizeInput(input: string, maxLength: number = 1000): string {
  // Limitar longitud
  let sanitized = input.substring(0, maxLength);
  
  // Remover caracteres de control
  sanitized = sanitized.replace(/[\x00-\x1F\x7F]/g, '');
  
  // Remover scripts
  sanitized = sanitized.replace(/<script[^>]*>.*?<\/script>/gi, '');
  
  return sanitized.trim();
}

export function validateEmail(email: string): boolean {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email) && email.length <= 255;
}

export function validateURL(url: string): boolean {
  try {
    new URL(url);
    return true;
  } catch {
    return false;
  }
}
```

### 2.4 Uso en Componentes

**Archivo: `frontend/components/AuditForm.tsx`**

```typescript
import { useState } from 'react';
import { postWithCSRF } from '@/lib/csrf';
import { sanitizeInput, validateURL } from '@/lib/sanitize';

export default function AuditForm() {
  const [url, setUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    
    // Validar entrada
    const sanitizedUrl = sanitizeInput(url);
    if (!validateURL(sanitizedUrl)) {
      setError('URL inválida');
      return;
    }
    
    setLoading(true);
    
    try {
      const response = await postWithCSRF('/api/audits', {
        url: sanitizedUrl
      });
      
      if (!response.ok) {
        throw new Error('Error al crear auditoría');
      }
      
      const data = await response.json();
      console.log('Auditoría creada:', data);
      setUrl('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error desconocido');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <input
        type="url"
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        placeholder="https://ejemplo.com"
        required
        maxLength={2048}
      />
      <button type="submit" disabled={loading}>
        {loading ? 'Cargando...' : 'Auditar'}
      </button>
      {error && <p style={{ color: 'red' }}>{error}</p>}
    </form>
  );
}
```

---

## 3. Docker - Dockerfile Seguro

### 3.1 Backend Dockerfile

**Archivo: `Dockerfile.backend`**

```dockerfile
# Multi-stage build para reducir tamaño
FROM python:3.11-slim as builder

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements
COPY backend/requirements.txt .

# Instalar dependencias Python en directorio de usuario
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage final
FROM python:3.11-slim

WORKDIR /app

# Crear usuario no-root
RUN useradd -m -u 1000 appuser

# Copiar dependencias del builder
COPY --from=builder /root/.local /home/appuser/.local

# Copiar código
COPY backend/ .

# Cambiar permisos
RUN chown -R appuser:appuser /app

# Cambiar a usuario no-root
USER appuser

# Configurar PATH
ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Exponer puerto
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')" || exit 1

# Comando de inicio
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 4. Configuración de Producción

### 4.1 docker-compose.prod.yml

```yaml
version: '3.8'

services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: auditor
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: auditor_db
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - auditor_network
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U auditor"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    command: redis-server --requirepass ${REDIS_PASSWORD}
    networks:
      - auditor_network
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  backend:
    build:
      context: .
      dockerfile: Dockerfile.backend
    environment:
      DEBUG: "False"
      ENVIRONMENT: production
      DATABASE_URL: postgresql+psycopg2://auditor:${DB_PASSWORD}@db:5432/auditor_db
      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/0
      SECRET_KEY: ${SECRET_KEY}
      CORS_ORIGINS: ${CORS_ORIGINS}
      ALLOWED_HOSTS: ${ALLOWED_HOSTS}
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - auditor_network
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M

volumes:
  postgres_data:

networks:
  auditor_network:
    driver: bridge
```

---

## 5. Resumen

Estos ejemplos cubren:
- ✅ Middleware de seguridad en FastAPI
- ✅ Rate limiting
- ✅ Validación de entrada
- ✅ Autenticación JWT
- ✅ Logging seguro
- ✅ Headers de seguridad en Next.js
- ✅ CSRF protection
- ✅ Sanitización de entrada
- ✅ Dockerfile seguro
- ✅ Configuración de producción

Implementa estos cambios antes de desplegar a producción.
