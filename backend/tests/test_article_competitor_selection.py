import asyncio
import json

from app.core.config import settings
from app.models import AIContentSuggestion, Audit, AuditStatus, Keyword
from app.services.geo_article_engine_service import GeoArticleEngineService


def _seed_audit(
    db_session,
    *,
    competitors,
    search_results=None,
) -> Audit:
    audit = Audit(
        url="https://petshop.example.com",
        domain="petshop.example.com",
        status=AuditStatus.COMPLETED,
        user_id="test-user",
        user_email="test@example.com",
        market="AR",
        target_audit={
            "audited_page_paths": ["/", "/products/dog-food", "/faq"],
            "site_metrics": {
                "schema_coverage_percent": 20.0,
                "structure_score_percent": 45.0,
                "h1_coverage_percent": 40.0,
                "faq_page_count": 0,
                "product_page_count": 8,
                "avg_semantic_score_percent": 38.0,
                "pages_analyzed": 3,
            },
            "content": {
                "title": "Pet food store",
                "meta_description": "Buy dog and cat food online",
                "text_sample": "Pet food and nutrition guides for dogs and cats",
                "conversational_tone": {"score": 1.0},
            },
            "structure": {"h1_check": {"status": "warn"}},
            "eeat": {"author_presence": {"status": "warn"}},
        },
        external_intelligence={"category": "E-commerce", "subcategory": "Pet Supplies"},
        search_results=search_results or {},
        competitor_audits=competitors,
    )
    db_session.add(audit)
    db_session.flush()

    db_session.add(
        Keyword(
            audit_id=audit.id,
            term="pet food online",
            volume=1000,
            difficulty=45,
            intent="commercial",
        )
    )
    db_session.add(
        Keyword(
            audit_id=audit.id,
            term="dog food delivery",
            volume=900,
            difficulty=42,
            intent="commercial",
        )
    )
    db_session.add(
        AIContentSuggestion(
            audit_id=audit.id,
            topic="Pet Food Buying Guide",
            suggestion_type="guide",
            priority="high",
            content_outline={"target_keyword": "pet food online"},
        )
    )
    db_session.commit()
    db_session.refresh(audit)
    return audit


def test_extract_competitors_prefers_valid_audited_domains(db_session):
    audit = _seed_audit(
        db_session,
        competitors=[
            {"url": "https://instagram.com/petshopbrand", "domain": "instagram.com"},
            {"url": "https://www.royalcanin.com/ar", "domain": "royalcanin.com"},
        ],
    )
    competitors = GeoArticleEngineService._extract_competitors_from_audit(
        audit=audit,
        audit_domain="petshop.example.com",
        vertical_hint="ecommerce",
    )
    assert competitors
    assert competitors[0]["domain"] == "royalcanin.com"
    assert all("instagram.com" not in c["domain"] for c in competitors)


