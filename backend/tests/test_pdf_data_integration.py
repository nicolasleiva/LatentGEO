import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.services.backlinks_service import BacklinksService as BacklinksServicePlural
from app.services.keywords_service import KeywordsService as KeywordsServicePlural
from app.services.pdf_service import PDFService
from app.services.rank_tracking_service import (
    RankTrackingService as RankTrackingServicePlural,
)


@pytest.mark.asyncio
async def test_keywords_service_no_invented_data():
    """Verifica que el servicio KeywordsService (plural) ya no invente datos."""
    mock_audit = {"structure": {"h1_check": {"details": {"example": "Test"}}}}
    url = "https://example.com"

    # El servicio legacy (plural) ahora es stub explícito.
    with pytest.raises(RuntimeError, match="stub"):
        KeywordsServicePlural.generate_keywords_from_audit(mock_audit, url)


@pytest.mark.asyncio
async def test_backlinks_service_no_invented_data():
    """Verifica que el servicio BacklinksService (plural) ya no invente datos."""
    url = "https://example.com"

    # El servicio legacy (plural) ahora es stub explícito.
    with pytest.raises(RuntimeError, match="stub"):
        BacklinksServicePlural.generate_backlinks_from_audit({}, url)


@pytest.mark.asyncio
async def test_rank_tracking_service_no_invented_data():
    """Verifica que el servicio RankTrackingService (plural) ya no invente datos."""
    url = "https://example.com"
    keywords = [{"keyword": "test"}]

    # El servicio legacy (plural) ahora es stub explícito.
    with pytest.raises(RuntimeError, match="stub"):
        RankTrackingServicePlural.generate_rankings_from_keywords(keywords, url)


@pytest.mark.asyncio
async def test_pdf_service_real_data_flow():
    """
    Verifica que PDFService llame a los servicios reales cuando no hay datos en la BD.
    Este test simula la generación del PDF y verifica que se intenten obtener datos reales.
    """
    mock_db = MagicMock()
    mock_audit = MagicMock()
    mock_audit.id = 1
    mock_audit.url = "https://example.com"
    mock_audit.target_audit = {}
    mock_audit.external_intelligence = {}
    mock_audit.search_results = {}
    mock_audit.competitor_audits = []

    # Simular que no hay nada en la BD
    mock_audit.pagespeed_data = None
    mock_audit.keywords = []
    mock_audit.backlinks = []
    mock_audit.rank_trackings = []
    mock_audit.llm_visibilities = []
    mock_audit.ai_content_suggestions = []
    mock_audit.report_markdown = "Test Report"

    # Configurar el mock de la DB para devolver el audit
    mock_db.query().filter().first.return_value = mock_audit
    mock_db.query().filter().all.return_value = []

    # Mock de los servicios reales para ver si son llamados
    with patch(
        "app.services.keyword_service.KeywordService.research_keywords",
        new_callable=AsyncMock,
    ) as mock_research:
        mock_research.return_value = []
        with patch(
            "app.services.backlink_service.BacklinkService.analyze_backlinks",
            new_callable=AsyncMock,
        ) as mock_backlinks:
            mock_backlinks.return_value = []
            with patch(
                "app.services.rank_tracker_service.RankTrackerService.track_rankings",
                new_callable=AsyncMock,
            ) as mock_rank:
                mock_rank.return_value = []

                # Mock de la generación de PDF para no crear archivos reales
                with patch(
                    "app.core.llm_kimi.get_llm_function", return_value=AsyncMock()
                ):
                    with patch(
                        "app.services.pipeline_service.PipelineService.generate_report",
                        new_callable=AsyncMock,
                    ) as mock_gen:
                        mock_gen.return_value = ("Report content " * 20, [])
                        with patch(
                            "app.services.pdf_service.PDFService.generate_comprehensive_pdf",
                            new_callable=AsyncMock,
                        ) as mock_pdf_gen:
                            mock_pdf_gen.return_value = "dummy.pdf"

                            # Ejecutar la lógica de generación
                            await PDFService.generate_pdf_with_complete_context(
                                mock_db, 1
                            )

                            # Verificar que se intentó obtener datos reales (porque la BD estaba vacía)
                            mock_research.assert_called_once()
                            mock_backlinks.assert_called_once()
                            # Rank tracking se llama si hay keywords. En este caso research_keywords devolvió [] así que no se llama.
                            # Pero el punto es que se llamó a la investigación real.

    print("\n[OK] Todos los tests de integración de datos pasaron satisfactoriamente.")


