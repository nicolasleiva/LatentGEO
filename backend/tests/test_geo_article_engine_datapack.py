import asyncio
import json

import pytest
from app.core.config import settings
from app.models import AIContentSuggestion, Audit, AuditStatus, Keyword
from app.services.geo_article_engine_service import (
    ArticleDataPackIncompleteError,
    GeoArticleEngineService,
)


def _seed_audit(db_session, *, minimal_paths: bool = False) -> Audit:
    paths = ["/"] if minimal_paths else ["/", "/products/nike-air", "/faq"]
    audit = Audit(
        url="https://store.example.com",
        domain="store.example.com",
        status=AuditStatus.COMPLETED,
        user_id="test-user",
        user_email="test@example.com",
        market="AR",
        target_audit={
            "audited_page_paths": paths,
            "site_metrics": {
                "schema_coverage_percent": 22.0,
                "structure_score_percent": 47.0,
                "h1_coverage_percent": 55.0,
                "faq_page_count": 0,
                "product_page_count": 4,
                "avg_semantic_score_percent": 31.0,
                "pages_analyzed": len(paths),
            },
            "content": {
                "title": "Store Example Running Shoes",
                "meta_description": "Buy running shoes in AR",
                "conversational_tone": {"score": 1.0},
            },
            "eeat": {
                "author_presence": {"status": "warn"},
            },
            "structure": {
                "h1_check": {"status": "warn"},
            },
        },
        search_results={
            "zapatilla nike": {
                "items": [
                    {
                        "title": "Statista Footwear",
                        "link": "https://www.statista.com/topics/123/footwear/",
                        "snippet": "Footwear market report",
                    },
                    {
                        "title": "Runner's World buying guide",
                        "link": "https://www.runnersworld.com/gear/a20865766/best-running-shoes/",
                        "snippet": "Trusted expert guide",
                    },
                    {
                        "title": "Nike official product page",
                        "link": "https://www.nike.com/running",
                        "snippet": "Official product details",
                    },
                ]
            }
        },
        competitor_audits=[
            {
                "url": "https://www.mercadolibre.com.ar/",
                "domain": "mercadolibre.com.ar",
                "geo_score": 66.0,
            }
        ],
    )
    db_session.add(audit)
    db_session.flush()
    db_session.add(
        Keyword(
            audit_id=audit.id,
            term="zapatilla nike",
            volume=15000,
            difficulty=70,
            intent="commercial",
        )
    )
    db_session.add(
        AIContentSuggestion(
            audit_id=audit.id,
            topic="AI Strategy Suggested Title",
            suggestion_type="guide",
            priority="high",
            content_outline={
                "target_keyword": "zapatilla nike",
                "sections": ["Section one", "Section two"],
                "business_context": "Sports retail",
            },
        )
    )
    db_session.commit()
    db_session.refresh(audit)
    return audit


def test_create_batch_fails_when_article_data_pack_prerequisites_missing(
    db_session, monkeypatch
):
    audit = _seed_audit(db_session, minimal_paths=True)
    monkeypatch.setattr(
        "app.services.geo_article_engine_service.is_kimi_configured", lambda: True
    )

    with pytest.raises(ArticleDataPackIncompleteError) as exc:
        GeoArticleEngineService.create_batch(
            db=db_session,
            audit=audit,
            article_count=1,
            language="es",
            tone="growth",
            include_schema=True,
        )
    assert "ARTICLE_DATA_PACK_INCOMPLETE" in str(exc.value)


