import pytest

from app.services.pipeline_service import PipelineService


def _make_target_audit(url: str, title: str, meta: str, h1: str):
    return {
        "url": url,
        "content": {
            "title": title,
            "meta_description": meta,
            "nav_text": "",
            "text_sample": "",
        },
        "structure": {
            "h1_check": {"details": {"example": h1}},
        },
        "audited_page_paths": [],
    }


def test_extract_core_terms_from_target_bootcamp():
    target = _make_target_audit(
        "https://platform5.la/",
        "Plataforma 5 | Coding Bootcamp",
        "Coding bootcamp for software development in LATAM",
        "Coding Bootcamp",
    )
    core_terms = PipelineService._extract_core_terms_from_target(target)
    assert "bootcamp" in core_terms
    assert "coding" in core_terms
    assert "plataforma" not in core_terms


def test_fallback_queries_no_brand():
    target = _make_target_audit(
        "https://platform5.la/",
        "Plataforma 5 | Coding Bootcamp",
        "Coding bootcamp for software development in LATAM",
        "Coding Bootcamp",
    )
    queries = PipelineService._generate_fallback_queries(target)
    assert queries
    joined = " ".join(q["query"].lower() for q in queries)
    assert "plataforma" not in joined
    assert "bootcamp" in joined


def test_extract_core_terms_from_nav_text():
    target = _make_target_audit(
        "https://example.com/",
        "Example Store",
        "Compra online productos de salud",
        "Salud y Bienestar",
    )
    target["content"]["nav_text"] = "Salud y Farmacia Dermocosmética"
    core_terms = PipelineService._extract_core_terms_from_target(target)
    assert "farmacia" in core_terms


def test_filter_competitor_urls_core_terms():
    items = [
        {
            "link": "https://examplebootcamp.com/",
            "title": "Top Coding Bootcamp Argentina",
            "snippet": "Coding bootcamp programs in Argentina",
        },
        {
            "link": "https://randomnews.com/article",
            "title": "Digital transformation news",
            "snippet": "An unrelated story",
        },
    ]
    competitors = PipelineService.filter_competitor_urls(
        items, target_domain="platform5.la", core_terms=["coding", "bootcamp"], limit=5
    )
    assert "https://examplebootcamp.com/" in competitors
    assert all("randomnews" not in url for url in competitors)


def test_filter_competitor_urls_does_not_block_dealer_by_dea_substring():
    items = [
        {
            "link": "https://www.gibson.com/",
            "title": "Authorized Fender dealer guitars",
            "snippet": "Buy premium guitar gear online.",
        }
    ]
    competitors = PipelineService.filter_competitor_urls(
        items,
        target_domain="example.com",
        core_terms=["fender", "guitar"],
        anchor_terms=["fender", "guitar"],
        limit=5,
    )
    assert "https://www.gibson.com/" in competitors


def test_extract_competitor_urls_falls_back_to_anchor_terms_when_core_terms_are_noisy():
    target = _make_target_audit(
        "https://v0-guitar-store-one.vercel.app/",
        "Growth Hacking & SEO Analytics Platform | Boost Your Traffic",
        "SEO automation suite for growth teams",
        "Growth Analytics",
    )
    target["category"] = "E-commerce"
    target["subcategory"] = "Musical Instruments & Pro Audio niche High-end guitar boutique"
    target["market"] = "United States"

    search_results = {
        "buy fender gibson guitar online USA": {
            "items": [
                {
                    "link": "https://www.themusiczoo.com/",
                    "title": "Premium electric guitars and gear",
                    "snippet": "Authorized Fender and Gibson dealer. Buy guitar online.",
                },
                {
                    "link": "https://www.sweetwater.com/",
                    "title": "Guitar store",
                    "snippet": "Shop guitars with fast shipping in USA.",
                },
            ]
        }
    }
    external_intelligence = {
        "market": "United States",
        "queries_to_run": [
            {"id": "q1", "query": "buy fender gibson guitar online USA", "purpose": "Competitor discovery"},
            {
                "id": "q2",
                "query": "premium electric acoustic guitar shop United States",
                "purpose": "Competitor discovery",
            },
        ],
    }

    urls = PipelineService._extract_competitor_urls_from_search(
        search_results=search_results,
        target_domain="v0-guitar-store-one.vercel.app",
        target_audit=target,
        external_intelligence=external_intelligence,
        limit=3,
    )

    assert urls
    assert any("themusiczoo.com" in url for url in urls)


def test_sanitize_context_label_removes_nuestro_token():
    cleaned = PipelineService._sanitize_context_label(
        "Coding Bootcamp Nuestro", fallback="Unclassified"
    )
    assert cleaned == "Coding Bootcamp"