@pytest.mark.asyncio
async def test_pdf_service_partial_failure():
    """
    Verifica que si falla un servicio (ej. Backlinks), los demás (ej. Keywords) sigan funcionando.
    """
    mock_db = MagicMock()
    mock_audit = MagicMock()
    mock_audit.id = 1
    mock_audit.url = "https://example.com"
    mock_audit.target_audit = {}
    mock_audit.external_intelligence = {}
    mock_audit.search_results = {}
    mock_audit.competitor_audits = []

    mock_audit.pagespeed_data = None
    mock_audit.keywords = []
    mock_audit.backlinks = []
    mock_audit.rank_trackings = []
    mock_audit.llm_visibilities = []
    mock_audit.ai_content_suggestions = []
    mock_audit.report_markdown = "Test Report"

    mock_db.query().filter().first.return_value = mock_audit

    # Mock keywords success
    mock_keyword_obj = MagicMock()
    mock_keyword_obj.term = "seo test"
    mock_keyword_obj.volume = 1000
    mock_keyword_obj.difficulty = 50
    mock_keyword_obj.cpc = 1.0
    mock_keyword_obj.intent = "Commercial"

    with patch(
        "app.services.keyword_service.KeywordService.research_keywords",
        new_callable=AsyncMock,
    ) as mock_research:
        mock_research.return_value = [mock_keyword_obj]

        # Mock backlinks FAILURE
        with patch(
            "app.services.backlink_service.BacklinkService.analyze_backlinks",
            new_callable=AsyncMock,
        ) as mock_backlinks:
            mock_backlinks.side_effect = Exception("Backlink API Failure")

            # Mock PDF generation internals
            with patch("app.core.llm_kimi.get_llm_function", return_value=AsyncMock()):
                with patch(
                    "app.services.pipeline_service.PipelineService.generate_report",
                    new_callable=AsyncMock,
                ) as mock_gen:
                    mock_gen.return_value = ("Report content " * 20, [])
                    with patch(
                        "app.services.pdf_service.PDFService.generate_comprehensive_pdf",
                        new_callable=AsyncMock,
                    ) as mock_pdf_gen:
                        mock_pdf_gen.return_value = "dummy.pdf"
                        with patch(
                            "app.services.rank_tracker_service.RankTrackerService.track_rankings",
                            new_callable=AsyncMock,
                        ) as mock_rank:
                            mock_rank.return_value = []
                            with patch(
                                "app.services.llm_visibility_service.LLMVisibilityService.generate_llm_visibility",
                                new_callable=AsyncMock,
                            ) as mock_vis:
                                mock_vis.return_value = []
                                with patch(
                                    "app.services.ai_content_service.AIContentService.generate_content_suggestions",
                                    return_value=[],
                                ):
                                    await PDFService.generate_pdf_with_complete_context(
                                        mock_db, 1
                                    )

                                    # Verify Keywords were passed to generate_report
                                    args, kwargs = mock_gen.call_args
                                    passed_keywords = kwargs.get("keywords_data", {})

                                    assert passed_keywords is not None
                                    assert (
                                        passed_keywords.get("total_keywords") == 1
                                    ), "Keywords should be present even if Backlinks failed"

                                    # Verify Backlinks were passed as empty dict
                                    passed_backlinks = kwargs.get("backlinks_data", {})
                                    assert (
                                        passed_backlinks == {}
                                    ), "Backlinks should be empty dict on failure"

    print("\n[OK] Test de fallo parcial exitoso.")


