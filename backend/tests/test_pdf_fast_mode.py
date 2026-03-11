import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.services.pdf_service import PDFService


@pytest.mark.asyncio
async def test_pdf_generation_uses_cached_geo_data_when_fresh_mode_disabled():
    mock_db = MagicMock()
    mock_audit = MagicMock()
    mock_audit.id = 1
    mock_audit.url = "https://example.com"
    mock_audit.target_audit = {"market": "argentina", "geo_score": 70}
    mock_audit.external_intelligence = {
        "category": "Education",
        "subcategory": "Bootcamp",
        "market": "argentina",
        "queries_to_run": ["coding bootcamp argentina"],
    }
    mock_audit.search_results = {}
    mock_audit.competitor_audits = []
    mock_audit.pagespeed_data = {
        "mobile": {"metadata": {"fetch_time": "2099-01-01T00:00:00Z"}}
    }
    mock_audit.keywords = [
        SimpleNamespace(
            term="nike running shoes",
            volume=1200,
            difficulty=40,
            cpc=1.2,
            intent="commercial",
        )
    ]
    mock_audit.backlinks = [
        SimpleNamespace(
            source_url="https://example.org/article",
            target_url="https://example.com/product",
            anchor_text="source",
            domain_authority=45,
            is_dofollow=True,
        )
    ]
    mock_audit.rank_trackings = [
        SimpleNamespace(
            keyword="nike running shoes", position=8, url="https://example.com/product"
        )
    ]
    mock_audit.llm_visibilities = [
        SimpleNamespace(
            query="best nike shoes",
            llm_name="ChatGPT",
            is_visible=True,
            rank=4,
            citation_text="Example citation",
        )
    ]
    mock_audit.ai_content_suggestions = [
        SimpleNamespace(
            topic="Best Nike Shoes Guide",
            suggestion_type="article",
            content_outline={"h2": ["Intro"]},
            priority="high",
            page_url="https://example.com/blog",
        )
    ]
    mock_audit.report_markdown = "Persisted report content. " * 10
    mock_audit.fix_plan = [{"issue": "existing fix"}]

    with patch.dict(
        os.environ,
        {"PDF_FORCE_FRESH_GEO": "false", "PDF_ALWAYS_FULL_MODE": "false"},
        clear=False,
    ), patch(
        "app.services.audit_service.AuditService.get_audit",
        return_value=mock_audit,
    ), patch(
        "app.services.audit_service.AuditService.get_audited_pages",
        return_value=[],
    ), patch(
        "app.services.audit_service.CompetitorService.get_competitors",
        return_value=[],
    ), patch(
        "app.services.keyword_service.KeywordService.research_keywords",
        new_callable=AsyncMock,
    ) as mock_fresh_keywords, patch(
        "app.services.backlink_service.BacklinkService.analyze_backlinks",
        new_callable=AsyncMock,
    ), patch(
        "app.services.rank_tracker_service.RankTrackerService.track_rankings",
        new_callable=AsyncMock,
    ), patch(
        "app.services.llm_visibility_service.LLMVisibilityService.check_visibility",
        new_callable=AsyncMock,
    ), patch(
        "app.services.pipeline_service.PipelineService.generate_report",
        new_callable=AsyncMock,
        return_value=("Regenerated report content. " * 20, []),
    ), patch(
        "app.services.product_intelligence_service.ProductIntelligenceService.analyze",
        new_callable=AsyncMock,
        side_effect=Exception("skip product intelligence in test"),
    ), patch(
        "app.services.pdf_service.PDFService.generate_comprehensive_pdf",
        new_callable=AsyncMock,
        return_value="dummy.pdf",
    ) as mock_pdf_generator:
        pdf_path = await PDFService.generate_pdf_with_complete_context(mock_db, 1)

    assert pdf_path == "dummy.pdf"
    mock_pdf_generator.assert_awaited_once()
    mock_fresh_keywords.assert_not_called()