def test_process_batch_rejects_when_authority_sources_insufficient(
    db_session, monkeypatch
):
    audit = _seed_audit(db_session)
    audit.search_results = {}
    db_session.commit()
    monkeypatch.setattr(
        "app.services.geo_article_engine_service.is_kimi_configured", lambda: True
    )
    monkeypatch.setattr(settings, "GEO_ARTICLE_AUDIT_ONLY", False, raising=False)

    batch = GeoArticleEngineService.create_batch(
        db=db_session,
        audit=audit,
        article_count=1,
        language="es",
        tone="growth",
        include_schema=True,
    )

    async def fake_search(**kwargs):
        return {
            "provider": "kimi-2.5-search",
            "results": [
                {
                    "position": 1,
                    "title": "Store result",
                    "url": "https://store.example.com/products/nike-air",
                    "domain": "store.example.com",
                    "snippet": "Internal result only",
                },
                {
                    "position": 2,
                    "title": "Single external",
                    "url": "https://example.org/nike",
                    "domain": "example.org",
                    "snippet": "Only one external source",
                },
            ],
            "evidence": [
                {"title": "Single external", "url": "https://example.org/nike"}
            ],
        }

    async def fake_llm(*, system_prompt, user_prompt):
        if "secondary keywords" in user_prompt:
            return json.dumps(
                {
                    "secondary_keywords": ["nike running", "nike ar sales"],
                    "search_intent": "commercial",
                }
            )
        return json.dumps(
            {
                "title": "Generated title",
                "markdown": "# Draft",
                "meta_title": "Meta",
                "meta_description": "Description",
            }
        )

    monkeypatch.setattr(
        "app.services.geo_article_engine_service.kimi_search_serp", fake_search
    )
    monkeypatch.setattr(
        "app.services.geo_article_engine_service.get_llm_function", lambda: fake_llm
    )

    processed = asyncio.run(GeoArticleEngineService.process_batch(db_session, batch.id))
    assert processed.status == "failed"
    assert processed.articles[0]["generation_status"] == "failed"
    assert (
        processed.articles[0]["generation_error"]["code"]
        == "INSUFFICIENT_AUTHORITY_SOURCES"
    )


def test_process_batch_builds_hybrid_keyword_strategy_and_uses_gap_prompt(
    db_session, monkeypatch
):
    audit = _seed_audit(db_session)
    monkeypatch.setattr(
        "app.services.geo_article_engine_service.is_kimi_configured", lambda: True
    )
    monkeypatch.setattr(settings, "GEO_ARTICLE_AUDIT_ONLY", False, raising=False)

    batch = GeoArticleEngineService.create_batch(
        db=db_session,
        audit=audit,
        article_count=1,
        language="es",
        tone="growth",
        include_schema=True,
    )

    async def fake_search(**kwargs):
        return {
            "provider": "kimi-2.5-search",
            "results": [
                {
                    "position": 1,
                    "title": "Mercado Libre zapatillas nike guide",
                    "url": "https://www.mercadolibre.com.ar/zapatillas-nike",
                    "domain": "mercadolibre.com.ar",
                    "snippet": "Nike running shoes guide for Argentina buyers",
                },
                {
                    "position": 2,
                    "title": "Nike official running shoes",
                    "url": "https://www.nike.com/ar/",
                    "domain": "nike.com",
                    "snippet": "Official running shoes catalog",
                },
                {
                    "position": 3,
                    "title": "Runner's World Nike running shoes guide",
                    "url": "https://www.runnersworld.com/gear/a20865766/best-running-shoes/",
                    "domain": "runnersworld.com",
                    "snippet": "Nike running shoes buying guide",
                },
                {
                    "position": 4,
                    "title": "Statista Nike running shoes report",
                    "url": "https://www.statista.com/topics/123/footwear/",
                    "domain": "statista.com",
                    "snippet": "Report on Nike running shoes market",
                },
                {
                    "position": 5,
                    "title": "Nike running shoes FAQ guide",
                    "url": "https://gearhub.com/blog/nike-running-faq",
                    "domain": "gearhub.com",
                    "snippet": "FAQ guide for Nike running shoes in Argentina",
                },
            ],
            "evidence": [
                {
                    "title": "Mercado Libre",
                    "url": "https://www.mercadolibre.com.ar/zapatillas-nike",
                },
                {"title": "Nike", "url": "https://www.nike.com/ar/"},
                {
                    "title": "Runner's World",
                    "url": "https://www.runnersworld.com/gear/a20865766/best-running-shoes/",
                },
            ],
        }

    prompts = []

    async def fake_llm(*, system_prompt, user_prompt):
        prompts.append(user_prompt)
        if "secondary keywords" in user_prompt:
            return json.dumps(
                {
                    "secondary_keywords": [
                        "comprar zapatilla nike",
                        "zapatilla nike ofertas ar",
                        "mejores zapatillas nike running",
                    ],
                    "search_intent": "commercial",
                }
            )
        return json.dumps(
            {
                "title": "",
                "markdown": (
                    "# Draft body\n\n"
                    "[Source: https://store.example.com/]\n\n"
                    "## FAQ\n"
                    "Q: Que revisar en zapatillas nike para running?\n"
                    "A: Prioriza amortiguacion y ajuste basado en guias expertas. "
                    "[Source: https://www.runnersworld.com/gear/a20865766/best-running-shoes/]\n"
                    "Q: Como comparar precios de zapatillas nike en AR?\n"
                    "A: Usa benchmarks de mercado y reportes comparativos. "
                    "[Source: https://www.statista.com/topics/123/footwear/]\n"
                    "Q: Que dudas frecuentes tienen los compradores?\n"
                    "A: Respuestas resumidas en guias FAQ del sector. "
                    "[Source: https://gearhub.com/blog/nike-running-faq]\n"
                ),
                "meta_title": "Draft meta title",
                "meta_description": "Draft meta description",
                "evidence_summary": [
                    {
                        "claim": "Market benchmarks highlight Nike running demand",
                        "source_url": "https://www.statista.com/topics/123/footwear/",
                    }
                ],
            }
        )

    monkeypatch.setattr(
        "app.services.geo_article_engine_service.kimi_search_serp", fake_search
    )
    monkeypatch.setattr(
        "app.services.geo_article_engine_service.get_llm_function", lambda: fake_llm
    )

    processed = asyncio.run(GeoArticleEngineService.process_batch(db_session, batch.id))
    assert processed.status == "completed"
    assert processed.summary["generated_count"] == 1

    article = processed.articles[0]
    assert article["generation_status"] == "completed"
    assert article["title"] == "AI Strategy Suggested Title"
    assert (
        article["keyword_strategy"]["strategy_mode"]
        == "audit_plus_kimi_search_expansion"
    )
    assert len(article["keyword_strategy"]["secondary_keywords"]) >= 2
    assert "schema" in article["competitor_gap_map"]
    assert article["evidence_summary"]
    assert "How to beat top competitor for this keyword" in article["markdown"]

    generation_prompts = [
        prompt
        for prompt in prompts
        if "Generate a complete GEO/SEO article ready to publish." in prompt
    ]
    assert generation_prompts, "Expected generation prompt to be captured"
    assert "competitor_gap_map" in generation_prompts[0]
    assert "article_data_pack" in generation_prompts[0]