@pytest.mark.asyncio
async def test_pdf_service_fallback_to_db():
    """
    Verifica que si falla la generación fresca, se use la data existente en BD.
    """
    mock_db = MagicMock()
    mock_audit = MagicMock()
    mock_audit.id = 1
    mock_audit.url = "https://example.com"
    mock_audit.target_audit = {}
    mock_audit.external_intelligence = {}
    mock_audit.search_results = {}
    mock_audit.competitor_audits = []

    # Existing DB data
    mock_kw = MagicMock()
    mock_kw.term = "fallback keyword"
    mock_kw.volume = 500
    mock_kw.difficulty = 50  # Assign int for comparison
    mock_audit.keywords = [mock_kw]

    # PageSpeed fallback
    mock_audit.pagespeed_data = {"mobile": {"score": 90}}

    # Backlinks fallback
    mock_bl = MagicMock()
    mock_bl.source_url = "http://backlink.com"
    mock_bl.domain_authority = 50
    mock_bl.is_dofollow = True
    mock_audit.backlinks = [mock_bl]

    mock_db.query().filter().first.return_value = mock_audit

    # Mock SERVICES FAILURE
    with patch(
        "app.services.keyword_service.KeywordService.research_keywords",
        side_effect=Exception("API Fail"),
    ):
        with patch(
            "app.services.backlink_service.BacklinkService.analyze_backlinks",
            side_effect=Exception("API Fail"),
        ):
            with patch(
                "app.services.pagespeed_service.PageSpeedService.analyze_both_strategies",
                side_effect=Exception("API Fail"),
            ):
                with patch(
                    "app.services.rank_tracker_service.RankTrackerService.track_rankings",
                    new_callable=AsyncMock,
                ) as mock_rank:
                    mock_rank.return_value = (
                        []
                    )  # Let rank succeed or fail, doesn't matter for this test

                # Mock internals
                with patch(
                    "app.core.llm_kimi.get_llm_function", return_value=AsyncMock()
                ):
                    with patch(
                        "app.services.pipeline_service.PipelineService.generate_report",
                        new_callable=AsyncMock,
                    ) as mock_gen:
                        mock_gen.return_value = ("Report content " * 20, [])
                        with patch(
                            "app.services.pdf_service.PDFService.generate_comprehensive_pdf",
                            new_callable=AsyncMock,
                        ) as mock_pdf_gen:
                            mock_pdf_gen.return_value = "dummy.pdf"
                            with patch(
                                "app.services.llm_visibility_service.LLMVisibilityService.generate_llm_visibility",
                                new_callable=AsyncMock,
                            ):
                                with patch(
                                    "app.services.ai_content_service.AIContentService.generate_content_suggestions",
                                    return_value=[],
                                ):
                                    await PDFService.generate_pdf_with_complete_context(
                                        mock_db, 1
                                    )

                                    args, kwargs = mock_gen.call_args

                                    # Verify Keywords fallback
                                    k_data = kwargs.get("keywords_data", {})
                                    assert k_data.get("total_keywords") == 1
                                    assert (
                                        k_data["items"][0]["keyword"]
                                        == "fallback keyword"
                                    )

                                    # Verify Backlinks fallback
                                    b_data = kwargs.get("backlinks_data", {})
                                    assert b_data.get("total_backlinks") == 1

                                    # Verify PageSpeed fallback
                                    p_data = kwargs.get("pagespeed_data", {})
                                    assert p_data["mobile"]["score"] == 90

    print("\n[OK] Test de fallback a BD exitoso.")


if __name__ == "__main__":
    asyncio.run(test_keywords_service_no_invented_data())
    asyncio.run(test_backlinks_service_no_invented_data())
    asyncio.run(test_rank_tracking_service_no_invented_data())
    asyncio.run(test_pdf_service_real_data_flow())
    asyncio.run(test_pdf_service_partial_failure())
    asyncio.run(test_pdf_service_fallback_to_db())