@pytest.mark.asyncio
async def test_pdf_generation_handles_null_cached_opportunity_scores():
    mock_db = MagicMock()
    mock_audit = MagicMock()
    mock_audit.id = 99
    mock_audit.url = "https://example.com"
    mock_audit.target_audit = {"market": "argentina", "geo_score": 70}
    mock_audit.external_intelligence = {
        "category": "Education",
        "subcategory": "Bootcamp",
        "market": "argentina",
        "queries_to_run": ["coding bootcamp argentina"],
    }
    mock_audit.search_results = {}
    mock_audit.competitor_audits = []
    mock_audit.pagespeed_data = {
        "mobile": {"metadata": {"fetch_time": "2099-01-01T00:00:00Z"}}
    }
    mock_audit.report_markdown = "Persisted report content. " * 10
    mock_audit.fix_plan = [{"issue": "existing fix"}]

    cached_context = {
        "keywords": [
            {
                "keyword": "nike pegasus 40",
                "search_volume": 1200,
                "difficulty": 44,
                "cpc": 1.9,
                "intent": "commercial",
                "opportunity_score": None,
            },
            {
                "keyword": "nike vomero 17",
                "search_volume": 900,
                "difficulty": 40,
                "cpc": 1.5,
                "intent": "commercial",
                "opportunity_score": None,
            },
        ],
        "backlinks": {
            "top_backlinks": [],
            "total_backlinks": 0,
            "referring_domains": 0,
        },
        "rank_tracking": [],
        "llm_visibility": [],
        "ai_content_suggestions": [],
    }

    with patch.dict(
        os.environ,
        {"PDF_FORCE_FRESH_GEO": "false", "PDF_ALWAYS_FULL_MODE": "false"},
        clear=False,
    ), patch(
        "app.services.audit_service.AuditService.get_audit",
        return_value=mock_audit,
    ), patch(
        "app.services.audit_service.AuditService.get_audited_pages",
        return_value=[],
    ), patch(
        "app.services.audit_service.CompetitorService.get_competitors",
        return_value=[],
    ), patch(
        "app.services.pdf_service.PDFService._load_complete_audit_context",
        return_value=cached_context,
    ), patch(
        "app.services.keyword_service.KeywordService.research_keywords",
        new_callable=AsyncMock,
    ) as mock_fresh_keywords, patch(
        "app.services.backlink_service.BacklinkService.analyze_backlinks",
        new_callable=AsyncMock,
    ), patch(
        "app.services.rank_tracker_service.RankTrackerService.track_rankings",
        new_callable=AsyncMock,
    ), patch(
        "app.services.llm_visibility_service.LLMVisibilityService.check_visibility",
        new_callable=AsyncMock,
    ), patch(
        "app.services.pipeline_service.PipelineService.generate_report",
        new_callable=AsyncMock,
        return_value=("Regenerated report content. " * 20, []),
    ), patch(
        "app.services.product_intelligence_service.ProductIntelligenceService.analyze",
        new_callable=AsyncMock,
        side_effect=Exception("skip product intelligence in test"),
    ), patch(
        "app.services.pdf_service.PDFService.generate_comprehensive_pdf",
        new_callable=AsyncMock,
        return_value="dummy.pdf",
    ) as mock_pdf_generator:
        pdf_path = await PDFService.generate_pdf_with_complete_context(mock_db, 99)

    assert pdf_path == "dummy.pdf"
    mock_pdf_generator.assert_awaited_once()
    mock_fresh_keywords.assert_not_called()