def test_process_batch_repairs_invalid_citations_when_enabled(db_session, monkeypatch):
    audit = _seed_audit(db_session)
    monkeypatch.setattr(
        "app.services.geo_article_engine_service.is_kimi_configured", lambda: True
    )
    monkeypatch.setattr(settings, "GEO_ARTICLE_AUDIT_ONLY", False, raising=False)
    monkeypatch.setattr(
        settings, "GEO_ARTICLE_REPAIR_INVALID_CITATIONS", True, raising=False
    )

    batch = GeoArticleEngineService.create_batch(
        db=db_session,
        audit=audit,
        article_count=1,
        language="es",
        tone="growth",
        include_schema=True,
    )

    async def fake_search(**kwargs):
        return {
            "provider": "kimi-2.5-search",
            "results": [
                {
                    "position": 1,
                    "title": "Mercado Libre zapatillas nike guide",
                    "url": "https://www.mercadolibre.com.ar/zapatillas-nike",
                    "domain": "mercadolibre.com.ar",
                    "snippet": "Nike running shoes guide for Argentina buyers",
                },
                {
                    "position": 2,
                    "title": "Runner's World Nike running shoes guide",
                    "url": "https://www.runnersworld.com/gear/a20865766/best-running-shoes/",
                    "domain": "runnersworld.com",
                    "snippet": "Nike running shoes buying guide",
                },
                {
                    "position": 3,
                    "title": "Statista Nike running shoes report",
                    "url": "https://www.statista.com/topics/123/footwear/",
                    "domain": "statista.com",
                    "snippet": "Report on Nike running shoes market",
                },
            ],
            "evidence": [
                {
                    "title": "Mercado Libre",
                    "url": "https://www.mercadolibre.com.ar/zapatillas-nike",
                },
                {
                    "title": "Runner's World",
                    "url": "https://www.runnersworld.com/gear/a20865766/best-running-shoes/",
                },
                {
                    "title": "Statista",
                    "url": "https://www.statista.com/topics/123/footwear/",
                },
            ],
        }

    async def fake_llm(*, system_prompt, user_prompt):
        if "secondary keywords" in user_prompt:
            return json.dumps(
                {
                    "secondary_keywords": [
                        "comprar zapatilla nike",
                        "zapatilla nike ofertas ar",
                        "mejores zapatillas nike running",
                    ],
                    "search_intent": "commercial",
                }
            )
        if "Repair invalid citations" in user_prompt:
            return (
                "# Draft body\n\n"
                "[Source: https://store.example.com/]\n\n"
                "## FAQ\n"
                "Q: Que revisar en zapatillas nike para running?\n"
                "A: Prioriza amortiguacion y ajuste basado en guias expertas. "
                "[Source: https://www.runnersworld.com/gear/a20865766/best-running-shoes/]\n"
                "Q: Como comparar precios de zapatillas nike en AR?\n"
                "A: Usa benchmarks de mercado y reportes comparativos. "
                "[Source: https://www.statista.com/topics/123/footwear/]\n"
            )
        return json.dumps(
            {
                "title": "",
                "markdown": "# Draft body\n\n[Source: https://invalid.example.com/foo]\n\n## FAQ\nAnswer block",
                "meta_title": "Draft meta title",
                "meta_description": "Draft meta description",
            }
        )

    monkeypatch.setattr(
        "app.services.geo_article_engine_service.kimi_search_serp", fake_search
    )
    monkeypatch.setattr(
        "app.services.geo_article_engine_service.get_llm_function", lambda: fake_llm
    )

    processed = asyncio.run(GeoArticleEngineService.process_batch(db_session, batch.id))
    assert processed.status == "completed"
    article = processed.articles[0]
    assert article["generation_status"] == "completed"
    assert "invalid.example.com" not in article["markdown"]


