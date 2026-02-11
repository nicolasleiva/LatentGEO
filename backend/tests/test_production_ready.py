"""
Production Readiness Integration Tests
Tests the full stack for production deployment.
"""
import pytest
import os
import tempfile
import json
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

@pytest.fixture
def test_db():
    """Temporary file DB for reliable testing on Windows"""
    db_fd, db_path = tempfile.mkstemp()
    db_url = f"sqlite:///{db_path}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    
    from app.models import Base
    Base.metadata.create_all(bind=engine)
    
    yield db_url, engine
    
    engine.dispose()
    os.close(db_fd)
    if os.path.exists(db_path):
        os.remove(db_path)

@pytest.fixture
def test_app(test_db):
    """Create a configured app for testing"""
    db_url, engine = test_db
    from app.main import create_app
    from app.core import database
    from app.core.config import settings
    from app.core.database import get_db
    from app.core.auth import get_current_user, AuthUser
    
    # Session factory for this engine
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Patch everything BEFORE calling create_app
    with patch.object(settings, 'DATABASE_URL', db_url), \
         patch.object(settings, 'DEBUG', False), \
         patch.object(database, 'engine', engine), \
         patch.object(database, 'SessionLocal', TestingSessionLocal):
        
        app = create_app()
        
        # Override dependency
        def override_get_db():
            db = TestingSessionLocal()
            try:
                yield db
            finally:
                db.close()

        def override_get_current_user():
            return AuthUser(user_id="test-user", email="test@example.com")
        
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user
        return app

@pytest.fixture
def client(test_app):
    """Test client with configured app"""
    return TestClient(test_app)

class TestProductionReadiness:
    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json().get("status") in ["healthy", "degraded"]

    def test_api_docs(self, client):
        response = client.get("/docs")
        assert response.status_code == 200

    def test_security_headers(self, client):
        response = client.get("/health")
        assert "X-Content-Type-Options" in response.headers
        assert "X-Frame-Options" in response.headers

    def test_rate_limit_headers(self, client):
        # We use /api/v1/audits/ which exists in the app
        response = client.get("/api/v1/audits/", headers={"X-Forwarded-For": "1.2.3.4"})
        # Should have rate limit headers (or be rejected with 401/422 but with headers)
        assert any(h in response.headers for h in ["X-RateLimit-Limit", "X-RateLimit-Remaining"]) or response.status_code == 401

class TestInputValidation:
    def test_ssrf_blocking(self, client):
        # SSRF attempt in audit creation
        response = client.post(
            "/api/v1/audits/",
            json={"url": "http://localhost:8080/admin"}
        )
        assert response.status_code in [400, 422]

class TestWebhookEndpoints:
    def test_webhook_health(self, client):
        response = client.get("/api/webhooks/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_github_webhook(self, client):
        from app.core.config import settings
        from app.services.webhook_service import WebhookService

        payload = {"zen": "Testing is good"}
        body = json.dumps(payload)

        secret = "test-webhook-secret"
        with patch.object(settings, "GITHUB_WEBHOOK_SECRET", secret):
            signature = "sha256=" + WebhookService.generate_signature(body, secret)
            response = client.post(
                "/api/webhooks/github/incoming",
                data=body,
                headers={
                    "X-GitHub-Event": "ping",
                    "X-Hub-Signature-256": signature,
                    "Content-Type": "application/json",
                },
            )
            assert response.status_code == 200

class TestSecurityConfiguration:
    def test_settings_existence(self):
        from app.core.config import settings
        assert hasattr(settings, 'RATE_LIMIT_DEFAULT')
        assert hasattr(settings, 'WEBHOOK_SECRET')

class TestAuthentication:
    def test_jwt_flow(self):
        from app.core.auth import create_access_token
        with patch.dict(os.environ, {"SECRET_KEY": "a-very-secret-test-key-that-is-long-enough"}):
            token = create_access_token({"sub": "test-user"})
            assert token is not None
            assert len(token) > 20

class TestMiddlewareIntegration:
    def test_middleware_stack(self, client):
        response = client.get("/health")
        assert "X-Response-Time" in response.headers
        assert response.status_code == 200
