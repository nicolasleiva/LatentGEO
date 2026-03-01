# Security Incident Remediation Log (2026-03-01)

## Incident Summary

- Scope: exposed credentials patterns and historical secret-scanning alerts.
- Repository: `LatentGEO`.
- Owner: Security/Platform team.
- Status: in-progress with blocking controls enabled.

## Immediate Actions Completed

1. Removed hardcoded database credentials from migration helper.
2. Added repository baseline file for `detect-secrets` (`.secrets.baseline`).
3. Added PR/push workflow for secret regression blocking:
   - `.github/workflows/secret-scan.yml`
4. Updated pre-commit secret scanner config to use baseline consistently.

## Required Operational Actions (outside code)

1. Rotate and revoke exposed provider keys (OpenAI, Google, DB, OAuth, webhooks).
2. Review provider audit logs for suspicious usage.
3. Close GitHub secret-scanning alerts only after confirming revocation.

## Evidence Checklist

- [ ] Rotation ticket IDs recorded
- [ ] Revocation timestamps recorded
- [ ] Affected GitHub alert numbers recorded
- [ ] Security review sign-off recorded

---

# 🔒 Mejoras de Seguridad Necesarias

## 1. Problemas de Seguridad Encontrados

### 🔴 CRÍTICO

| Problema | Ubicación | Riesgo | Solución |
|----------|-----------|--------|----------|
| Credenciales hardcodeadas | `docker-compose.yml` | Exposición de secretos | Usar AWS Secrets Manager |
| DEBUG=True en producción | `.env.template` | Información sensible expuesta | Usar DEBUG=False en prod |
| Contraseña BD débil | `docker-compose.yml` | Acceso no autorizado | Generar contraseña fuerte |
| CORS abierto | `.env.template` | CSRF/XSS attacks | Especificar dominios reales |
| Sin HTTPS | Configuración | Man-in-the-middle | Usar CloudFront + ACM |
| Sin rate limiting | Backend | DDoS/Brute force | Implementar middleware |
| Sin CSRF protection | Frontend | CSRF attacks | Validar tokens CSRF |
| Sin validación de entrada | Backend | SQL injection/XSS | Usar Pydantic validators |

---

## 2. Cambios Inmediatos (Antes de Producción)

### 2.1 Backend - Seguridad en FastAPI

**Archivo: `backend/app/core/security.py`**

```python
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import os

def setup_security_middleware(app: FastAPI):
    """Configurar middleware de seguridad"""
    
    # 1. HTTPS Redirect (solo en producción)
    if os.getenv("ENVIRONMENT") == "production":
        app.add_middleware(HTTPSRedirectMiddleware)
    
    # 2. Trusted Hosts
    allowed_hosts = os.getenv("ALLOWED_HOSTS", "localhost").split(",")
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=allowed_hosts
    )
    
    # 3. CORS - Restrictivo
    cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
        max_age=600,  # 10 minutos
    )
    
    # 4. Rate Limiting
    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter
    
    return app

# Headers de seguridad
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}
```

**Usar en `backend/app/main.py`:**

```python
from fastapi import FastAPI
from .core.security import setup_security_middleware, SECURITY_HEADERS

app = FastAPI()

# Aplicar seguridad
setup_security_middleware(app)

# Agregar headers de seguridad
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    for header, value in SECURITY_HEADERS.items():
        response.headers[header] = value
    return response
```

### 2.2 Validación de Entrada

**Archivo: `backend/app/schemas/validators.py`**

```python
from pydantic import BaseModel, Field, validator
from typing import Optional
import re

class URLInput(BaseModel):
    url: str = Field(..., min_length=10, max_length=2048)
    
    @validator('url')
    def validate_url(cls, v):
        # Validar que sea una URL válida
        url_pattern = r'^https?://[a-zA-Z0-9\-._~:/?#\[\]@!$&\'()*+,;=]+$'
        if not re.match(url_pattern, v):
            raise ValueError('URL inválida')
        # Prevenir SSRF
        if any(blocked in v.lower() for blocked in ['localhost', '127.0.0.1', '192.168', '10.0']):
            raise ValueError('URL no permitida')
        return v

class APIKeyInput(BaseModel):
    api_key: str = Field(..., min_length=20, max_length=500)
    
    @validator('api_key')
    def validate_api_key(cls, v):
        # No permitir caracteres especiales peligrosos
        if not re.match(r'^[a-zA-Z0-9\-_]+$', v):
            raise ValueError('API Key inválida')
        return v
```

### 2.3 Autenticación y Autorización

**Archivo: `backend/app/core/auth.py`**

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthCredentials
import jwt
import os
from datetime import datetime, timedelta

security = HTTPBearer()

async def verify_token(credentials: HTTPAuthCredentials = Depends(security)):
    """Verificar JWT token"""
    try:
        payload = jwt.decode(
            credentials.credentials,
            os.getenv("SECRET_KEY"),
            algorithms=["HS256"]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
        return user_id
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Crear JWT token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=1)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode,
        os.getenv("SECRET_KEY"),
        algorithm="HS256"
    )
    return encoded_jwt
```

### 2.4 Logging Seguro

**Archivo: `backend/app/core/logger.py`**

```python
import logging
import os
from pythonjsonlogger import jsonlogger

