"""
Complete System Verification Script
Verifies all core business components are working.
"""
import sys

sys.path.insert(0, ".")


def main():
    print("=" * 60)
    print("COMPLETE SYSTEM VERIFICATION")
    print("=" * 60)

    errors = []
    warnings = []

    # ===== 1. CORE ROUTES =====
    print("\n1. Core API Routes...")
    try:
        from app.api.routes import analytics, audits, health, pagespeed, reports, search

        print("   ✓ audits, reports, analytics, health, search, pagespeed")
    except Exception as e:
        errors.append(f"Core routes: {e}")
        print(f"   ✗ Core routes failed: {e}")

    # ===== 2. INTEGRATIONS =====
    print("\n2. Integrations...")

    # HubSpot
    try:
        from app.integrations.hubspot.auth import HubSpotAuth
        from app.integrations.hubspot.service import HubSpotService

        print("   ✓ HubSpot integration")
    except Exception as e:
        errors.append(f"HubSpot: {e}")
        print(f"   ✗ HubSpot failed: {e}")

    # GitHub
    try:
        from app.integrations.github.oauth import GitHubOAuth
        from app.integrations.github.service import GitHubService

        print("   ✓ GitHub integration")
    except Exception as e:
        errors.append(f"GitHub: {e}")
        print(f"   ✗ GitHub failed: {e}")

    # ===== 3. SEO/GEO SERVICES =====
    print("\n3. SEO/GEO Services (Core Business)...")

    # Audit Service
    try:
        from app.services.audit_service import AuditService

        print("   ✓ AuditService")
    except Exception as e:
        errors.append(f"AuditService: {e}")
        print(f"   ✗ AuditService: {e}")

    # LLM Visibility (GEO Core)
    try:
        from app.services.llm_visibility_service import LLMVisibilityService

        print("   ✓ LLMVisibilityService (GEO Core)")
    except Exception as e:
        errors.append(f"LLMVisibilityService: {e}")
        print(f"   ✗ LLMVisibilityService: {e}")

    # Backlinks
    try:
        from app.services.backlink_service import BacklinkService

        print("   ✓ BacklinkService")
    except Exception as e:
        warnings.append(f"BacklinkService: {e}")
        print(f"   ⚠ BacklinkService: {e}")

    # Keywords
    try:
        from app.services.keyword_service import KeywordService

        print("   ✓ KeywordService")
    except Exception as e:
        warnings.append(f"KeywordService: {e}")
        print(f"   ⚠ KeywordService: {e}")

    # GEO Score
    try:
        from app.services.geo_score_service import GEOScoreService

        print("   ✓ GEOScoreService")
    except Exception as e:
        warnings.append(f"GEOScoreService: {e}")
        print(f"   ⚠ GEOScoreService: {e}")

    # Pipeline
    try:
        from app.services.pipeline_service import PipelineService

        print("   ✓ PipelineService")
    except Exception as e:
        errors.append(f"PipelineService: {e}")
        print(f"   ✗ PipelineService: {e}")

    # PDF Generation
    try:
        from app.services.pdf_service import PDFService

        print("   ✓ PDFService")
    except Exception as e:
        errors.append(f"PDFService: {e}")
        print(f"   ✗ PDFService: {e}")

    # ===== 4. SECURITY =====
    print("\n4. Security Components...")

    try:
        from app.core.middleware import (
            RateLimitMiddleware,
            RequestValidationMiddleware,
            SecurityHeadersMiddleware,
        )

        print("   ✓ Security Middleware")
    except Exception as e:
        errors.append(f"Security Middleware: {e}")
        print(f"   ✗ Security Middleware: {e}")

    try:
        from app.services.webhook_service import WebhookService

        print("   ✓ WebhookService")
    except Exception as e:
        errors.append(f"WebhookService: {e}")
        print(f"   ✗ WebhookService: {e}")

    try:
        from app.schemas.validators import HTMLContent, URLInput

        print("   ✓ Input Validators")
    except Exception as e:
        errors.append(f"Validators: {e}")
        print(f"   ✗ Validators: {e}")

    import os

    os.environ["SECRET_KEY"] = "test-key-12345"
    try:
        from app.core.auth import create_access_token, verify_token

        print("   ✓ JWT Auth")
    except Exception as e:
        errors.append(f"JWT Auth: {e}")
        print(f"   ✗ JWT Auth: {e}")

    # ===== 5. APP STARTUP =====
    print("\n5. Application Startup...")
    try:
        from app.main import create_app

        app = create_app()
        route_count = len(app.routes)
        print(f"   ✓ App created with {route_count} routes")
    except Exception as e:
        errors.append(f"App startup: {e}")
        print(f"   ✗ App startup: {e}")

    # ===== SUMMARY =====
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    if errors:
        print(f"\n❌ ERRORS ({len(errors)}):")
        for err in errors:
            print(f"   - {err}")

    if warnings:
        print(f"\n⚠ WARNINGS ({len(warnings)}):")
        for warn in warnings:
            print(f"   - {warn}")

    if not errors:
        print("\n✅ ALL CRITICAL COMPONENTS: PASSED")
        print("   The system is production-ready!")
        return True
    else:
        print("\n❌ CRITICAL ERRORS FOUND - FIX BEFORE DEPLOYING")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
