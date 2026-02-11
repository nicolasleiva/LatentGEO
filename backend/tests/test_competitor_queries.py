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