def get_logger(name: str):
    """Logger con formato JSON para CloudWatch"""
    logger = logging.getLogger(name)
    
    # No loguear información sensible
    class SensitiveDataFilter(logging.Filter):
        SENSITIVE_KEYS = ['password', 'token', 'secret', 'api_key', 'credential']
        
        def filter(self, record):
            # Sanitizar mensaje
            for key in self.SENSITIVE_KEYS:
                if key in record.getMessage().lower():
                    record.msg = record.msg.replace(key, '***')
            return True
    
    handler = logging.StreamHandler()
    formatter = jsonlogger.JsonFormatter()
    handler.setFormatter(formatter)
    handler.addFilter(SensitiveDataFilter())
    logger.addHandler(handler)
    logger.setLevel(os.getenv("LOG_LEVEL", "info").upper())
    
    return logger
```

---

## 3. Frontend - Seguridad en Next.js

### 3.1 Headers de Seguridad

**Archivo: `frontend/next.config.mjs`**

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
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
            value: 'max-age=31536000; includeSubDomains'
          },
          {
            key: 'Content-Security-Policy',
            value: "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
          },
          {
            key: 'Referrer-Policy',
            value: 'strict-origin-when-cross-origin'
          }
        ]
      }
    ]
  },
  
  // Otras configuraciones
  reactStrictMode: true,
  swcMinify: true,
  
  // Deshabilitar X-Powered-By
  poweredByHeader: false,
};

export default nextConfig;
```

### 3.2 CSRF Protection

**Archivo: `frontend/lib/csrf.ts`**

```typescript
import { getCookie, setCookie } from 'cookies-next';

export async function getCSRFToken(): Promise<string> {
  let token = getCookie('csrf-token') as string;
  
  if (!token) {
    const response = await fetch('/api/csrf-token');
    const data = await response.json();
    token = data.token;
    setCookie('csrf-token', token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax'
    });
  }
  
  return token;
}

export async function fetchWithCSRF(url: string, options: RequestInit = {}) {
  const token = await getCSRFToken();
  
  return fetch(url, {
    ...options,
    headers: {
      ...options.headers,
      'X-CSRF-Token': token,
    }
  });
}
```

### 3.3 Sanitización de Entrada

**Archivo: `frontend/lib/sanitize.ts`**

```typescript
import DOMPurify from 'isomorphic-dompurify';

export function sanitizeHTML(dirty: string): string {
  return DOMPurify.sanitize(dirty, {
    ALLOWED_TAGS: ['b', 'i', 'em', 'strong', 'a', 'p', 'br'],
    ALLOWED_ATTR: ['href', 'target']
  });
}

export function sanitizeURL(url: string): string {
  try {
    const parsed = new URL(url);
    if (!['http:', 'https:'].includes(parsed.protocol)) {
      return '';
    }
    return url;
  } catch {
    return '';
  }
}
```

---

## 4. Docker - Seguridad en Contenedores

### 4.1 Dockerfile Seguro

**Archivo: `Dockerfile.backend` (mejorado)**

```dockerfile
# Multi-stage build
FROM python:3.11-slim as builder

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Final stage
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

# Usar usuario no-root
USER appuser

ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 4.2 Docker Compose Seguro

**Archivo: `docker-compose.prod.yml`**

```yaml
version: '3.8'

services:
  db:
    image: postgres:16-alpine
    container_name: auditor_db
    environment:
      POSTGRES_USER: auditor
      POSTGRES_PASSWORD: ${DB_PASSWORD}  # Desde .env
      POSTGRES_DB: auditor_db
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - auditor_network
    restart: unless-stopped
    # No exponer puerto en producción
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U auditor"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: auditor_redis
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
    container_name: auditor_backend
    environment:
      DEBUG: "False"
      ENVIRONMENT: production
      DATABASE_URL: postgresql+psycopg2://auditor:${DB_PASSWORD}@db:5432/auditor_db
      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/0
      SECRET_KEY: ${SECRET_KEY}
      CORS_ORIGINS: ${CORS_ORIGINS}
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
    # Limitar recursos
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

## 5. Checklist de Seguridad

### Antes de Producción

- [ ] Cambiar todas las contraseñas por defecto
- [ ] Generar SECRET_KEY segura
- [ ] Configurar CORS con dominios reales
- [ ] Habilitar HTTPS/TLS
- [ ] Implementar rate limiting
- [ ] Validar todas las entradas
- [ ] Sanitizar outputs
- [ ] Implementar CSRF protection
- [ ] Usar JWT tokens con expiración
- [ ] Loguear eventos de seguridad
- [ ] Usar contenedores con usuario no-root
- [ ] Limitar recursos de contenedores
- [ ] Usar AWS Secrets Manager
- [ ] Habilitar encryption en BD y Redis
- [ ] Configurar WAF en CloudFront
- [ ] Implementar CI/CD con tests de seguridad

### En Producción

- [ ] Monitorear logs en CloudWatch
- [ ] Configurar alertas de seguridad
- [ ] Hacer backups regulares
- [ ] Actualizar dependencias regularmente
- [ ] Hacer auditorías de seguridad
- [ ] Implementar DDoS protection
- [ ] Usar VPN para acceso administrativo
- [ ] Habilitar MFA en AWS
- [ ] Rotar credenciales regularmente

---

## 6. Herramientas de Seguridad Recomendadas

```bash
# Escanear vulnerabilidades en dependencias
pip install safety
safety check

# Análisis estático de código
pip install bandit
bandit -r backend/

# Escanear secretos
pip install detect-secrets
detect-secrets scan

# OWASP ZAP para testing
docker run -t owasp/zap2docker-stable zap-baseline.py -t https://auditor-geo.com
```

---

## 7. Referencias

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [Next.js Security](https://nextjs.org/docs/advanced-features/security-headers)
- [AWS Security Best Practices](https://aws.amazon.com/architecture/security-identity-compliance/)