@pytest.mark.asyncio
async def test_pdf_generation_uses_report_cache_when_signature_matches():
    mock_db = MagicMock()
    mock_audit = MagicMock()
    mock_audit.id = 55
    mock_audit.url = "https://example.com"
    mock_audit.domain = "example.com"
    mock_audit.target_audit = {"market": "argentina", "geo_score": 70}
    mock_audit.external_intelligence = {
        "category": "Education",
        "subcategory": "Bootcamp",
        "market": "argentina",
        "queries_to_run": ["coding bootcamp argentina"],
    }
    mock_audit.search_results = {}
    mock_audit.competitor_audits = []
    mock_audit.pagespeed_data = {
        "mobile": {"metadata": {"fetch_time": "2099-01-01T00:00:00Z"}}
    }
    mock_audit.keywords = []
    mock_audit.backlinks = []
    mock_audit.rank_trackings = []
    mock_audit.llm_visibilities = []
    mock_audit.ai_content_suggestions = []
    mock_audit.report_markdown = "Cached markdown content. " * 20
    mock_audit.fix_plan = [{"issue": "cached"}]

    cached_context = {
        "keywords": [{"keyword": "bootcamp", "search_volume": 1000}],
        "backlinks": {
            "top_backlinks": [],
            "total_backlinks": 0,
            "referring_domains": 0,
        },
        "rank_tracking": [],
        "llm_visibility": [],
        "ai_content_suggestions": [],
    }

    with patch.dict(
        os.environ,
        {"PDF_FORCE_FRESH_GEO": "false", "PDF_ALWAYS_FULL_MODE": "false"},
        clear=False,
    ), patch(
        "app.services.audit_service.AuditService.get_audit",
        return_value=mock_audit,
    ), patch(
        "app.services.audit_service.AuditService.get_audited_pages",
        return_value=[],
    ), patch(
        "app.services.audit_service.CompetitorService.get_competitors",
        return_value=[],
    ), patch(
        "app.services.pdf_service.PDFService._load_complete_audit_context",
        return_value=cached_context,
    ), patch(
        "app.services.pdf_service.PDFService._compute_report_context_signature",
        return_value="sig-123",
    ), patch(
        "app.services.pdf_service.PDFService._load_saved_report_signature",
        return_value="sig-123",
    ), patch(
        "app.services.keyword_service.KeywordService.research_keywords",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "app.services.backlink_service.BacklinkService.analyze_backlinks",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "app.services.rank_tracker_service.RankTrackerService.track_rankings",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "app.services.llm_visibility_service.LLMVisibilityService.check_visibility",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "app.services.ai_content_service.AIContentService.generate_suggestions",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "app.services.pipeline_service.PipelineService.generate_report",
        new_callable=AsyncMock,
    ) as mock_generate_report, patch(
        "app.services.pdf_service.PDFService.generate_comprehensive_pdf",
        new_callable=AsyncMock,
        return_value="dummy.pdf",
    ):
        result = await PDFService.generate_pdf_with_complete_context(
            mock_db, 55, return_details=True
        )

    assert result["pdf_path"] == "dummy.pdf"
    assert result["report_cache_hit"] is True
    assert result["report_regenerated"] is False
    assert result["generation_mode"] == "report_cache_hit"
    mock_generate_report.assert_not_called()