def test_process_batch_fails_when_repair_disabled(db_session, monkeypatch):
    audit = _seed_audit(db_session)
    monkeypatch.setattr(
        "app.services.geo_article_engine_service.is_kimi_configured", lambda: True
    )
    monkeypatch.setattr(settings, "GEO_ARTICLE_AUDIT_ONLY", False, raising=False)
    monkeypatch.setattr(
        settings, "GEO_ARTICLE_REPAIR_INVALID_CITATIONS", False, raising=False
    )

    batch = GeoArticleEngineService.create_batch(
        db=db_session,
        audit=audit,
        article_count=1,
        language="es",
        tone="growth",
        include_schema=True,
    )

    async def fake_search(**kwargs):
        return {
            "provider": "kimi-2.5-search",
            "results": [
                {
                    "position": 1,
                    "title": "Mercado Libre zapatillas nike guide",
                    "url": "https://www.mercadolibre.com.ar/zapatillas-nike",
                    "domain": "mercadolibre.com.ar",
                    "snippet": "Nike running shoes guide for Argentina buyers",
                },
                {
                    "position": 2,
                    "title": "Runner's World Nike running shoes guide",
                    "url": "https://www.runnersworld.com/gear/a20865766/best-running-shoes/",
                    "domain": "runnersworld.com",
                    "snippet": "Nike running shoes buying guide",
                },
                {
                    "position": 3,
                    "title": "Statista Nike running shoes report",
                    "url": "https://www.statista.com/topics/123/footwear/",
                    "domain": "statista.com",
                    "snippet": "Report on Nike running shoes market",
                },
            ],
            "evidence": [
                {
                    "title": "Mercado Libre",
                    "url": "https://www.mercadolibre.com.ar/zapatillas-nike",
                },
                {
                    "title": "Runner's World",
                    "url": "https://www.runnersworld.com/gear/a20865766/best-running-shoes/",
                },
                {
                    "title": "Statista",
                    "url": "https://www.statista.com/topics/123/footwear/",
                },
            ],
        }

    async def fake_llm(*, system_prompt, user_prompt):
        if "secondary keywords" in user_prompt:
            return json.dumps(
                {
                    "secondary_keywords": [
                        "comprar zapatilla nike",
                        "zapatilla nike ofertas ar",
                        "mejores zapatillas nike running",
                    ],
                    "search_intent": "commercial",
                }
            )
        return json.dumps(
            {
                "title": "",
                "markdown": "# Draft body\n\n[Source: https://invalid.example.com/foo]\n\n## FAQ\nAnswer block",
                "meta_title": "Draft meta title",
                "meta_description": "Draft meta description",
            }
        )

    monkeypatch.setattr(
        "app.services.geo_article_engine_service.kimi_search_serp", fake_search
    )
    monkeypatch.setattr(
        "app.services.geo_article_engine_service.get_llm_function", lambda: fake_llm
    )

    processed = asyncio.run(GeoArticleEngineService.process_batch(db_session, batch.id))
    assert processed.status == "failed"
    assert processed.articles[0]["generation_status"] == "failed"
    assert processed.articles[0]["generation_error"]["code"] == "KIMI_GENERATION_FAILED"