def test_normalize_market_value_ignores_nuestro():
    assert PipelineService._normalize_market_value("nuestro") is None
    assert PipelineService._normalize_market_value("latam") == "Latin America"


def test_fallback_queries_strip_possessive_noise_tokens():
    target = _make_target_audit(
        "https://example.com/",
        "Example | Coding Bootcamp",
        "Conoce nuestro coding bootcamp online con mentores senior",
        "Coding Bootcamp",
    )
    queries = PipelineService._generate_fallback_queries(target)
    assert queries
    joined = " ".join(q["query"].lower() for q in queries)
    assert "nuestro" not in joined


def test_extract_internal_urls_from_search_accepts_only_exact_host():
    items = [
        {"link": "https://example.com/"},
        {"link": "https://example.com/bootcamp/javascript"},
        {"link": "https://www.example.com/about"},
        {"link": "https://blog.example.com/post"},
        {"link": "https://evil-example.com/"},
        {"link": "ftp://example.com/file"},
    ]

    urls = PipelineService._extract_internal_urls_from_search(
        items, target_domain="example.com", limit=10
    )

    assert "https://example.com/" in urls
    assert "https://example.com/bootcamp/javascript" in urls
    assert "https://www.example.com/about" in urls
    assert all("blog.example.com" not in u for u in urls)
    assert all("evil-example.com" not in u for u in urls)
    assert all(not u.startswith("ftp://") for u in urls)


def test_sanitize_report_sources_normalizes_internal_placeholders():
    report = (
        "A [Source: score_definitions] "
        "B [Source: data_quality] "
        "C [Source: competitor_query_coverage] "
        "D [Source: /faqs]"
    )
    target = {"url": "https://example.com/"}

    sanitized = PipelineService._sanitize_report_sources(report, target)

    assert "[Source: Internal audit - score definitions]" in sanitized
    assert "[Source: Internal audit - data quality notes]" in sanitized
    assert "[Source: Internal audit - competitor query coverage]" in sanitized
    assert "[Source: https://example.com/faqs]" in sanitized


def test_extract_agent_payload_maps_alternate_llm_keys():
    raw_payload = {
        "classification": {
            "category": "Education Bootcamps",
            "subcategory": "Coding Bootcamp",
            "business_type": "EDTECH",
        },
        "strategic_queries": [
            {"query": "coding bootcamp argentina", "purpose": "competitors"},
            {"query": "best coding bootcamp", "purpose": "competitors"},
        ],
        "ymyl_status": "false",
        "market_country": "Argentina",
    }

    payload = PipelineService._extract_agent_payload(raw_payload)

    assert payload.get("category") == "Education Bootcamps"
    assert payload.get("subcategory") == "Coding Bootcamp"
    assert payload.get("business_type") == "EDTECH"
    assert isinstance(payload.get("queries_to_run"), list)
    assert payload.get("market") == "Argentina"
    assert payload.get("is_ymyl") is False


def test_prune_queries_keeps_competitor_markers_when_relevant():
    target = _make_target_audit(
        "https://plataforma5.la/",
        "Plataforma 5 | Coding Bootcamp",
        "Bootcamp de programación full stack",
        "Coding Bootcamp Full Stack",
    )
    queries = [
        {"id": "q1", "query": "best coding bootcamp", "purpose": "competitors"},
        {"id": "q2", "query": "coding bootcamp vs universidad", "purpose": "comparison"},
        {"id": "q3", "query": "bootcamp alternativas", "purpose": "comparison"},
    ]

    pruned = PipelineService._prune_competitor_queries(
        queries,
        target,
        llm_category="Coding Bootcamp",
        llm_subcategory="Full Stack",
        market_hint="Argentina",
    )

    joined = " | ".join(q.get("query", "").lower() for q in pruned)
    assert "best coding bootcamp" in joined
    assert "coding bootcamp vs universidad" in joined
    assert "alternativas" not in joined


def test_prune_queries_does_not_reject_generic_domain_token_as_brand():
    target = _make_target_audit(
        "https://robot.com/",
        "Robot.com | Autonomous Delivery Robots",
        "Autonomous delivery robotics solutions for logistics",
        "Autonomous Mobile Robots",
    )
    queries = [
        {
            "id": "q1",
            "query": "autonomous delivery robots United States logistics",
            "purpose": "competitor discovery",
        },
        {
            "id": "q2",
            "query": "warehouse AMR subscription United States",
            "purpose": "competitor discovery",
        },
    ]

    pruned = PipelineService._prune_competitor_queries(
        queries,
        target,
        llm_category="Robotics",
        llm_subcategory="Autonomous Mobile Robots",
        market_hint="United States",
    )

    assert pruned
    joined = " | ".join(q.get("query", "").lower() for q in pruned)
    assert "autonomous delivery robots" in joined