@pytest.mark.asyncio
async def test_pdf_generation_uses_reloaded_canonical_context_for_signature_cache():
    mock_db = MagicMock()
    mock_db.refresh = MagicMock()
    mock_audit = MagicMock()
    mock_audit.id = 58
    mock_audit.url = "https://example.com"
    mock_audit.domain = "example.com"
    mock_audit.target_audit = {"market": "argentina", "geo_score": 70}
    mock_audit.external_intelligence = {
        "category": "Education",
        "subcategory": "Bootcamp",
        "market": "argentina",
        "queries_to_run": ["coding bootcamp argentina"],
    }
    mock_audit.search_results = {}
    mock_audit.competitor_audits = []
    mock_audit.pagespeed_data = {
        "mobile": {"metadata": {"fetch_time": "2099-01-01T00:00:00Z"}}
    }
    mock_audit.keywords = []
    mock_audit.backlinks = []
    mock_audit.rank_trackings = []
    mock_audit.llm_visibilities = []
    mock_audit.ai_content_suggestions = []
    mock_audit.report_markdown = "Cached markdown content. " * 20
    mock_audit.fix_plan = [{"issue": "cached"}]

    initial_context = {
        "keywords": [],
        "backlinks": {
            "top_backlinks": [],
            "total_backlinks": 0,
            "referring_domains": 0,
        },
        "rank_tracking": [],
        "llm_visibility": [],
        "ai_content_suggestions": [],
        "pagespeed": mock_audit.pagespeed_data,
    }
    canonical_context = {
        "keywords": [
            {"keyword": f"bootcamp term {index}", "search_volume": 100 + index}
            for index in range(10)
        ],
        "backlinks": {
            "top_backlinks": [
                {
                    "source_url": "https://ref.example.org/article",
                    "target_url": "https://example.com/",
                    "anchor_text": "bootcamp",
                    "domain_authority": 42,
                    "link_type": "dofollow",
                }
            ],
            "total_backlinks": 1,
            "referring_domains": 1,
        },
        "rank_tracking": [
            {
                "keyword": "coding bootcamp argentina",
                "position": 4,
                "url": "https://example.com/",
            }
        ],
        "llm_visibility": [
            {
                "query": "best coding bootcamp argentina",
                "mentioned": True,
                "position": 2,
            }
        ],
        "ai_content_suggestions": [
            {
                "title": "Coding Bootcamp Guide",
                "priority": "high",
                "target_keyword": "coding bootcamp argentina",
            }
        ],
        "pagespeed": mock_audit.pagespeed_data,
    }
    canonical_signature_inputs = (
        PDFService._build_signature_inputs_from_complete_context(
            canonical_context,
            mock_audit.pagespeed_data,
        )
    )
    expected_signature = PDFService._compute_report_context_signature(
        audit=mock_audit,
        pagespeed_data=canonical_signature_inputs["pagespeed_data"],
        keywords_data=canonical_signature_inputs["keywords_data"],
        backlinks_data=canonical_signature_inputs["backlinks_data"],
        rank_tracking_data=canonical_signature_inputs["rank_tracking_data"],
        llm_visibility_data=canonical_signature_inputs["llm_visibility_data"],
        ai_content_suggestions=canonical_signature_inputs["ai_content_suggestions"],
    )

    fresh_keywords = [
        {"keyword": f"fresh keyword {index}", "search_volume": 1000 + index}
        for index in range(20)
    ]
    fresh_backlinks = [
        SimpleNamespace(
            source_url="https://fresh.example.org/article",
            target_url="https://example.com/",
            anchor_text="fresh link",
            domain_authority=39,
            is_dofollow=True,
        )
    ]
    fresh_rankings = [
        {
            "keyword": "coding bootcamp argentina",
            "position": 4,
            "url": "https://example.com/",
        }
    ]
    fresh_llm_visibility = [
        {
            "query": "best coding bootcamp argentina",
            "is_visible": True,
            "rank": 2,
        }
    ]
    fresh_ai_suggestions = [
        {
            "title": "Coding Bootcamp Guide",
            "priority": "high",
            "target_keyword": "coding bootcamp argentina",
        }
    ]

    with patch.dict(
        os.environ,
        {"PDF_FORCE_FRESH_GEO": "false", "PDF_ALWAYS_FULL_MODE": "false"},
        clear=False,
    ), patch(
        "app.services.audit_service.AuditService.get_audit",
        return_value=mock_audit,
    ), patch(
        "app.services.audit_service.AuditService.get_audited_pages",
        return_value=[],
    ), patch(
        "app.services.audit_service.CompetitorService.get_competitors",
        return_value=[],
    ), patch(
        "app.services.pdf_service.PDFService._load_complete_audit_context",
        side_effect=[initial_context, canonical_context],
    ), patch(
        "app.services.pdf_service.PDFService._load_saved_report_signature",
        return_value=expected_signature,
    ), patch(
        "app.services.keyword_service.KeywordService.research_keywords",
        new_callable=AsyncMock,
        return_value=fresh_keywords,
    ), patch(
        "app.services.backlink_service.BacklinkService.analyze_backlinks",
        new_callable=AsyncMock,
        return_value=fresh_backlinks,
    ), patch(
        "app.services.rank_tracker_service.RankTrackerService.track_rankings",
        new_callable=AsyncMock,
        return_value=fresh_rankings,
    ), patch(
        "app.services.llm_visibility_service.LLMVisibilityService.check_visibility",
        new_callable=AsyncMock,
        return_value=fresh_llm_visibility,
    ), patch(
        "app.services.ai_content_service.AIContentService.generate_suggestions",
        new_callable=AsyncMock,
        return_value=fresh_ai_suggestions,
    ), patch(
        "app.services.pipeline_service.PipelineService.generate_report",
        new_callable=AsyncMock,
    ) as mock_generate_report, patch(
        "app.services.product_intelligence_service.ProductIntelligenceService.analyze",
        new_callable=AsyncMock,
        side_effect=Exception("skip product intelligence in test"),
    ), patch(
        "app.services.pdf_service.PDFService.generate_comprehensive_pdf",
        new_callable=AsyncMock,
        return_value="dummy.pdf",
    ):
        result = await PDFService.generate_pdf_with_complete_context(
            mock_db, 58, return_details=True
        )

    assert result["pdf_path"] == "dummy.pdf"
    assert result["report_cache_hit"] is True
    assert result["report_regenerated"] is False
    assert result["generation_mode"] == "report_cache_hit"
    mock_generate_report.assert_not_called()


