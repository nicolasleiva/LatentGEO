"""
Script para generar secrets seguros para producción
Ejecutar: python generate_secrets.py
"""
import secrets
import base64
from cryptography.fernet import Fernet

print("=" * 60)
print("GENERANDO SECRETS PARA PRODUCCIÓN")
print("=" * 60)
print()

# 1. SECRET_KEY para JWT/Sessions
secret_key = base64.b64encode(secrets.token_bytes(32)).decode()
print("SECRET_KEY (para .env):")
print(f"SECRET_KEY={secret_key}")
print()

# 2. ENCRYPTION_KEY para OAuth tokens (Fernet)
encryption_key = Fernet.generate_key().decode()
print("ENCRYPTION_KEY (para .env):")
print(f"ENCRYPTION_KEY={encryption_key}")
print()

# 3. WEBHOOK_SECRET
webhook_secret = secrets.token_hex(32)
print("WEBHOOK_SECRET (para .env):")
print(f"WEBHOOK_SECRET={webhook_secret}")
print()

# 4. Generar .env.production template
env_template = f"""# PRODUCTION ENVIRONMENT VARIABLES
# Generated: {secrets.token_hex(4)}

# Security
SECRET_KEY={secret_key}
ENCRYPTION_KEY={encryption_key}
WEBHOOK_SECRET={webhook_secret}

# Database (CAMBIAR A TU POSTGRESQL)
DATABASE_URL=postgresql://user:password@localhost:5432/auditor_geo

# Redis
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# CORS (CAMBIAR A TU DOMINIO)
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# HTTPS
FORCE_HTTPS=true

# API Keys (AGREGAR TUS KEYS REALES)
NVIDIA_API_KEY=your_nvidia_key_here
GOOGLE_PAGESPEED_API_KEY=your_google_key_here
GOOGLE_API_KEY=your_google_key_here
CSE_ID=your_cse_id_here

# Auth0 (AGREGAR TUS CREDENCIALES)
AUTH0_DOMAIN=your_domain.auth0.com
AUTH0_CLIENT_ID=your_client_id
AUTH0_CLIENT_SECRET=your_client_secret

# Monitoring
SENTRY_DSN=your_sentry_dsn_here
ENVIRONMENT=production
LOG_FORMAT=json

# Rate Limiting
RATE_LIMIT_DEFAULT=100
RATE_LIMIT_AUTH=10
RATE_LIMIT_HEAVY=5
"""

with open(".env.production.generated", "w") as f:
    f.write(env_template)

print("=" * 60)
print("OK - Archivo .env.production.generated creado")
print("=" * 60)
print()
print("PRÓXIMOS PASOS:")
print("1. Revisar .env.production.generated")
print("2. Completar con tus API keys reales")
print("3. Renombrar a .env.production")
print("4. NUNCA commitear este archivo a git")
print()