def test_citation_url_normalization_allows_www_and_http(db_session, monkeypatch):
    audit = _seed_audit(db_session)
    monkeypatch.setattr(
        "app.services.geo_article_engine_service.is_kimi_configured", lambda: True
    )
    monkeypatch.setattr(settings, "GEO_ARTICLE_AUDIT_ONLY", False, raising=False)
    monkeypatch.setattr(
        settings, "GEO_ARTICLE_REPAIR_INVALID_CITATIONS", False, raising=False
    )

    batch = GeoArticleEngineService.create_batch(
        db=db_session,
        audit=audit,
        article_count=1,
        language="es",
        tone="growth",
        include_schema=True,
    )

    async def fake_search(**kwargs):
        return {
            "provider": "kimi-2.5-search",
            "results": [
                {
                    "position": 1,
                    "title": "Mercado Libre zapatillas nike guide",
                    "url": "https://www.mercadolibre.com.ar/zapatillas-nike",
                    "domain": "mercadolibre.com.ar",
                    "snippet": "Nike running shoes guide for Argentina buyers",
                },
                {
                    "position": 2,
                    "title": "Runner's World Nike running shoes guide",
                    "url": "https://www.runnersworld.com/gear/a20865766/best-running-shoes/",
                    "domain": "runnersworld.com",
                    "snippet": "Nike running shoes buying guide",
                },
                {
                    "position": 3,
                    "title": "Statista Nike running shoes report",
                    "url": "https://www.statista.com/topics/123/footwear/",
                    "domain": "statista.com",
                    "snippet": "Report on Nike running shoes market",
                },
            ],
            "evidence": [
                {
                    "title": "Mercado Libre",
                    "url": "https://www.mercadolibre.com.ar/zapatillas-nike",
                },
                {
                    "title": "Runner's World",
                    "url": "https://www.runnersworld.com/gear/a20865766/best-running-shoes/",
                },
                {
                    "title": "Statista",
                    "url": "https://www.statista.com/topics/123/footwear/",
                },
            ],
        }

    async def fake_llm(*, system_prompt, user_prompt):
        if "secondary keywords" in user_prompt:
            return json.dumps(
                {
                    "secondary_keywords": [
                        "comprar zapatilla nike",
                        "zapatilla nike ofertas ar",
                        "mejores zapatillas nike running",
                    ],
                    "search_intent": "commercial",
                }
            )
        return json.dumps(
            {
                "title": "",
                "markdown": (
                    "# Draft body\n\n"
                    "[Source: https://store.example.com/]\n\n"
                    "[Source: http://www.runnersworld.com/gear/a20865766/best-running-shoes/]\n\n"
                    "## FAQ\nAnswer block"
                ),
                "meta_title": "Draft meta title",
                "meta_description": "Draft meta description",
            }
        )

    monkeypatch.setattr(
        "app.services.geo_article_engine_service.kimi_search_serp", fake_search
    )
    monkeypatch.setattr(
        "app.services.geo_article_engine_service.get_llm_function", lambda: fake_llm
    )

    processed = asyncio.run(GeoArticleEngineService.process_batch(db_session, batch.id))
    assert processed.status == "completed"
    assert processed.articles[0]["generation_status"] == "completed"
