"""
Tests for Security Middleware - Production Ready
"""
import time
from unittest.mock import MagicMock

import pytest
from app.core.middleware import (
    RateLimitMiddleware,
    RequestLoggingMiddleware,
    RequestValidationMiddleware,
    SecurityHeadersMiddleware,
    configure_security_middleware,
)
from fastapi import FastAPI
from fastapi.testclient import TestClient


class TestRateLimitMiddleware:
    """Tests for rate limiting functionality"""

    @pytest.fixture
    def app(self):
        """Create a test app with rate limiting"""
        app = FastAPI()

        app.add_middleware(
            RateLimitMiddleware,
            default_limit=5,  # Very low for testing
            default_window=60,
            endpoint_limits={"/api/auth": (2, 60)},
            trusted_ips=["127.0.0.1"],
        )

        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        @app.get("/api/auth/login")
        async def auth_endpoint():
            return {"status": "authenticated"}

        @app.get("/health")
        async def health():
            return {"status": "healthy"}

        return app

    def test_rate_limit_headers_present(self, app):
        """Test that rate limit headers are added to response"""
        client = TestClient(app)

        # Make request from non-trusted IP
        response = client.get("/test", headers={"X-Forwarded-For": "1.2.3.4"})

        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers

    def test_health_endpoint_bypasses_rate_limit(self, app):
        """Test that health endpoint bypasses rate limiting"""
        client = TestClient(app)

        # Make many requests to health - should all succeed
        for _ in range(20):
            response = client.get("/health", headers={"X-Forwarded-For": "1.2.3.4"})
            assert response.status_code == 200

    def test_rate_limit_exceeded(self, app):
        """Test that rate limiting works when limit is exceeded"""
        client = TestClient(app)

        # Make requests until limit is exceeded
        responses = []
        for _ in range(10):
            response = client.get("/test", headers={"X-Forwarded-For": "9.9.9.9"})
            responses.append(response.status_code)

        # Some should be 200, some should be 429
        assert 429 in responses

    def test_endpoint_specific_limits(self, app):
        """Test that endpoint-specific limits work"""
        client = TestClient(app)

        # Auth endpoint has stricter limit (2/min)
        for i in range(5):
            response = client.get(
                "/api/auth/login", headers={"X-Forwarded-For": "8.8.8.8"}
            )
            if i >= 2:
                assert response.status_code == 429


class TestSecurityHeadersMiddleware:
    """Tests for security headers"""

    @pytest.fixture
    def app(self):
        """Create a test app with security headers"""
        app = FastAPI()

        app.add_middleware(SecurityHeadersMiddleware, csp_enabled=True)

        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        return app

    def test_security_headers_present(self, app):
        """Test that all security headers are present"""
        client = TestClient(app)
        response = client.get("/test")

        # Check required headers
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"
        assert response.headers.get("X-XSS-Protection") == "1; mode=block"
        assert "Strict-Transport-Security" in response.headers
        assert "Referrer-Policy" in response.headers
        assert "Permissions-Policy" in response.headers

    def test_csp_header_present(self, app):
        """Test that CSP header is present when enabled"""
        client = TestClient(app)
        response = client.get("/test")

        assert "Content-Security-Policy" in response.headers
        csp = response.headers.get("Content-Security-Policy")

        # Check CSP directives
        assert "default-src 'self'" in csp
        assert "frame-ancestors" in csp


class TestRequestValidationMiddleware:
    """Tests for request validation"""

    @pytest.fixture
    def app(self):
        """Create a test app with request validation"""
        app = FastAPI()

        app.add_middleware(RequestValidationMiddleware)

        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        return app

    def test_normal_request_passes(self, app):
        """Test that normal requests pass validation"""
        client = TestClient(app)
        response = client.get("/test")

        assert response.status_code == 200

    def test_path_traversal_blocked(self, app):
        """Test that path traversal attempts are blocked"""
        client = TestClient(app)

        # Use query param to avoid TestClient path normalization
        response = client.get("/test?file=../../etc/passwd")
        assert response.status_code == 400

    def test_xss_attempt_blocked(self, app):
        """Test that XSS attempts in URL are blocked"""
        client = TestClient(app)

        # The middleware checks the whole URL string
        response = client.get("/test", params={"x": "<script>alert(1)</script>"})
        assert response.status_code == 400

    def test_javascript_url_blocked(self, app):
        """Test that javascript: URLs are blocked"""
        client = TestClient(app)

        response = client.get("/test?url=javascript:alert(1)")
        assert response.status_code == 400


class TestRequestLoggingMiddleware:
    """Tests for request logging"""

    @pytest.fixture
    def app(self):
        """Create a test app with request logging"""
        app = FastAPI()

        app.add_middleware(RequestLoggingMiddleware)

        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        return app

    def test_response_time_header_added(self, app):
        """Test that X-Response-Time header is added"""
        client = TestClient(app)
        response = client.get("/test")

        assert "X-Response-Time" in response.headers

        # Should be a valid time string
        time_str = response.headers.get("X-Response-Time")
        assert time_str.endswith("s")


class TestConfigureSecurityMiddleware:
    """Tests for the middleware configuration function"""

    def test_configure_debug_mode(self):
        """Test middleware configuration in debug mode"""
        app = FastAPI()

        settings = MagicMock()
        settings.DEBUG = True
        settings.TRUSTED_HOSTS = ["*"]
        settings.FORCE_HTTPS = False

        result = configure_security_middleware(app, settings)

        assert result is not None

    def test_configure_production_mode(self):
        """Test middleware configuration in production mode"""
        app = FastAPI()

        settings = MagicMock()
        settings.DEBUG = False
        settings.TRUSTED_HOSTS = ["localhost", "example.com"]
        settings.FORCE_HTTPS = False

        result = configure_security_middleware(app, settings)

        assert result is not None


# Integration test with full middleware stack
class TestFullMiddlewareStack:
    """Integration tests with all middleware combined"""

    @pytest.fixture
    def app(self):
        """Create a test app with full middleware stack"""
        app = FastAPI()

        settings = MagicMock()
        settings.DEBUG = True
        settings.TRUSTED_HOSTS = ["*"]
        settings.FORCE_HTTPS = False

        configure_security_middleware(app, settings)

        @app.get("/api/test")
        async def test_endpoint():
            return {"status": "ok"}

        @app.get("/health")
        async def health():
            return {"status": "healthy"}

        return app

    def test_full_stack_request(self, app):
        """Test a request through the full middleware stack"""
        client = TestClient(app)
        response = client.get("/api/test")

        assert response.status_code == 200

        # Check security headers present
        assert "X-Content-Type-Options" in response.headers
        assert "X-Response-Time" in response.headers

    def test_health_check_fast(self, app):
        """Test that health checks are fast through middleware"""
        client = TestClient(app)

        start = time.time()
        for _ in range(10):
            response = client.get("/health")
            assert response.status_code == 200
        elapsed = time.time() - start

        # 10 health checks should complete quickly
        assert elapsed < 2.0  # Less than 2 seconds


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
