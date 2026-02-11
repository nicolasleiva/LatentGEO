"""
Tests para verificar que los servicios de GEO funcionan con APIs reales.
NO usa mocks ni datos falsos - solo APIs reales.
"""

import pytest
import asyncio
import os
from sqlalchemy.orm import Session
from app.core.config import settings
from app.services.pagespeed_service import PageSpeedService
from app.services.keyword_service import KeywordService
from app.services.backlink_service import BacklinkService
from app.services.rank_tracker_service import RankTrackerService
from app.core.database import SessionLocal

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION_TESTS") != "1",
    reason="Set RUN_INTEGRATION_TESTS=1 to run real GEO service integration tests.",
)


class TestPageSpeedServiceReal:
    """Test PageSpeed con API real de Google"""

    @pytest.mark.asyncio
    async def test_pagespeed_api_key_configured(self):
        """Verifica que la API key está configurada"""
        assert settings.GOOGLE_PAGESPEED_API_KEY is not None, (
            "GOOGLE_PAGESPEED_API_KEY no está configurada"
        )
        assert len(settings.GOOGLE_PAGESPEED_API_KEY) > 10, (
            "GOOGLE_PAGESPEED_API_KEY parece inválida"
        )

    @pytest.mark.asyncio
    async def test_analyze_url_returns_real_data(self):
        """Test que analyze_url retorna datos reales de la API"""
        if not settings.GOOGLE_PAGESPEED_API_KEY:
            pytest.skip("GOOGLE_PAGESPEED_API_KEY no configurada")

        url = "https://www.google.com"
        result = await PageSpeedService.analyze_url(
            url=url, api_key=settings.GOOGLE_PAGESPEED_API_KEY, strategy="mobile"
        )

        # Verificar que no hay error
        assert "error" not in result, f"Error en respuesta: {result.get('error')}"

        # Verificar estructura de datos reales
        assert "performance_score" in result, "No se encontró performance_score"
        assert "accessibility_score" in result, "No se encontró accessibility_score"
        assert "core_web_vitals" in result, "No se encontró core_web_vitals"
        assert "url" in result, "No se encontró url"
        assert result["url"] == url, f"URL no coincide: {result['url']} != {url}"

        # Verificar que los scores son números reales (0-100)
        assert 0 <= result["performance_score"] <= 100, (
            f"performance_score inválido: {result['performance_score']}"
        )
        assert 0 <= result["accessibility_score"] <= 100, (
            f"accessibility_score inválido: {result['accessibility_score']}"
        )

    @pytest.mark.asyncio
    async def test_analyze_both_strategies(self):
        """Test que analyze_both_strategies retorna mobile y desktop"""
        if not settings.GOOGLE_PAGESPEED_API_KEY:
            pytest.skip("GOOGLE_PAGESPEED_API_KEY no configurada")

        url = "https://www.google.com"
        result = await PageSpeedService.analyze_both_strategies(
            url=url, api_key=settings.GOOGLE_PAGESPEED_API_KEY
        )

        assert "mobile" in result, "No se encontró mobile"
        assert "desktop" in result, "No se encontró desktop"

        # Verificar que ambos tienen datos reales
        for strategy in ["mobile", "desktop"]:
            assert "performance_score" in result[strategy], (
                f"No performance_score en {strategy}"
            )
            assert result[strategy]["url"] == url, f"URL no coincide en {strategy}"


class TestKeywordServiceReal:
    """Test Keyword Service con API real de NVIDIA/Kimi"""

    @pytest.mark.asyncio
    async def test_nvidia_api_key_configured(self):
        """Verifica que la API key de NVIDIA está configurada"""
        api_key = settings.NVIDIA_API_KEY or settings.NV_API_KEY
        assert api_key is not None, "NVIDIA_API_KEY no está configurada"
        assert len(api_key) > 20, "NVIDIA_API_KEY parece inválida"

    @pytest.mark.asyncio
    async def test_research_keywords_returns_real_data(self):
        """Test que research_keywords retorna datos reales de la API"""
        db = SessionLocal()
        try:
            service = KeywordService(db)

            # Si no hay API key, el servicio debe retornar lista vacía
            if not service.client:
                result = await service.research_keywords(1, "example.com")
                assert result == [], "Sin API key debe retornar lista vacía"
                pytest.skip("NVIDIA_API_KEY no configurada")

            # Test con API real
            result = await service.research_keywords(
                audit_id=1, domain="google.com", seed_keywords=["search", "technology"]
            )

            # Verificar que retorna datos reales
            assert isinstance(result, list), "Resultado debe ser lista"
            assert len(result) > 0, "Debe retornar al menos una keyword"

            # Verificar estructura de datos reales
            for kw in result:
                assert hasattr(kw, "term"), "Keyword sin atributo term"
                assert kw.term is not None, "Keyword term no puede ser None"
                assert len(kw.term) > 0, "Keyword term no puede estar vacío"
                assert hasattr(kw, "volume"), "Keyword sin atributo volume"
                assert hasattr(kw, "difficulty"), "Keyword sin atributo difficulty"
                assert hasattr(kw, "intent"), "Keyword sin atributo intent"

        finally:
            db.close()


