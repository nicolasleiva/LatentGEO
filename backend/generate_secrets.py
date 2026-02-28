"""
Genera un template local de variables sin secretos reales.
Uso: python generate_secrets.py
"""

from pathlib import Path


TEMPLATE_PATH = Path(".env.template")

ENV_TEMPLATE = """# TEMPLATE DE ENTORNO (SIN SECRETOS REALES)
# Completar con secretos desde tu Secret Manager en producción.

# Security
SECRET_KEY=<set-in-secret-manager>
ENCRYPTION_KEY=<set-in-secret-manager>
WEBHOOK_SECRET=<set-in-secret-manager>

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/auditor_geo

# Redis
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# CORS
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# HTTPS
FORCE_HTTPS=true

# API Keys
NVIDIA_API_KEY=<set-in-secret-manager>
GOOGLE_PAGESPEED_API_KEY=<set-in-secret-manager>
SERPER_API_KEY=<set-in-secret-manager>

# Auth0
AUTH0_DOMAIN=your_domain.auth0.com
AUTH0_CLIENT_ID=<set-in-secret-manager>
AUTH0_CLIENT_SECRET=<set-in-secret-manager>

# Monitoring
SENTRY_DSN=<set-in-secret-manager>
ENVIRONMENT=production
LOG_FORMAT=json

# Rate Limiting
RATE_LIMIT_DEFAULT=100
RATE_LIMIT_AUTH=10
RATE_LIMIT_HEAVY=5
"""


def main() -> None:
    TEMPLATE_PATH.write_text(ENV_TEMPLATE, encoding="utf-8")
    print("=" * 60)
    print("OK - Archivo .env.template creado")
    print("=" * 60)
    print("No se generaron ni imprimieron secretos reales.")
    print("Usar Secret Manager en producción y .env en local.")


if __name__ == "__main__":
    main()
