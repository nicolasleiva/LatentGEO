"""
Production Test Configuration
Uses YOUR existing .env and database configuration
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# Load YOUR existing .env file
env_path = Path(__file__).parent.parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    print("Warning: .env file not found. Please ensure it exists in the project root.")


class ProductionTestConfig:
    """
    Configuration for production-ready testing
    Uses YOUR EXISTING environment and database
    """

    # ============================================
    # DATABASE CONFIGURATION (YOUR EXISTING DB)
    # ============================================

    # Uses your existing DATABASE_URL from .env
    DATABASE_URL = os.getenv("DATABASE_URL", "")

    # Connection pooling settings
    DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "20"))
    DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "40"))
    DB_POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "3600"))
    DB_ECHO = os.getenv("DB_ECHO", "False").lower() == "true"

    # ============================================
    # EXTERNAL APIs (FROM YOUR .env)
    # ============================================

    # All API keys from your .env configuration
    SERP_API_KEY = os.getenv("SERP_API_KEY", "")
    AHREFS_API_KEY = os.getenv("AHREFS_API_KEY", "")
    SEMRUSH_API_KEY = os.getenv("SEMRUSH_API_KEY", "")
    MOZ_API_KEY = os.getenv("MOZ_API_KEY", "")

    # Google APIs
    GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "")
    GOOGLE_CLOUD_CREDENTIALS_PATH = os.getenv("GOOGLE_CLOUD_CREDENTIALS_PATH", "")
    GOOGLE_PAGESPEED_API_KEY = os.getenv("GOOGLE_PAGESPEED_API_KEY", "")

    # AI APIs
    NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
    NV_API_KEY = os.getenv("NV_API_KEY", "")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

    # Cloud Services
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
    AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET", "")

    # ============================================
    # AUTHENTICATION (FROM YOUR .env)
    # ============================================

    AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN", "")
    AUTH0_CLIENT_ID = os.getenv("AUTH0_CLIENT_ID", "")
    AUTH0_CLIENT_SECRET = os.getenv("AUTH0_CLIENT_SECRET", "")

    # ============================================
    # STRIPE PAYMENTS (FROM YOUR .env)
    # ============================================

    STRIPE_API_KEY = os.getenv("STRIPE_API_KEY", "")
    STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

    # ============================================
    # EMAIL CONFIGURATION (FROM YOUR .env)
    # ============================================

    SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM = os.getenv("SMTP_FROM", "noreply@auditor-geo.com")

    # ============================================
    # LOGGING & MONITORING
    # ============================================

    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("LOG_FILE", "logs/production.log")
    SENTRY_DSN = os.getenv("SENTRY_DSN", "")
    DATADOG_API_KEY = os.getenv("DATADOG_API_KEY", "")

    # ============================================
    # TEST CONFIGURATION
    # ============================================

    # Timeout for API calls during tests (seconds)
    API_TIMEOUT = int(os.getenv("API_TIMEOUT", "30"))

    # Database transaction handling
    TRANSACTIONS_ENABLED = os.getenv("TRANSACTIONS_ENABLED", "True").lower() == "true"

    # Run slow tests (API calls, etc)
    RUN_SLOW_TESTS = os.getenv("RUN_SLOW_TESTS", "True").lower() == "true"

    # Run integration tests
    RUN_INTEGRATION_TESTS = os.getenv("RUN_INTEGRATION_TESTS", "True").lower() == "true"


# Export configuration
config = ProductionTestConfig()


# ============================================
# VALIDATION
# ============================================


def validate_configuration():
    """
    Validate that all required settings are configured
    Raise error if critical settings are missing
    """
    critical_settings = [
        ("DATABASE_URL", config.DATABASE_URL),
        ("NVIDIA_API_KEY", config.NVIDIA_API_KEY or config.NV_API_KEY),
        ("AUTH0_DOMAIN", config.AUTH0_DOMAIN),
    ]

    missing = []
    for name, value in critical_settings:
        if not value:
            missing.append(name)

    if missing:
        raise ValueError(
            f"Missing critical environment variables: {', '.join(missing)}\n"
            f"Please configure .env.production file"
        )

    print("Production configuration validated")


if __name__ == "__main__":
    # Validate on import
    validate_configuration()

    # Print configuration summary
    print("\n" + "=" * 60)
    print("PRODUCTION TEST CONFIGURATION")
    print("=" * 60)
    print(f"Database: {config.DATABASE_URL}")
    print(f"Log Level: {config.LOG_LEVEL}")
    print(f"Run Slow Tests: {config.RUN_SLOW_TESTS}")
    print(f"Run Integration Tests: {config.RUN_INTEGRATION_TESTS}")
    print("=" * 60)