def test_normalize_category_fields_splits_primary_subcategory_blob():
    category, subcategory = PipelineService._normalize_category_fields(
        "primary Industrial Technology subcategory Autonomous Mobile Robots confidence 100",
        None,
    )

    assert category == "Industrial Technology"
    assert subcategory == "Autonomous Mobile Robots"


def test_prune_queries_keeps_ecommerce_shipping_and_market_intent():
    target = _make_target_audit(
        "https://www.farmalife.com.ar/",
        "Farmalife | Farmacia Online",
        "Farmacia online y dermocosmética en Argentina",
        "Farmacia Online",
    )
    queries = [
        {
            "id": "q1",
            "query": "farmacia online argentina envio gratis",
            "purpose": "competitor discovery",
        },
        {
            "id": "q2",
            "query": "dermocosmetica venta online Argentina",
            "purpose": "competitor discovery",
        },
    ]

    pruned = PipelineService._prune_competitor_queries(
        queries,
        target,
        llm_category="Healthcare",
        llm_subcategory="Pharmaceutical retail",
        market_hint="Argentina",
    )

    assert len(pruned) == 2


def test_prune_queries_accepts_category_plus_geo_when_market_hint_missing():
    target = _make_target_audit(
        "https://ceibo.digital/",
        "Ceibo | Digital Transformation",
        "Technology consulting and software development services",
        "Digital Transformation Services",
    )
    queries = [
        {
            "id": "q1",
            "query": "digital agency argentina",
            "purpose": "competitor discovery",
        },
        {
            "id": "q2",
            "query": "azure web app saas argentina",
            "purpose": "competitor discovery",
        },
    ]

    pruned = PipelineService._prune_competitor_queries(
        queries,
        target,
        llm_category="Technology",
        llm_subcategory="Digital agencies and software",
        market_hint=None,
    )

    assert pruned
    assert len(pruned) >= 1


def test_extract_core_terms_prefers_category_when_page_content_is_error_like():
    target = _make_target_audit(
        "https://ceibo.digital/",
        "App unavailable",
        "Service unavailable error",
        "Error",
    )
    target["category"] = "Technology"
    target["subcategory"] = "Digital Agency"

    terms = PipelineService._extract_core_terms_from_target(target, max_terms=3)
    joined = " ".join(terms)

    assert "technology" in joined or "digital" in joined
    assert "error" not in joined
    assert "unavailable" not in joined
    assert "app" not in joined
    assert "stopped" not in joined


def test_primary_query_guitar_ecommerce_es_market():
    target = _make_target_audit(
        "https://guitarras.example.com/",
        "Tienda de instrumentos",
        "Compra guitarras online",
        "Guitarra eléctrica y acústica",
    )
    target["language"] = "es"
    target["market"] = "Argentina"
    target["category"] = "E-commerce"
    target["subcategory"] = "Instrumentos musicales"
    target["content"]["nav_items"] = ["Guitarras", "Acústicas", "Eléctricas"]
    target["content"]["text_sample"] = "Tienda de guitarra profesional con stock disponible."

    profile = PipelineService._build_core_business_profile(target, max_terms=6)
    query = PipelineService._build_primary_business_query(
        profile, target["market"], target["language"]
    )

    assert query == "tienda de guitarras online Argentina"


def test_no_metadata_outlier_as_primary_query():
    target = _make_target_audit(
        "https://v0-guitar-store-one.vercel.app/",
        "Growth Hacking & SEO Analytics Platform | Boost Your Traffic",
        "SEO automation suite for growth teams",
        "FIND YOUR SOUND",
    )
    target["language"] = "en"
    target["market"] = "United States"
    target["category"] = "E-commerce"
    target["subcategory"] = "Musical Instruments"
    target["content"]["nav_items"] = ["Shop", "Electrics", "Acoustics"]
    target["content"]["text_sample"] = (
        "Handcrafted guitars for modern musicians. Fender and Gibson collection."
    )

    profile = PipelineService._build_core_business_profile(target, max_terms=6)
    query = PipelineService._build_primary_business_query(
        profile, target["market"], target["language"]
    )

    assert query
    assert "guitar" in query.lower()
    assert "seo" not in query.lower()
    assert "growth" not in query.lower()