def test_process_batch_uses_audited_competitor_not_serp_social(db_session, monkeypatch):
    audit = _seed_audit(
        db_session,
        competitors=[
            {"url": "https://instagram.com/petshopbrand", "domain": "instagram.com"},
            {"url": "https://www.royalcanin.com/ar", "domain": "royalcanin.com"},
        ],
    )

    monkeypatch.setattr(
        "app.services.geo_article_engine_service.is_kimi_configured", lambda: True
    )
    monkeypatch.setattr(settings, "GEO_ARTICLE_AUDIT_ONLY", False, raising=False)
    monkeypatch.setattr(
        settings, "GEO_ARTICLE_REPAIR_INVALID_CITATIONS", True, raising=False
    )
    monkeypatch.setattr(settings, "GEO_ARTICLE_REQUIRE_QA", False, raising=False)

    batch = GeoArticleEngineService.create_batch(
        db=db_session,
        audit=audit,
        article_count=1,
        language="en",
        tone="growth",
        include_schema=True,
    )

    async def fake_search(**kwargs):
        return {
            "provider": "kimi-2.5-search",
            "results": [
                {
                    "position": 1,
                    "title": "Instagram pet food tips",
                    "url": "https://instagram.com/somepetprofile",
                    "domain": "instagram.com",
                    "snippet": "Pet food tips",
                },
                {
                    "position": 2,
                    "title": "PetMD pet food guide",
                    "url": "https://www.petmd.com/dog/nutrition/pet-food-guide",
                    "domain": "petmd.com",
                    "snippet": "Comprehensive pet food guide and nutrition analysis",
                },
                {
                    "position": 3,
                    "title": "AKC dog food guide",
                    "url": "https://www.akc.org/expert-advice/nutrition/dog-food-guide/",
                    "domain": "akc.org",
                    "snippet": "Dog food guide and nutrition best practices",
                },
                {
                    "position": 4,
                    "title": "RSPCA cat food guide",
                    "url": "https://www.rspca.org.uk/adviceandwelfare/pets/cats/diet",
                    "domain": "rspca.org.uk",
                    "snippet": "Cat food guide and diet recommendations",
                },
                {
                    "position": 5,
                    "title": "Chewy pet food guide",
                    "url": "https://www.chewy.com/education/dog-food-buying-guide",
                    "domain": "chewy.com",
                    "snippet": "Pet food buying guide and product comparisons",
                },
            ],
            "evidence": [
                {
                    "title": "PetMD",
                    "url": "https://www.petmd.com/dog/nutrition/pet-food-guide",
                },
                {
                    "title": "AKC",
                    "url": "https://www.akc.org/expert-advice/nutrition/dog-food-guide/",
                },
                {
                    "title": "RSPCA",
                    "url": "https://www.rspca.org.uk/adviceandwelfare/pets/cats/diet",
                },
                {
                    "title": "Chewy",
                    "url": "https://www.chewy.com/education/dog-food-buying-guide",
                },
            ],
        }

    async def fake_llm(*, system_prompt, user_prompt):
        if "secondary keywords" in user_prompt:
            return json.dumps(
                {
                    "secondary_keywords": ["dog food guide", "cat food nutrition"],
                    "search_intent": "commercial",
                }
            )
        return json.dumps(
            {
                "title": "Pet food online guide",
                "markdown": (
                    "# Pet food online guide\n\n"
                    "[Source: https://petshop.example.com/]\n"
                    "[Source: https://www.petmd.com/dog/nutrition/pet-food-guide]\n"
                ),
                "meta_title": "Pet food online guide",
                "meta_description": "Guide for pet food online buyers",
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
    assert article["competitor_to_beat"] == "royalcanin.com"


def test_process_batch_sets_competitor_to_none_when_no_valid_audited_competitor(
    db_session, monkeypatch
):
    audit = _seed_audit(
        db_session,
        competitors=[
            {"url": "https://instagram.com/petshopbrand", "domain": "instagram.com"},
            {"url": "https://facebook.com/petshopbrand", "domain": "facebook.com"},
        ],
    )

    monkeypatch.setattr(
        "app.services.geo_article_engine_service.is_kimi_configured", lambda: True
    )
    monkeypatch.setattr(settings, "GEO_ARTICLE_AUDIT_ONLY", True, raising=False)
    monkeypatch.setattr(settings, "GEO_ARTICLE_REQUIRE_QA", False, raising=False)

    batch = GeoArticleEngineService.create_batch(
        db=db_session,
        audit=audit,
        article_count=1,
        language="en",
        tone="growth",
        include_schema=True,
    )

    async def fake_llm(*, system_prompt, user_prompt):
        return json.dumps(
            {
                "title": "Pet food online guide",
                "markdown": "# Pet food online guide\n\n[Source: https://petshop.example.com/]\n",
                "meta_title": "Pet food online guide",
                "meta_description": "Guide for pet food online buyers",
            }
        )

    monkeypatch.setattr(
        "app.services.geo_article_engine_service.get_llm_function", lambda: fake_llm
    )

    processed = asyncio.run(GeoArticleEngineService.process_batch(db_session, batch.id))
    assert processed.status == "completed"
    article = processed.articles[0]
    assert article["generation_status"] == "completed"
    assert article["competitor_to_beat"] is None


def test_audits_competitors_route_filters_social_domains(client, db_session):
    audit = _seed_audit(
        db_session,
        competitors=[
            {
                "url": "https://instagram.com/petshopbrand",
                "domain": "instagram.com",
                "geo_score": 99,
            },
            {
                "url": "https://www.royalcanin.com/ar",
                "domain": "royalcanin.com",
                "geo_score": 20,
            },
        ],
    )

    response = client.get(f"/api/v1/audits/{audit.id}/competitors")
    assert response.status_code == 200
    payload = response.json()
    assert payload
    domains = [item.get("domain", "") for item in payload]
    assert all("instagram.com" not in d for d in domains)
    normalized_domains = {str(d).strip().lower() for d in domains}
    assert "royalcanin.com" in normalized_domains