@pytest.mark.asyncio
async def test_pdf_generation_ignores_cached_deterministic_report():
    mock_db = MagicMock()
    mock_audit = MagicMock()
    mock_audit.id = 57
    mock_audit.url = "https://example.com"
    mock_audit.domain = "example.com"
    mock_audit.target_audit = {"market": "argentina", "geo_score": 70}
    mock_audit.external_intelligence = {
        "category": "Education",
        "subcategory": "Bootcamp",
        "market": "argentina",
        "queries_to_run": ["coding bootcamp argentina"],
    }
    mock_audit.search_results = {}
    mock_audit.competitor_audits = []
    mock_audit.pagespeed_data = {
        "mobile": {"metadata": {"fetch_time": "2099-01-01T00:00:00Z"}}
    }
    mock_audit.keywords = []
    mock_audit.backlinks = []
    mock_audit.rank_trackings = []
    mock_audit.llm_visibilities = []
    mock_audit.ai_content_suggestions = []
    mock_audit.report_markdown = "# GEO Audit Report\n\n## Generation Mode\n- Mode: full_deterministic_regenerated\n"
    mock_audit.fix_plan = []

    cached_context = {
        "keywords": [{"keyword": "bootcamp", "search_volume": 1000}],
        "backlinks": {
            "top_backlinks": [],
            "total_backlinks": 0,
            "referring_domains": 0,
        },
        "rank_tracking": [],
        "llm_visibility": [],
        "ai_content_suggestions": [],
    }

    with patch.dict(
        os.environ,
        {"PDF_FORCE_FRESH_GEO": "false", "PDF_ALWAYS_FULL_MODE": "false"},
        clear=False,
    ), patch(
        "app.services.audit_service.AuditService.get_audit",
        return_value=mock_audit,
    ), patch(
        "app.services.audit_service.AuditService.get_audited_pages",
        return_value=[],
    ), patch(
        "app.services.audit_service.CompetitorService.get_competitors",
        return_value=[],
    ), patch(
        "app.services.pdf_service.PDFService._load_complete_audit_context",
        return_value=cached_context,
    ), patch(
        "app.services.pdf_service.PDFService._compute_report_context_signature",
        return_value="sig-123",
    ), patch(
        "app.services.pdf_service.PDFService._load_saved_report_signature",
        return_value="sig-123",
    ), patch(
        "app.services.keyword_service.KeywordService.research_keywords",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "app.services.backlink_service.BacklinkService.analyze_backlinks",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "app.services.rank_tracker_service.RankTrackerService.track_rankings",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "app.services.llm_visibility_service.LLMVisibilityService.check_visibility",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "app.services.ai_content_service.AIContentService.generate_suggestions",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "app.services.product_intelligence_service.ProductIntelligenceService.analyze",
        new_callable=AsyncMock,
        side_effect=Exception("skip product intelligence in test"),
    ), patch(
        "app.services.pipeline_service.PipelineService.generate_report",
        new_callable=AsyncMock,
        return_value=("Regenerated report content. " * 20, []),
    ) as mock_generate_report, patch(
        "app.services.pdf_service.PDFService.generate_comprehensive_pdf",
        new_callable=AsyncMock,
        return_value="dummy.pdf",
    ):
        result = await PDFService.generate_pdf_with_complete_context(
            mock_db, 57, return_details=True
        )

    assert result["report_cache_hit"] is False
    assert result["report_persisted"] is True
    assert result["generation_mode"] == "report_regenerated"
    mock_generate_report.assert_awaited_once()