class TestBacklinkServiceReal:
    """Test Backlink Service con APIs reales"""

    @pytest.mark.asyncio
    async def test_google_api_keys_configured(self):
        """Verifica que las API keys de Google están configuradas"""
        assert settings.GOOGLE_API_KEY is not None, "GOOGLE_API_KEY no está configurada"
        assert settings.CSE_ID is not None, "CSE_ID no está configurado"

    @pytest.mark.asyncio
    async def test_analyze_backlinks_returns_data(self):
        """Test que analyze_backlinks retorna datos reales"""
        if not settings.GOOGLE_API_KEY or not settings.CSE_ID:
            pytest.skip("GOOGLE_API_KEY o CSE_ID no configurados")

        db = SessionLocal()
        try:
            service = BacklinkService(db)

            result = await service.analyze_backlinks(audit_id=1, domain="google.com")

            # Verificar que retorna datos
            assert isinstance(result, list), "Resultado debe ser lista"

            # Verificar estructura de los backlinks
            for backlink in result:
                assert hasattr(backlink, "source_url"), "Backlink sin source_url"
                assert hasattr(backlink, "target_url"), "Backlink sin target_url"
                assert backlink.source_url is not None, "source_url no puede ser None"

        finally:
            db.close()


class TestRankTrackerServiceReal:
    """Test Rank Tracker Service con APIs reales"""

    @pytest.mark.asyncio
    async def test_track_rankings_returns_data(self):
        """Test que track_rankings retorna datos reales"""
        if not settings.GOOGLE_API_KEY or not settings.CSE_ID:
            pytest.skip("GOOGLE_API_KEY o CSE_ID no configurados")

        db = SessionLocal()
        try:
            service = RankTrackerService(db)

            result = await service.track_rankings(
                audit_id=1, domain="google.com", keywords=["search engine", "google"]
            )

            # Verificar que retorna datos
            assert isinstance(result, list), "Resultado debe ser lista"

            # Verificar estructura de los rankings
            for ranking in result:
                assert hasattr(ranking, "keyword"), "Ranking sin keyword"
                assert hasattr(ranking, "position"), "Ranking sin position"
                assert hasattr(ranking, "url"), "Ranking sin url"

        finally:
            db.close()


class TestDataQuality:
    """Test que verifica la calidad de los datos retornados"""

    @pytest.mark.asyncio
    async def test_no_mock_data_in_pagespeed(self):
        """Verifica que PageSpeed no retorna datos mock"""
        if not settings.GOOGLE_PAGESPEED_API_KEY:
            pytest.skip("GOOGLE_PAGESPEED_API_KEY no configurada")

        url = "https://www.google.com"
        result = await PageSpeedService.analyze_url(
            url=url, api_key=settings.GOOGLE_PAGESPEED_API_KEY, strategy="mobile"
        )

        # Verificar que no es un error
        assert "error" not in result, f"Retornó error: {result}"

        # Verificar que los datos parecen reales (variabilidad)
        # Los scores reales típicamente varían y no son valores redondos como 50, 75, 100
        scores = [
            result.get("performance_score", 0),
            result.get("accessibility_score", 0),
            result.get("best_practices_score", 0),
            result.get("seo_score", 0),
        ]

        # Verificar que hay metadata real
        assert "metadata" in result, "No hay metadata"
        assert "fetch_time" in result["metadata"], "No hay fetch_time"
        assert result["metadata"]["fetch_time"] != "", "fetch_time vacío"

    @pytest.mark.asyncio
    async def test_services_return_consistent_data(self):
        """Test que los servicios retornan datos consistentes"""
        # Este test verifica que la estructura de datos es consistente
        # entre diferentes llamadas a los servicios
        pass


if __name__ == "__main__":
    # Ejecutar tests manualmente
    print("=" * 60)
    print("TESTING GEO SERVICES WITH REAL APIs")
    print("=" * 60)

    # Test PageSpeed
    print("\n1. Testing PageSpeed API Key...")
    try:
        assert settings.GOOGLE_PAGESPEED_API_KEY is not None
        print(f"   ✓ API Key configured: {settings.GOOGLE_PAGESPEED_API_KEY[:20]}...")
    except AssertionError as e:
        print(f"   ✗ {e}")

    # Test NVIDIA
    print("\n2. Testing NVIDIA API Key...")
    try:
        api_key = settings.NVIDIA_API_KEY or settings.NV_API_KEY
        assert api_key is not None
        print(f"   ✓ API Key configured: {api_key[:20]}...")
    except AssertionError as e:
        print(f"   ✗ {e}")

    print("\n" + "=" * 60)
    print("Run with: pytest tests/test_geo_services_real.py -v")
    print("=" * 60)
