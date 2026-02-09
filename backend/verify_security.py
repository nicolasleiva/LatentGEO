"""
Quick verification script for security components
"""
import sys
sys.path.insert(0, '.')

def main():
    print("=" * 50)
    print("SECURITY COMPONENTS VERIFICATION")
    print("=" * 50)
    
    # Test 1: Middleware imports
    print("\n1. Testing Middleware imports...")
    try:
        from app.core.middleware import (
            RateLimitMiddleware, 
            SecurityHeadersMiddleware, 
            RequestValidationMiddleware,
            RequestLoggingMiddleware,
            configure_security_middleware
        )
        print("   ✓ All middleware components imported successfully")
    except Exception as e:
        print(f"   ✗ Middleware import failed: {e}")
        return False
    
    # Test 2: Webhook service
    print("\n2. Testing Webhook Service...")
    try:
        from app.services.webhook_service import (
            WebhookService, 
            WebhookEventType,
            WebhookDeliveryStatus
        )
        print("   ✓ Webhook service imported successfully")
        
        # Test signature generation
        payload = '{"test": "data"}'
        secret = "test-secret-key"
        sig = WebhookService.generate_signature(payload, secret)
        print(f"   ✓ Signature generation works: {sig[:20]}...")
        
        # Test signature verification
        is_valid = WebhookService.verify_signature(payload, sig, secret)
        assert is_valid == True, "Signature should be valid"
        print("   ✓ Signature verification works")
        
        # Test invalid signature
        is_invalid = WebhookService.verify_signature(payload, "wrong", secret)
        assert is_invalid == False, "Invalid signature should fail"
        print("   ✓ Invalid signature correctly rejected")
        
        # List event types
        events = [e.value for e in WebhookEventType]
        print(f"   ✓ {len(events)} webhook event types defined")
        
    except Exception as e:
        print(f"   ✗ Webhook service test failed: {e}")
        return False
    
    # Test 3: Validators
    print("\n3. Testing Validators...")
    try:
        from app.schemas.validators import (
            URLInput,
            APIKeyInput, 
            EmailInput,
            HTMLContent,
            WebhookURLInput
        )
        print("   ✓ Validators imported successfully")
        
        # Test valid URL
        valid_url = URLInput(url="https://example.com/page")
        print("   ✓ Valid URL accepted")
        
        # Test valid email
        valid_email = EmailInput(email="test@example.com")
        print("   ✓ Valid email accepted")
        
        # Test HTML sanitization
        html = HTMLContent(content='<script>alert(1)</script>Hello')
        assert '<script>' not in html.content, "Script should be removed"
        print("   ✓ HTML sanitization works")
        
    except Exception as e:
        print(f"   ✗ Validators test failed: {e}")
        return False
    
    # Test 4: Config settings
    print("\n4. Testing Config Settings...")
    try:
        from app.core.config import settings
        
        assert hasattr(settings, 'RATE_LIMIT_DEFAULT')
        assert hasattr(settings, 'RATE_LIMIT_AUTH')
        assert hasattr(settings, 'RATE_LIMIT_HEAVY')
        assert hasattr(settings, 'DEFAULT_WEBHOOK_URL')
        assert hasattr(settings, 'WEBHOOK_SECRET')
        assert hasattr(settings, 'FRONTEND_URL')
        assert hasattr(settings, 'TRUSTED_HOSTS')
        assert hasattr(settings, 'FORCE_HTTPS')
        
        print("   ✓ All security settings exist")
        print(f"   - RATE_LIMIT_DEFAULT: {settings.RATE_LIMIT_DEFAULT}")
        print(f"   - RATE_LIMIT_AUTH: {settings.RATE_LIMIT_AUTH}")
        print(f"   - RATE_LIMIT_HEAVY: {settings.RATE_LIMIT_HEAVY}")
        print(f"   - FORCE_HTTPS: {settings.FORCE_HTTPS}")
        
    except Exception as e:
        print(f"   ✗ Config test failed: {e}")
        return False
    
    # Test 5: Auth module
    print("\n5. Testing Auth Module...")
    try:
        import os
        os.environ['SECRET_KEY'] = 'test-secret-key-for-verification'
        
        from app.core.auth import create_access_token, create_refresh_token
        
        token = create_access_token({"sub": "user123"})
        assert len(token) > 50, "Token should be substantial length"
        print("   ✓ Access token generation works")
        
        refresh = create_refresh_token({"sub": "user123"})
        assert len(refresh) > 50, "Refresh token should be substantial length"
        print("   ✓ Refresh token generation works")
        
    except Exception as e:
        print(f"   ✗ Auth module test failed: {e}")
        return False
    
    print("\n" + "=" * 50)
    print("ALL SECURITY COMPONENTS: PASSED ✓")
    print("=" * 50)
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