@pytest.mark.asyncio
async def test_pdf_generation_force_report_refresh_bypasses_cache():
    mock_db = MagicMock()
    mock_audit = MagicMock()
    mock_audit.id = 56
    mock_audit.url = "https://example.com"
    mock_audit.domain = "example.com"
    mock_audit.target_audit = {"market": "argentina", "geo_score": 70}
    mock_audit.external_intelligence = {
        "category": "Education",
        "subcategory": "Bootcamp",
        "market": "argentina",
        "queries_to_run": ["coding bootcamp argentina"],
    }
    mock_audit.search_results = {}
    mock_audit.competitor_audits = []
    mock_audit.pagespeed_data = {
        "mobile": {"metadata": {"fetch_time": "2099-01-01T00:00:00Z"}}
    }
    mock_audit.keywords = []
    mock_audit.backlinks = []
    mock_audit.rank_trackings = []
    mock_audit.llm_visibilities = []
    mock_audit.ai_content_suggestions = []
    mock_audit.report_markdown = "Cached markdown content. " * 20
    mock_audit.fix_plan = [{"issue": "cached"}]

    cached_context = {
        "keywords": [{"keyword": "bootcamp", "search_volume": 1000}],
        "backlinks": {
            "top_backlinks": [],
            "total_backlinks": 0,
            "referring_domains": 0,
        },
        "rank_tracking": [],
        "llm_visibility": [],
        "ai_content_suggestions": [],
    }

    with patch.dict(
        os.environ,
        {"PDF_FORCE_FRESH_GEO": "false", "PDF_ALWAYS_FULL_MODE": "false"},
        clear=False,
    ), patch(
        "app.services.audit_service.AuditService.get_audit",
        return_value=mock_audit,
    ), patch(
        "app.services.audit_service.AuditService.get_audited_pages",
        return_value=[],
    ), patch(
        "app.services.audit_service.CompetitorService.get_competitors",
        return_value=[],
    ), patch(
        "app.services.pdf_service.PDFService._load_complete_audit_context",
        return_value=cached_context,
    ), patch(
        "app.services.pdf_service.PDFService._compute_report_context_signature",
        return_value="sig-123",
    ), patch(
        "app.services.pdf_service.PDFService._load_saved_report_signature",
        return_value="sig-123",
    ), patch(
        "app.services.keyword_service.KeywordService.research_keywords",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "app.services.backlink_service.BacklinkService.analyze_backlinks",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "app.services.rank_tracker_service.RankTrackerService.track_rankings",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "app.services.llm_visibility_service.LLMVisibilityService.check_visibility",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "app.services.ai_content_service.AIContentService.generate_suggestions",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "app.services.pdf_service.PDFService._save_report_signature"
    ), patch(
        "app.services.pipeline_service.PipelineService.generate_report",
        new_callable=AsyncMock,
        return_value=("Regenerated report content. " * 20, []),
    ) as mock_generate_report, patch(
        "app.services.product_intelligence_service.ProductIntelligenceService.analyze",
        new_callable=AsyncMock,
        side_effect=Exception("skip product intelligence in test"),
    ), patch(
        "app.services.pdf_service.PDFService.generate_comprehensive_pdf",
        new_callable=AsyncMock,
        return_value="dummy.pdf",
    ):
        result = await PDFService.generate_pdf_with_complete_context(
            mock_db,
            56,
            force_report_refresh=True,
            return_details=True,
        )

    assert result["pdf_path"] == "dummy.pdf"
    assert result["report_cache_hit"] is False
    assert result["report_regenerated"] is True
    assert result["generation_mode"] == "report_regenerated"
    mock_generate_report.assert_awaited_once()