def test_reject_outlier_queries_keep_core_queries():
    target = _make_target_audit(
        "https://example.com/",
        "Example",
        "Example",
        "Tienda de guitarras",
    )
    core_profile = {
        "core_terms": ["guitarras", "instrumentos"],
        "outlier_terms": ["seo", "growth", "analytics"],
    }
    queries = [
        {"id": "q1", "query": "seo growth analytics argentina", "purpose": "competitor discovery"},
        {"id": "q2", "query": "tienda de guitarras online argentina", "purpose": "competitor discovery"},
    ]

    pruned = PipelineService._prune_competitor_queries(
        queries,
        target,
        llm_category="E-commerce",
        llm_subcategory="Musical Instruments",
        market_hint="Argentina",
        core_profile=core_profile,
    )

    assert len(pruned) == 1
    assert "guitarras" in pruned[0]["query"].lower()


@pytest.mark.asyncio
async def test_agent1_infers_category_when_llm_returns_unknown():
    service = PipelineService()
    target = _make_target_audit(
        "https://plataforma5.la/",
        "Plataforma 5 | Coding Bootcamp",
        "Bootcamp intensivo de programación full stack",
        "Coding Bootcamp Full Stack",
    )

    async def fake_llm(*, system_prompt: str, user_prompt: str) -> str:
        return """
        {
          "category": "Unknown Category",
          "queries_to_run": [
            {"query": "coding bootcamp", "purpose": "competitor discovery"}
          ],
          "business_type": "EDTECH"
        }
        """

    external_intel, queries = await service.analyze_external_intelligence(
        target,
        llm_function=fake_llm,
        mode="fast",
        retry_policy={"max_retries": 0, "timeout_seconds": 10},
    )

    assert external_intel.get("category")
    assert external_intel.get("category") != "Unknown Category"
    assert external_intel.get("category_source") in {"onsite_inference", "agent1"}
    assert isinstance(external_intel.get("queries_to_run"), list)
    assert len(external_intel.get("queries_to_run")) >= 1
    assert external_intel.get("query_source") in {"agent1", "agent1_retry", "agent1_recovered"}
    assert external_intel.get("primary_query")
    assert queries[0]["query"] == external_intel.get("primary_query")
    assert len(queries) >= 1


@pytest.mark.asyncio
async def test_primary_query_is_first_and_mandatory():
    service = PipelineService()
    target = _make_target_audit(
        "https://guitarras.example.com/",
        "SEO Growth Platform",
        "SEO tools and analytics",
        "Tienda de guitarras",
    )
    target["language"] = "es"
    target["market"] = "Argentina"
    target["category"] = "E-commerce"
    target["subcategory"] = "Instrumentos musicales"
    target["content"]["nav_items"] = ["Guitarras", "Ofertas"]
    target["content"]["text_sample"] = "Guitarra acústica con envío y stock disponible."

    async def fake_llm(*, system_prompt: str, user_prompt: str) -> str:
        return """
        {
          "category": "E-commerce",
          "queries_to_run": [
            {"query": "seo growth platform argentina", "purpose": "competitor discovery"},
            {"query": "analytics tools argentina", "purpose": "competitor discovery"}
          ],
          "business_type": "RETAIL"
        }
        """

    external_intel, queries = await service.analyze_external_intelligence(
        target,
        llm_function=fake_llm,
        mode="full",
        retry_policy={"max_retries": 0, "timeout_seconds": 10},
    )

    assert external_intel.get("primary_query")
    assert queries
    assert queries[0]["query"] == external_intel.get("primary_query")
    assert "guitarra" in queries[0]["query"].lower()


@pytest.mark.asyncio
async def test_fail_closed_when_no_evidence_for_primary_query():
    service = PipelineService()
    target = {
        "url": "https://example.com/",
        "content": {"title": "", "meta_description": "", "text_sample": "", "nav_items": []},
        "structure": {"h1_check": {"details": {"example": ""}}},
        "audited_page_paths": [],
        "language": "en",
    }

    async def fake_llm(*, system_prompt: str, user_prompt: str) -> str:
        return "{}"

    with pytest.raises(RuntimeError, match="AGENT1_CORE_QUERY_EMPTY"):
        await service.analyze_external_intelligence(
            target,
            llm_function=fake_llm,
            mode="full",
            retry_policy={"max_retries": 0, "timeout_seconds": 5},
        )


@pytest.mark.asyncio
async def test_agent1_error_raises_without_fallbacks():
    service = PipelineService()
    target = _make_target_audit(
        "https://plataforma5.la/",
        "Plataforma 5 | Coding Bootcamp",
        "Bootcamp intensivo de programación full stack",
        "Coding Bootcamp Full Stack",
    )

    async def failing_llm(*, system_prompt: str, user_prompt: str) -> str:
        raise TimeoutError("llm timeout")

    with pytest.raises(RuntimeError):
        await service.analyze_external_intelligence(
            target,
            llm_function=failing_llm,
            mode="fast",
            retry_policy={"max_retries": 0, "timeout_seconds": 1},
        )
