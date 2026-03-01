"""
GEO Features API Routes
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from app.core.access_control import ensure_audit_access
from app.core.auth import AuthUser, get_current_user
from app.core.database import get_db
from app.core.llm_kimi import (
    KimiGenerationError,
    KimiSearchError,
    KimiSearchUnavailableError,
    KimiUnavailableError,
    get_llm_function,
)
from app.core.logger import get_logger
from app.models import CitationTracking, DiscoveredQuery
from app.services.audit_service import AuditService
from app.services.citation_tracker_service import CitationTrackerService
from app.services.competitor_citation_service import CompetitorCitationService
from app.services.content_template_service import ContentTemplateService
from app.services.geo_article_engine_service import (
    ArticleDataPackIncompleteError,
    GeoArticleEngineService,
    InsufficientAuthoritySourcesError,
)
from app.services.geo_commerce_service import GeoCommerceService
from app.services.query_discovery_service import QueryDiscoveryService
from app.services.schema_optimizer_service import SchemaOptimizerService
from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

logger = get_logger(__name__)

router = APIRouter(
    prefix="/geo",
    tags=["GEO Features"],
    responses={404: {"description": "Not found"}},
)


def _get_owned_audit(db: Session, audit_id: int, current_user: AuthUser):
    audit = AuditService.get_audit(db, audit_id)
    return ensure_audit_access(audit, current_user)


def _extract_domain_brand(url: str) -> tuple[str, str]:
    domain = urlparse(url).netloc.replace("www.", "")
    brand_name = domain.split(".")[0].title() if domain else "Brand"
    return domain, brand_name


_ALLOWED_ERROR_CATEGORIES = {"internal_error", "invalid_input", "unauthorized"}
_ALLOWED_ERROR_CODES = {
    "workers_unavailable",
    "timeout",
    "dependency_error",
    "internal_error",
}

_SAFE_HTTP_ERROR_MESSAGES = {
    "KIMI_UNAVAILABLE": "Service temporarily unavailable.",
    "KIMI_GENERATION_FAILED": "Upstream generation dependency failed.",
    "ARTICLE_DATA_PACK_INCOMPLETE": "Required article data pack is incomplete.",
    "INSUFFICIENT_AUTHORITY_SOURCES": "Insufficient authority sources.",
    "INVALID_INPUT": "Invalid request payload.",
}


def _sanitize_geo_error_category(value: Any) -> str:
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in _ALLOWED_ERROR_CATEGORIES:
            return normalized
    return "internal_error"


def _sanitize_geo_error_code(value: Any) -> str:
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in _ALLOWED_ERROR_CODES:
            return normalized
    return "dependency_error"


def _sanitize_geo_gap_analysis(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {
            "has_data": False,
            "has_gaps": None,
            "error": "internal_error",
            "error_code": "dependency_error",
        }

    if "error" in value or "error_code" in value:
        return {
            "has_data": False,
            "has_gaps": None,
            "error": _sanitize_geo_error_category(value.get("error")),
            "error_code": _sanitize_geo_error_code(value.get("error_code")),
        }

    has_gaps = value.get("has_gaps")
    return {
        **value,
        "has_gaps": has_gaps if isinstance(has_gaps, bool) else False,
    }


def _sanitize_geo_benchmark_payload(payload: Any) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return {
            "has_data": False,
            "has_gaps": None,
            "error": "internal_error",
            "error_code": "internal_error",
        }

    if "error" in payload or "error_code" in payload:
        return {
            "has_data": False,
            "has_gaps": None,
            "error": _sanitize_geo_error_category(payload.get("error")),
            "error_code": _sanitize_geo_error_code(payload.get("error_code")),
        }

    sanitized = dict(payload)
    if "gap_analysis" in sanitized:
        sanitized["gap_analysis"] = _sanitize_geo_gap_analysis(sanitized["gap_analysis"])
    return sanitized


def _safe_http_error_detail(code: str) -> Dict[str, str]:
    normalized_code = str(code or "INTERNAL_ERROR").strip().upper()
    return {
        "code": normalized_code,
        "message": _SAFE_HTTP_ERROR_MESSAGES.get(
            normalized_code, "Internal server error."
        ),
    }


# ============= Pydantic Models =============


class CitationTrackingRequest(BaseModel):
    audit_id: int
    industry: Optional[str] = "general"
    keywords: List[str] = Field(default_factory=list)
    llm_name: str = "kimi"


class QueryDiscoveryRequest(BaseModel):
    brand_name: str
    domain: str
    industry: str
    keywords: List[str]


class QueryDiscoveryLegacyRequest(BaseModel):
    audit_id: int
    seed_query: str


class CompetitorAnalysisRequest(BaseModel):
    audit_id: int
    competitor_domains: List[str]
    queries: List[str]


class CompetitorAnalysisLegacyRequest(BaseModel):
    audit_id: int
    competitors: List[str] = Field(default_factory=list)


class SchemaGeneratorRequest(BaseModel):
    html_content: str = ""
    url: str
    page_type: Optional[str] = None


class SchemaGeneratorLegacyRequest(BaseModel):
    url: str
    schema_type: Optional[str] = None
    html_content: Optional[str] = ""


class ContentTemplateRequest(BaseModel):
    template_type: str  # guide, comparison, faq, listicle, tutorial
    topic: str
    keywords: List[str]


class CommerceCampaignRequest(BaseModel):
    audit_id: int
    competitor_domains: List[str] = Field(default_factory=list)
    market: Optional[str] = None
    channels: List[str] = Field(
        default_factory=lambda: ["chatgpt", "perplexity", "google-ai"]
    )
    objective: Optional[str] = None
    use_ai_playbook: bool = False


class CommerceQueryAnalyzeRequest(BaseModel):
    audit_id: int
    query: str = Field(
        ..., min_length=1, description="Single commerce query to analyze"
    )
    market: str = Field(
        ..., min_length=2, max_length=16, description="Market code (AR, US, MX, etc.)"
    )
    top_k: int = Field(default=10, ge=1, le=20)
    language: str = "es"


class ArticleEngineRequest(BaseModel):
    audit_id: int
    article_count: int = Field(default=3, ge=1, le=12)
    language: str = "en"
    tone: str = "executive"
    include_schema: bool = True
    market: Optional[str] = None
    run_async: bool = True


# ============= Citation Tracking Endpoints =============


@router.post("/citation-tracking/start")
async def start_citation_tracking(
    request: CitationTrackingRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """Inicia citation tracking para un audit."""
    try:
        # Obtener audit
        audit = _get_owned_audit(db, request.audit_id, current_user)

        # Obtener datos del audit
        domain, brand_name = _extract_domain_brand(audit.url)

        # Ejecutar en background
        async def run_tracking():
            get_llm_function()
            await CitationTrackerService.track_citations(
                db=db,
                audit_id=request.audit_id,
                brand_name=brand_name,
                domain=domain,
                industry=request.industry,
                keywords=request.keywords,
                llm_name=request.llm_name,
            )

        background_tasks.add_task(run_tracking)

        return {
            "message": "Citation tracking started",
            "audit_id": request.audit_id,
            "status": "processing",
        }

    except Exception as e:
        logger.error(f"Error starting citation tracking: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/citation-tracking/history/{audit_id}")
def get_citation_history(
    audit_id: int,
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """Obtiene historial de citaciones."""
    try:
        _get_owned_audit(db, audit_id, current_user)
        history = CitationTrackerService.get_citation_history(db, audit_id, days)
        return history
    except Exception as e:
        logger.error(f"Error getting citation history: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/citation-tracking/recent/{audit_id}")
def get_recent_citations(
    audit_id: int,
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """Obtiene citaciones recientes."""
    try:
        _get_owned_audit(db, audit_id, current_user)
        from sqlalchemy import desc

        citations = (
            db.query(CitationTracking)
            .filter(
                CitationTracking.audit_id == audit_id,
                CitationTracking.is_mentioned,
            )
            .order_by(desc(CitationTracking.tracked_at))
            .limit(limit)
            .all()
        )

        return [
            {
                "query": c.query,
                "citation_text": c.citation_text,
                "sentiment": c.sentiment,
                "llm_name": c.llm_name,
                "tracked_at": c.tracked_at.isoformat(),
            }
            for c in citations
        ]
    except Exception as e:
        logger.error(f"Error getting recent citations: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/citations/{audit_id}")
def get_recent_citations_legacy(
    audit_id: int,
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """Legacy citations endpoint used by current GEO UI."""
    try:
        _get_owned_audit(db, audit_id, current_user)
        from sqlalchemy import desc

        citations = (
            db.query(CitationTracking)
            .filter(
                CitationTracking.audit_id == audit_id,
                CitationTracking.is_mentioned,
            )
            .order_by(desc(CitationTracking.tracked_at))
            .limit(limit)
            .all()
        )
        return {
            "citations": [
                {
                    "id": c.id,
                    "query": c.query,
                    "response_preview": (c.citation_text or c.full_response or "")[
                        :220
                    ],
                    "llm_name": c.llm_name,
                    "citation_type": (
                        "direct" if c.position and c.position <= 2 else "indirect"
                    ),
                    "confidence": 0.85 if c.is_mentioned else 0.4,
                    "created_at": c.tracked_at.isoformat(),
                }
                for c in citations
            ]
        }
    except Exception as e:
        logger.error(f"Error getting legacy citations: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/citation-history/{audit_id}")
def get_citation_history_legacy(
    audit_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """Legacy monthly citation history endpoint used by current GEO UI."""
    try:
        _get_owned_audit(db, audit_id, current_user)
        from collections import defaultdict

        from sqlalchemy import desc

        rows = (
            db.query(CitationTracking)
            .filter(CitationTracking.audit_id == audit_id)
            .order_by(desc(CitationTracking.tracked_at))
            .all()
        )

        grouped: Dict[tuple[int, int], Dict[str, Any]] = defaultdict(
            lambda: {
                "mentions": 0,
                "total": 0,
                "queries": [],
            }
        )

        for row in rows:
            key = (row.tracked_at.year, row.tracked_at.month)
            grouped[key]["total"] += 1
            if row.is_mentioned:
                grouped[key]["mentions"] += 1
                if row.query and row.query not in grouped[key]["queries"]:
                    grouped[key]["queries"].append(row.query)

        history = []
        for (year, month), data in sorted(grouped.items(), reverse=True):
            history.append(
                {
                    "month": datetime(year, month, 1).strftime("%B"),
                    "year": year,
                    "citations": data["mentions"],
                    "queries_tracked": data["total"],
                    "citation_rate": round(
                        (data["mentions"] / max(1, data["total"])) * 100, 1
                    ),
                    "top_queries": data["queries"][:4],
                }
            )
        return {"history": history}
    except Exception as e:
        logger.error(f"Error getting legacy citation history: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ============= Query Discovery Endpoints =============


@router.post("/query-discovery/discover")
async def discover_queries(
    request: QueryDiscoveryRequest,
    db: Session = Depends(get_db),
    _current_user: AuthUser = Depends(get_current_user),
):
    """Descubre queries relevantes para el nicho."""
    try:
        backend_llm = get_llm_function()

        async def llm_adapter(prompt_text: str) -> str:
            return await backend_llm(
                system_prompt="You generate realistic search and assistant queries.",
                user_prompt=prompt_text,
            )

        queries = await QueryDiscoveryService.discover_queries(
            brand_name=request.brand_name,
            domain=request.domain,
            industry=request.industry,
            keywords=request.keywords,
            llm_function=llm_adapter,
        )

        return {"total_discovered": len(queries), "queries": queries[:20]}  # Top 20

    except Exception as e:
        logger.error(f"Error discovering queries: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/query-discovery")
async def discover_queries_legacy(
    request: QueryDiscoveryLegacyRequest,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """
    Legacy endpoint used by current GEO UI.
    Discovers query opportunities from a seed query and stores them for the audit.
    """
    try:
        audit = _get_owned_audit(db, request.audit_id, current_user)
        domain, brand_name = _extract_domain_brand(audit.url)
        seed = (request.seed_query or "").strip()
        if not seed:
            raise HTTPException(status_code=400, detail="seed_query is required")

        keywords = [seed]
        for row in getattr(audit, "keywords", None) or []:
            term = getattr(row, "term", None)
            if term and term not in keywords:
                keywords.append(term)
            if len(keywords) >= 8:
                break

        discovered = await QueryDiscoveryService.discover_queries(
            brand_name=brand_name,
            domain=domain,
            industry=(audit.category or "general"),
            keywords=keywords,
            llm_function=None,
        )
        QueryDiscoveryService.save_discovered_queries(
            db, request.audit_id, discovered[:20]
        )
        opportunities = QueryDiscoveryService.get_top_opportunities(
            db, request.audit_id, limit=10
        )

        mapped = []
        for row in opportunities:
            mapped.append(
                {
                    "query": row.get("query"),
                    "intent": row.get("intent", "informational"),
                    "potential_score": row.get("potential_score", 0),
                    "volume_estimate": "medium",
                    "competition_level": (
                        "high" if row.get("potential_score", 0) > 60 else "medium"
                    ),
                    "recommendation": "Create a citation-ready page with direct answers, proof blocks, and trusted external sources.",
                }
            )

        return {
            "total_opportunities": len(mapped),
            "opportunities": mapped,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error discovering legacy queries: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/query-discovery/opportunities/{audit_id}")
def get_query_opportunities(
    audit_id: int,
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """Obtiene las mejores oportunidades de queries."""
    try:
        _get_owned_audit(db, audit_id, current_user)
        opportunities = QueryDiscoveryService.get_top_opportunities(db, audit_id, limit)
        return {
            "total_opportunities": len(opportunities),
            "opportunities": opportunities,
        }
    except Exception as e:
        logger.error(f"Error getting opportunities: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ============= Competitor Citation Endpoints =============


@router.post("/competitor-analysis/analyze")
async def analyze_competitor_citations(
    request: CompetitorAnalysisRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """Analiza citaciones de competidores."""
    try:
        # Obtener audit
        audit = _get_owned_audit(db, request.audit_id, current_user)

        domain, brand_name = _extract_domain_brand(audit.url)

        # Ejecutar análisis
        async def run_analysis():
            llm_function = get_llm_function()
            await CompetitorCitationService.analyze_competitor_citations(
                db=db,
                audit_id=request.audit_id,
                brand_name=brand_name,
                domain=domain,
                competitor_domains=request.competitor_domains,
                queries=request.queries,
                llm_function=llm_function,
            )

        background_tasks.add_task(run_analysis)

        return {
            "message": "Competitor analysis started",
            "audit_id": request.audit_id,
            "competitors_count": len(request.competitor_domains),
        }

    except Exception as e:
        logger.error(f"Error analyzing competitors: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/competitor-analysis/benchmark/{audit_id}")
def get_citation_benchmark(
    audit_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """Obtiene benchmark de citaciones vs competidores."""
    try:
        _get_owned_audit(db, audit_id, current_user)
        benchmark = CompetitorCitationService.get_citation_benchmark(db, audit_id)
        return _sanitize_geo_benchmark_payload(benchmark)
    except Exception as e:
        logger.error(f"Error getting benchmark: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/competitor-analysis")
async def analyze_competitor_citations_legacy(
    request: CompetitorAnalysisLegacyRequest,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """Legacy endpoint that returns synchronous competitor analysis for current UI."""
    try:
        audit = _get_owned_audit(db, request.audit_id, current_user)
        domain, brand_name = _extract_domain_brand(audit.url)
        competitor_domains = [
            c.strip() for c in (request.competitors or []) if c and c.strip()
        ]
        if not competitor_domains:
            raise HTTPException(
                status_code=400, detail="At least one competitor is required"
            )

        # Build compact query set using discovered opportunities, then fallback to default.
        query_rows = (
            db.query(DiscoveredQuery)
            .filter(DiscoveredQuery.audit_id == request.audit_id)
            .order_by(DiscoveredQuery.potential_score.desc())
            .limit(5)
            .all()
        )
        queries = [q.query for q in query_rows if getattr(q, "query", None)]
        if not queries:
            queries = [
                f"best {audit.category or 'product'} alternatives",
                f"{brand_name} vs marketplace options",
                f"where to buy {audit.category or brand_name}",
            ]

        backend_llm = get_llm_function()

        async def quick_llm(user_prompt: str) -> str:
            return await backend_llm(
                system_prompt=(
                    "You are a competitive visibility analyst. "
                    "Respond with factual, concise text and avoid fabrication."
                ),
                user_prompt=user_prompt,
            )

        analysis = await CompetitorCitationService.analyze_competitor_citations(
            db=db,
            audit_id=request.audit_id,
            brand_name=brand_name,
            domain=domain,
            competitor_domains=competitor_domains,
            queries=queries,
            llm_function=quick_llm,
        )

        your_mentions = int(analysis.get("your_brand", {}).get("mentions", 0))
        total_queries = max(1, len(queries))
        your_rate = round((your_mentions / total_queries) * 100, 1)

        competitors_payload = []
        for row in analysis.get("competitors", []):
            mentions = int(row.get("mentions", 0))
            comp_rate = round((mentions / total_queries) * 100, 1)
            competitors_payload.append(
                {
                    "name": row.get("name") or row.get("domain"),
                    "citations": mentions,
                    "citation_rate": comp_rate,
                    "top_queries": row.get("queries_mentioned", [])[:4],
                    "strengths": [
                        "Higher appearance in AI answer sets",
                        "Broader query coverage",
                    ],
                    "weaknesses": [
                        "Generic answer quality in long-tail intents",
                        "Lower first-party authority for niche product specifics",
                    ],
                }
            )

        gaps = []
        if competitors_payload:
            top = max(competitors_payload, key=lambda x: x.get("citations", 0))
            if top.get("citations", 0) > your_mentions:
                gaps.append(
                    f"{top['name']} appears {top['citations'] - your_mentions} more times across sampled queries."
                )
        opportunities = [
            "Create citation-ready comparison pages by category and model.",
            "Add trusted external references to conversion-critical claims.",
            "Ship FAQ + schema bundles on top-intent pages first.",
        ]

        return {
            "your_citations": your_mentions,
            "your_citation_rate": your_rate,
            "competitors": competitors_payload,
            "gaps": gaps,
            "opportunities": opportunities,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in legacy competitor analysis: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ============= Schema Optimizer Endpoints =============


@router.post("/schema/generate")
async def generate_schema(
    request: SchemaGeneratorRequest,
    _current_user: AuthUser = Depends(get_current_user),
):
    """Genera Schema.org optimizado para la página."""
    try:
        backend_llm = get_llm_function()

        async def llm_adapter(prompt_text: str) -> str:
            return await backend_llm(
                system_prompt="You improve schema descriptions for machine readability.",
                user_prompt=prompt_text,
            )

        result = await SchemaOptimizerService.generate_schema(
            html_content=request.html_content,
            url=request.url,
            page_type=request.page_type,
            llm_function=llm_adapter,
        )

        return result

    except Exception as e:
        logger.error(f"Error generating schema: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/schema/multiple")
async def generate_multiple_schemas(
    request: SchemaGeneratorRequest,
    _current_user: AuthUser = Depends(get_current_user),
):
    """Genera múltiples schemas si la página lo amerita."""
    try:
        schemas = SchemaOptimizerService.generate_multiple_schemas(
            html_content=request.html_content, url=request.url
        )

        return {"total_schemas": len(schemas), "schemas": schemas}

    except Exception as e:
        logger.error(f"Error generating schemas: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/schema-generator")
async def generate_schema_legacy(
    request: SchemaGeneratorLegacyRequest,
    _current_user: AuthUser = Depends(get_current_user),
):
    """Legacy schema generator endpoint used by current frontend component."""
    try:
        backend_llm = get_llm_function()

        async def llm_adapter(prompt_text: str) -> str:
            return await backend_llm(
                system_prompt="You improve schema descriptions for machine readability.",
                user_prompt=prompt_text,
            )

        result = await SchemaOptimizerService.generate_schema(
            html_content=request.html_content or "",
            url=request.url,
            page_type=request.schema_type,
            llm_function=llm_adapter,
        )
        return {
            "schema_type": result.get("page_type", "Organization"),
            "schema_json": result.get("implementation_code", ""),
            "recommendations": [
                "Validate schema in Rich Results Test before publishing.",
                "Prioritize Product, FAQPage, and Organization entities for commerce journeys.",
            ],
        }
    except Exception as e:
        logger.error(f"Error generating legacy schema: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/schema-multiple")
async def generate_multiple_schemas_legacy(
    request: SchemaGeneratorLegacyRequest,
    _current_user: AuthUser = Depends(get_current_user),
):
    """Legacy multiple-schema endpoint used by current frontend component."""
    try:
        schemas = SchemaOptimizerService.generate_multiple_schemas(
            html_content=request.html_content or "",
            url=request.url,
        )
        return {
            "schemas": [
                {
                    "schema_type": row.get("type", "Organization"),
                    "reason": "Suggested based on detected page structure and intent.",
                    "priority": (
                        "high"
                        if row.get("type") in {"Product", "Article", "FAQPage"}
                        else "medium"
                    ),
                    "schema_json": json.dumps(
                        row.get("schema", {}), indent=2, ensure_ascii=False
                    ),
                }
                for row in schemas
            ]
        }
    except Exception as e:
        logger.error(f"Error generating legacy multiple schemas: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ============= Content Template Endpoints =============


@router.get("/content-templates/list")
def list_content_templates(
    _current_user: AuthUser = Depends(get_current_user),
):
    """Lista todos los templates disponibles."""
    try:
        templates = ContentTemplateService.get_all_templates()
        return {"total_templates": len(templates), "templates": templates}
    except Exception as e:
        logger.error(f"Error listing templates: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/content-templates")
def list_content_templates_legacy(
    category: str = "all",
    _current_user: AuthUser = Depends(get_current_user),
):
    """Legacy endpoint used by current GEO UI card."""
    try:
        category_map = {
            "guide": "blog",
            "comparison": "product",
            "faq": "faq",
            "listicle": "landing",
            "tutorial": "service",
        }
        templates = []
        for key, template in ContentTemplateService.TEMPLATES.items():
            mapped_category = category_map.get(key, "blog")
            if category != "all" and mapped_category != category:
                continue
            templates.append(
                {
                    "id": key,
                    "name": template.get("name", key.title()),
                    "description": template.get("description", ""),
                    "category": mapped_category,
                    "structure": "".join(template.get("structure", [])),
                    "tips": template.get("llm_optimization", []),
                }
            )
        return {
            "total": len(templates),
            "templates": templates,
        }
    except Exception as e:
        logger.error(f"Error listing legacy templates: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/content-templates/generate")
async def generate_content_template(
    request: ContentTemplateRequest,
    _current_user: AuthUser = Depends(get_current_user),
):
    """Genera un template de contenido personalizado."""
    try:
        backend_llm = get_llm_function()

        async def llm_adapter(prompt_text: str) -> str:
            return await backend_llm(
                system_prompt="You are a GEO content strategist.",
                user_prompt=prompt_text,
            )

        template = await ContentTemplateService.generate_template(
            template_type=request.template_type,
            topic=request.topic,
            keywords=request.keywords,
            llm_function=llm_adapter,
        )

        return template

    except ValueError:
        raise HTTPException(status_code=400, detail="Internal server error")
    except Exception as e:
        logger.error(f"Error generating template: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/content-templates/analyze")
def analyze_content(
    payload: Any = Body(...),
    _current_user: AuthUser = Depends(get_current_user),
):
    """Analiza contenido existente y sugiere mejoras para GEO."""
    try:
        content = ""
        if isinstance(payload, str):
            content = payload.strip()
        elif isinstance(payload, dict):
            content = str(payload.get("content", "")).strip()

        if not content:
            raise HTTPException(status_code=422, detail="content is required")

        analysis = ContentTemplateService.analyze_content_for_geo(content)
        return analysis
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing content: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/analyze-content")
def analyze_content_legacy(
    payload: Dict[str, Any] = Body(...),
    _current_user: AuthUser = Depends(get_current_user),
):
    """Legacy endpoint for freeform content GEO analysis card."""
    try:
        content = str(payload.get("content", "")).strip()
        if not content:
            raise HTTPException(status_code=400, detail="content is required")

        analysis = ContentTemplateService.analyze_content_for_geo(content)
        score = int(analysis.get("score", 0))
        if score >= 80:
            geo_readiness = "Strong citation readiness"
        elif score >= 60:
            geo_readiness = "Moderate readiness; prioritize structured upgrades"
        else:
            geo_readiness = "Low readiness; major GEO structure and evidence gaps"

        return {
            "score": score,
            "strengths": analysis.get("strengths", []),
            "weaknesses": analysis.get("improvements", []),
            "recommendations": analysis.get("improvements", []),
            "geo_readiness": geo_readiness,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in legacy content analyze: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ============= Commerce LLM Tool =============


@router.post("/commerce-query/analyze")
async def analyze_commerce_query(
    request: CommerceQueryAnalyzeRequest,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """
    Query-first commerce analyzer:
    - Uses Kimi 2.5 search only (no Google fallback).
    - Explains why audited domain is not #1 and how to beat top result.
    """
    try:
        audit = _get_owned_audit(db, request.audit_id, current_user)
        analysis = await GeoCommerceService.analyze_query(
            db=db,
            audit=audit,
            query=request.query.strip(),
            market=request.market.strip().upper(),
            top_k=request.top_k,
            language=request.language,
            llm_function=get_llm_function(),
        )
        payload = analysis.payload or {}
        return {
            "analysis_id": analysis.id,
            "query": payload.get("query", request.query.strip()),
            "market": payload.get("market", request.market.strip().upper()),
            "audited_domain": payload.get("audited_domain"),
            "target_position": payload.get("target_position"),
            "top_result": payload.get("top_result"),
            "results": payload.get("results", []),
            "why_not_first": payload.get("why_not_first", []),
            "disadvantages_vs_top1": payload.get("disadvantages_vs_top1", []),
            "action_plan": payload.get("action_plan", []),
            "evidence": payload.get("evidence", []),
            "provider": payload.get("provider", "kimi-2.5-search"),
            "generated_at": payload.get(
                "generated_at", analysis.created_at.isoformat()
            ),
        }
    except KimiSearchUnavailableError:
        raise HTTPException(
            status_code=503,
            detail=_safe_http_error_detail("KIMI_UNAVAILABLE"),
        )
    except KimiSearchError:
        raise HTTPException(
            status_code=502,
            detail=_safe_http_error_detail("KIMI_GENERATION_FAILED"),
        )
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=_safe_http_error_detail("INVALID_INPUT"),
        )
    except Exception as e:
        logger.error(f"Error analyzing commerce query: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/commerce-query/latest/{audit_id}")
def get_latest_commerce_query_analysis(
    audit_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """Fetch latest query-first ecommerce analysis for the audit."""
    try:
        _get_owned_audit(db, audit_id, current_user)
        analysis = GeoCommerceService.get_latest_query_analysis(db, audit_id)
        if not analysis:
            return {"has_data": False}
        payload = analysis.payload or {}
        return {
            "has_data": True,
            "analysis_id": analysis.id,
            "audit_id": analysis.audit_id,
            "created_at": analysis.created_at.isoformat(),
            "query": payload.get("query"),
            "market": payload.get("market"),
            "audited_domain": payload.get("audited_domain"),
            "target_position": payload.get("target_position"),
            "top_result": payload.get("top_result"),
            "results": payload.get("results", []),
            "why_not_first": payload.get("why_not_first", []),
            "disadvantages_vs_top1": payload.get("disadvantages_vs_top1", []),
            "action_plan": payload.get("action_plan", []),
            "evidence": payload.get("evidence", []),
            "provider": payload.get("provider", "kimi-2.5-search"),
            "payload": payload,
        }
    except Exception as e:
        logger.error(f"Error fetching latest commerce query analysis: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/commerce-campaign/generate")
async def generate_commerce_campaign(
    request: CommerceCampaignRequest,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """Generate an ecommerce campaign to increase AI citation share."""
    try:
        audit = _get_owned_audit(db, request.audit_id, current_user)
        llm_function = get_llm_function() if request.use_ai_playbook else None
        campaign = await GeoCommerceService.generate_campaign(
            db=db,
            audit=audit,
            competitor_domains=request.competitor_domains,
            market=request.market,
            channels=request.channels,
            objective=request.objective,
            llm_function=llm_function,
            use_ai_playbook=request.use_ai_playbook,
        )
        return {
            "campaign_id": campaign.id,
            "audit_id": campaign.audit_id,
            "created_at": campaign.created_at.isoformat(),
            "payload": campaign.payload,
        }
    except Exception as e:
        logger.error(f"Error generating commerce campaign: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/commerce-campaign/latest/{audit_id}")
def get_latest_commerce_campaign(
    audit_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """Fetch latest ecommerce campaign for the audit."""
    try:
        _get_owned_audit(db, audit_id, current_user)
        campaign = GeoCommerceService.get_latest_campaign(db, audit_id)
        if not campaign:
            return {"has_data": False}
        return {
            "has_data": True,
            "campaign_id": campaign.id,
            "audit_id": campaign.audit_id,
            "created_at": campaign.created_at.isoformat(),
            "payload": campaign.payload,
        }
    except Exception as e:
        logger.error(f"Error fetching latest commerce campaign: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ============= Article Engine Tool =============


@router.post("/article-engine/generate")
async def generate_article_batch(
    request: ArticleEngineRequest,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """Create and process article-engine batch with strict GEO/SEO data-pack rules."""
    try:
        audit = _get_owned_audit(db, request.audit_id, current_user)
        batch = GeoArticleEngineService.create_batch(
            db=db,
            audit=audit,
            article_count=request.article_count,
            language=request.language,
            tone=request.tone,
            include_schema=request.include_schema,
            market=request.market,
        )
        if request.run_async:
            from app.workers.tasks import generate_article_batch_task

            async_result = generate_article_batch_task.delay(batch.id)
            summary = dict(batch.summary or {})
            summary["task_id"] = async_result.id
            batch.summary = summary
            db.commit()
            db.refresh(batch)
            return GeoArticleEngineService.serialize_batch(batch)

        processed = await GeoArticleEngineService.process_batch(db, batch.id)
        # Surface strict contractual failures with explicit HTTP status.
        if processed.status == "failed":
            articles = processed.articles or []
            first_error = None
            for article in articles:
                if isinstance(article, dict) and isinstance(
                    article.get("generation_error"), dict
                ):
                    first_error = article["generation_error"]
                    break
            if first_error:
                code = str(first_error.get("code") or "").strip().upper()
                if code == "KIMI_UNAVAILABLE":
                    raise HTTPException(
                        status_code=503,
                        detail=_safe_http_error_detail(code),
                    )
                if code == "KIMI_GENERATION_FAILED":
                    raise HTTPException(
                        status_code=502,
                        detail=_safe_http_error_detail(code),
                    )
                if code in {
                    "ARTICLE_DATA_PACK_INCOMPLETE",
                    "INSUFFICIENT_AUTHORITY_SOURCES",
                }:
                    raise HTTPException(
                        status_code=422,
                        detail=_safe_http_error_detail(code),
                    )
        return GeoArticleEngineService.serialize_batch(processed)
    except KimiUnavailableError:
        raise HTTPException(
            status_code=503,
            detail=_safe_http_error_detail("KIMI_UNAVAILABLE"),
        )
    except KimiSearchUnavailableError:
        raise HTTPException(
            status_code=503,
            detail=_safe_http_error_detail("KIMI_UNAVAILABLE"),
        )
    except (ArticleDataPackIncompleteError, InsufficientAuthoritySourcesError) as exc:
        code = (
            "INSUFFICIENT_AUTHORITY_SOURCES"
            if isinstance(exc, InsufficientAuthoritySourcesError)
            else "ARTICLE_DATA_PACK_INCOMPLETE"
        )
        raise HTTPException(
            status_code=422,
            detail=_safe_http_error_detail(code),
        )
    except (KimiGenerationError, KimiSearchError):
        raise HTTPException(
            status_code=502,
            detail=_safe_http_error_detail("KIMI_GENERATION_FAILED"),
        )
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=_safe_http_error_detail("INVALID_INPUT"),
        )
    except Exception as e:
        logger.error(f"Error generating article batch: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/article-engine/status/{batch_id}")
def get_article_batch_status(
    batch_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """Fetch processing/completion status for an article batch."""
    try:
        batch = GeoArticleEngineService.get_batch(db, batch_id)
        if not batch:
            raise HTTPException(status_code=404, detail="Article batch not found")
        _get_owned_audit(db, batch.audit_id, current_user)
        return {
            "has_data": True,
            **GeoArticleEngineService.serialize_batch(batch),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching article batch status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/article-engine/latest/{audit_id}")
def get_latest_article_batch(
    audit_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """Fetch latest generated article batch for the audit."""
    try:
        _get_owned_audit(db, audit_id, current_user)
        batch = GeoArticleEngineService.get_latest_batch(db, audit_id)
        if not batch:
            return {"has_data": False}
        return {"has_data": True, **GeoArticleEngineService.serialize_batch(batch)}
    except Exception as e:
        logger.error(f"Error fetching latest article batch: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ============= Dashboard Summary Endpoint =============


@router.get("/dashboard/{audit_id}")
async def get_geo_dashboard(
    audit_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """Obtiene resumen completo de GEO para el dashboard."""
    try:
        _get_owned_audit(db, audit_id, current_user)
        citation_history: Dict[str, Any] = {}
        opportunities: List[Dict[str, Any]] = []
        benchmark: Dict[str, Any] = {}
        latest_campaign = None
        latest_query_analysis = None
        latest_batch = None

        try:
            citation_history = (
                CitationTrackerService.get_citation_history(db, audit_id, 30) or {}
            )
        except Exception as history_exc:
            logger.warning(
                f"Citation history failed for audit {audit_id}: {history_exc}"
            )

        try:
            opportunities = (
                QueryDiscoveryService.get_top_opportunities(db, audit_id, 5) or []
            )
        except Exception as opportunities_exc:
            logger.warning(
                f"Query opportunities failed for audit {audit_id}: {opportunities_exc}"
            )

        try:
            benchmark = (
                CompetitorCitationService.get_citation_benchmark(db, audit_id) or {}
            )
        except Exception as benchmark_exc:
            logger.warning(
                f"Competitor benchmark failed for audit {audit_id}: {benchmark_exc}"
            )
        benchmark = _sanitize_geo_benchmark_payload(benchmark)

        try:
            latest_campaign = GeoCommerceService.get_latest_campaign(db, audit_id)
        except Exception as campaign_exc:
            logger.warning(
                f"Legacy commerce campaign lookup failed for audit {audit_id}: {campaign_exc}"
            )

        try:
            latest_query_analysis = GeoCommerceService.get_latest_query_analysis(
                db, audit_id
            )
        except Exception as query_exc:
            logger.warning(
                f"Commerce query analysis lookup failed for audit {audit_id}: {query_exc}"
            )

        try:
            latest_batch = GeoArticleEngineService.get_latest_batch(db, audit_id)
        except Exception as batch_exc:
            logger.warning(
                f"Article engine lookup failed for audit {audit_id}: {batch_exc}"
            )

        benchmark_gap_payload = benchmark.get("gap_analysis")
        if benchmark_gap_payload is None and (
            "error" in benchmark or "error_code" in benchmark
        ):
            benchmark_gap_payload = benchmark

        return {
            "audit_id": audit_id,
            "citation_tracking": {
                "citation_rate": citation_history.get("citation_rate", 0),
                "total_queries": citation_history.get("total_queries", 0),
                "mentions": citation_history.get("mentions", 0),
                "sentiment_breakdown": citation_history.get("sentiment_breakdown", {}),
            },
            "top_opportunities": opportunities,
            "competitor_benchmark": {
                "has_data": benchmark.get("has_data", False),
                "your_mentions": benchmark.get("your_mentions", 0),
                "top_competitor": (
                    benchmark.get("competitors", [{}])[0].get("name")
                    if benchmark.get("competitors")
                    else None
                ),
                "gap_analysis": _sanitize_geo_gap_analysis(benchmark_gap_payload),
            },
            "commerce_campaign": {
                "has_data": latest_campaign is not None,
                "campaign_id": latest_campaign.id if latest_campaign else None,
            },
            "commerce_query_analyzer": {
                "has_data": latest_query_analysis is not None,
                "analysis_id": (
                    latest_query_analysis.id if latest_query_analysis else None
                ),
                "query": (
                    (latest_query_analysis.payload or {}).get("query")
                    if latest_query_analysis
                    else None
                ),
                "market": (
                    (latest_query_analysis.payload or {}).get("market")
                    if latest_query_analysis
                    else None
                ),
            },
            "article_engine": {
                "has_data": latest_batch is not None,
                "batch_id": latest_batch.id if latest_batch else None,
                "generated_count": (
                    (latest_batch.summary or {}).get("generated_count", 0)
                    if latest_batch
                    else 0
                ),
            },
        }

    except Exception as e:
        logger.error(f"Error getting GEO dashboard: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