@pytest.mark.asyncio
async def test_pdf_generation_caps_keyword_context_to_30_items():
    mock_db = MagicMock()
    mock_audit = MagicMock()
    mock_audit.id = 88
    mock_audit.url = "https://example.com"
    mock_audit.domain = "example.com"
    mock_audit.target_audit = {"market": "argentina", "geo_score": 70}
    mock_audit.external_intelligence = {
        "category": "Education",
        "subcategory": "Bootcamp",
        "market": "argentina",
        "queries_to_run": ["coding bootcamp argentina"],
    }
    mock_audit.search_results = {}
    mock_audit.competitor_audits = []
    mock_audit.pagespeed_data = {
        "mobile": {"metadata": {"fetch_time": "2099-01-01T00:00:00Z"}}
    }
    mock_audit.keywords = []
    mock_audit.backlinks = []
    mock_audit.rank_trackings = []
    mock_audit.llm_visibilities = []
    mock_audit.ai_content_suggestions = []
    mock_audit.report_markdown = "Cached markdown content. " * 20
    mock_audit.fix_plan = [{"issue": "cached"}]

    cached_context = {
        "keywords": [
            {"keyword": f"keyword {index}", "search_volume": 1000 + index}
            for index in range(100)
        ],
        "backlinks": {
            "top_backlinks": [],
            "total_backlinks": 0,
            "referring_domains": 0,
        },
        "rank_tracking": [],
        "llm_visibility": [],
        "ai_content_suggestions": [],
    }

    with patch.dict(
        os.environ,
        {"PDF_FORCE_FRESH_GEO": "false", "PDF_ALWAYS_FULL_MODE": "false"},
        clear=False,
    ), patch(
        "app.services.audit_service.AuditService.get_audit",
        return_value=mock_audit,
    ), patch(
        "app.services.audit_service.AuditService.get_audited_pages",
        return_value=[],
    ), patch(
        "app.services.audit_service.CompetitorService.get_competitors",
        return_value=[],
    ), patch(
        "app.services.pdf_service.PDFService._load_complete_audit_context",
        return_value=cached_context,
    ), patch(
        "app.services.pdf_service.PDFService._compute_report_context_signature",
        return_value="sig-123",
    ), patch(
        "app.services.pdf_service.PDFService._load_saved_report_signature",
        return_value="sig-123",
    ), patch(
        "app.services.keyword_service.KeywordService.research_keywords",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "app.services.backlink_service.BacklinkService.analyze_backlinks",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "app.services.rank_tracker_service.RankTrackerService.track_rankings",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "app.services.llm_visibility_service.LLMVisibilityService.check_visibility",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "app.services.ai_content_service.AIContentService.generate_suggestions",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "app.services.product_intelligence_service.ProductIntelligenceService.analyze",
        new_callable=AsyncMock,
        side_effect=Exception("skip product intelligence in test"),
    ), patch(
        "app.services.pipeline_service.PipelineService.generate_report",
        new_callable=AsyncMock,
        return_value=("Cached markdown content. " * 20, []),
    ), patch(
        "app.services.pdf_service.PDFService.generate_comprehensive_pdf",
        new_callable=AsyncMock,
        return_value="dummy.pdf",
    ) as mock_pdf_generator:
        result = await PDFService.generate_pdf_with_complete_context(
            mock_db, 88, return_details=True
        )

    assert result["pdf_path"] == "dummy.pdf"
    kwargs = mock_pdf_generator.await_args.kwargs
    assert len(kwargs["keywords_data"]["items"]) == PDFService.PDF_KEYWORDS_CONTEXT_LIMIT
    assert kwargs["keywords_data"]["total"] == 100
