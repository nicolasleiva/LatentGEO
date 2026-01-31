"""
GEO Features API Routes
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from app.core.database import get_db
from app.services.citation_tracker_service import CitationTrackerService
from app.services.query_discovery_service import QueryDiscoveryService
from app.services.competitor_citation_service import CompetitorCitationService
from app.services.schema_optimizer_service import SchemaOptimizerService
from app.services.content_template_service import ContentTemplateService
from app.services.audit_service import AuditService
from app.core.llm_kimi import get_llm_function
from app.core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/geo",
    tags=["GEO Features"],
    responses={404: {"description": "Not found"}},
)


# ============= Pydantic Models =============

class CitationTrackingRequest(BaseModel):
    audit_id: int
    industry: Optional[str] = "general"
    keywords: Optional[List[str]] = []
    llm_name: str = "kimi"


class QueryDiscoveryRequest(BaseModel):
    brand_name: str
    domain: str
    industry: str
    keywords: List[str]


class CompetitorAnalysisRequest(BaseModel):
    audit_id: int
    competitor_domains: List[str]
    queries: List[str]


class SchemaGeneratorRequest(BaseModel):
    html_content: str
    url: str
    page_type: Optional[str] = None


class ContentTemplateRequest(BaseModel):
    template_type: str  # guide, comparison, faq, listicle, tutorial
    topic: str
    keywords: List[str]


# ============= Citation Tracking Endpoints =============

@router.post("/citation-tracking/start")
async def start_citation_tracking(
    request: CitationTrackingRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Inicia citation tracking para un audit."""
    try:
        # Obtener audit
        audit = AuditService.get_audit(db, request.audit_id)
        if not audit:
            raise HTTPException(status_code=404, detail="Audit not found")
        
        # Obtener datos del audit
        from urllib.parse import urlparse
        domain = urlparse(audit.url).netloc.replace('www.', '')
        brand_name = domain.split('.')[0].title()
        
        # Ejecutar en background
        async def run_tracking():
            llm_function = get_llm_function()
            await CitationTrackerService.track_citations(
                db=db,
                audit_id=request.audit_id,
                brand_name=brand_name,
                domain=domain,
                industry=request.industry,
                keywords=request.keywords,
                llm_name=request.llm_name
            )
        
        background_tasks.add_task(run_tracking)
        
        return {
            "message": "Citation tracking started",
            "audit_id": request.audit_id,
            "status": "processing"
        }
        
    except Exception as e:
        logger.error(f"Error starting citation tracking: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/citation-tracking/history/{audit_id}")
def get_citation_history(
    audit_id: int,
    days: int = 30,
    db: Session = Depends(get_db)
):
    """Obtiene historial de citaciones."""
    try:
        history = CitationTrackerService.get_citation_history(db, audit_id, days)
        return history
    except Exception as e:
        logger.error(f"Error getting citation history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/citation-tracking/recent/{audit_id}")
def get_recent_citations(
    audit_id: int,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """Obtiene citaciones recientes."""
    try:
        from app.models import CitationTracking
        from sqlalchemy import desc
        
        citations = db.query(CitationTracking).filter(
            CitationTracking.audit_id == audit_id,
            CitationTracking.is_mentioned == True
        ).order_by(desc(CitationTracking.tracked_at)).limit(limit).all()
        
        return [
            {
                "query": c.query,
                "citation_text": c.citation_text,
                "sentiment": c.sentiment,
                "llm_name": c.llm_name,
                "tracked_at": c.tracked_at.isoformat()
            }
            for c in citations
        ]
    except Exception as e:
        logger.error(f"Error getting recent citations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============= Query Discovery Endpoints =============

@router.post("/query-discovery/discover")
async def discover_queries(
    request: QueryDiscoveryRequest,
    db: Session = Depends(get_db)
):
    """Descubre queries relevantes para el nicho."""
    try:
        llm_function = get_llm_function()
        
        queries = await QueryDiscoveryService.discover_queries(
            brand_name=request.brand_name,
            domain=request.domain,
            industry=request.industry,
            keywords=request.keywords,
            llm_function=llm_function
        )
        
        return {
            "total_discovered": len(queries),
            "queries": queries[:20]  # Top 20
        }
        
    except Exception as e:
        logger.error(f"Error discovering queries: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/query-discovery/opportunities/{audit_id}")
def get_query_opportunities(
    audit_id: int,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """Obtiene las mejores oportunidades de queries."""
    try:
        opportunities = QueryDiscoveryService.get_top_opportunities(db, audit_id, limit)
        return {
            "total_opportunities": len(opportunities),
            "opportunities": opportunities
        }
    except Exception as e:
        logger.error(f"Error getting opportunities: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============= Competitor Citation Endpoints =============

@router.post("/competitor-analysis/analyze")
async def analyze_competitor_citations(
    request: CompetitorAnalysisRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Analiza citaciones de competidores."""
    try:
        # Obtener audit
        audit = AuditService.get_audit(db, request.audit_id)
        if not audit:
            raise HTTPException(status_code=404, detail="Audit not found")
        
        from urllib.parse import urlparse
        domain = urlparse(audit.url).netloc.replace('www.', '')
        brand_name = domain.split('.')[0].title()
        
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
                llm_function=llm_function
            )
        
        background_tasks.add_task(run_analysis)
        
        return {
            "message": "Competitor analysis started",
            "audit_id": request.audit_id,
            "competitors_count": len(request.competitor_domains)
        }
        
    except Exception as e:
        logger.error(f"Error analyzing competitors: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/competitor-analysis/benchmark/{audit_id}")
def get_citation_benchmark(
    audit_id: int,
    db: Session = Depends(get_db)
):
    """Obtiene benchmark de citaciones vs competidores."""
    try:
        benchmark = CompetitorCitationService.get_citation_benchmark(db, audit_id)
        return benchmark
    except Exception as e:
        logger.error(f"Error getting benchmark: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============= Schema Optimizer Endpoints =============

@router.post("/schema/generate")
async def generate_schema(request: SchemaGeneratorRequest):
    """Genera Schema.org optimizado para la página."""
    try:
        llm_function = get_llm_function()
        
        result = await SchemaOptimizerService.generate_schema(
            html_content=request.html_content,
            url=request.url,
            page_type=request.page_type,
            llm_function=llm_function
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error generating schema: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/schema/multiple")
async def generate_multiple_schemas(request: SchemaGeneratorRequest):
    """Genera múltiples schemas si la página lo amerita."""
    try:
        schemas = SchemaOptimizerService.generate_multiple_schemas(
            html_content=request.html_content,
            url=request.url
        )
        
        return {
            "total_schemas": len(schemas),
            "schemas": schemas
        }
        
    except Exception as e:
        logger.error(f"Error generating schemas: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============= Content Template Endpoints =============

@router.get("/content-templates/list")
def list_content_templates():
    """Lista todos los templates disponibles."""
    try:
        templates = ContentTemplateService.get_all_templates()
        return {
            "total_templates": len(templates),
            "templates": templates
        }
    except Exception as e:
        logger.error(f"Error listing templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/content-templates/generate")
async def generate_content_template(request: ContentTemplateRequest):
    """Genera un template de contenido personalizado."""
    try:
        llm_function = get_llm_function()
        
        template = await ContentTemplateService.generate_template(
            template_type=request.template_type,
            topic=request.topic,
            keywords=request.keywords,
            llm_function=llm_function
        )
        
        return template
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating template: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/content-templates/analyze")
def analyze_content(content: str):
    """Analiza contenido existente y sugiere mejoras para GEO."""
    try:
        analysis = ContentTemplateService.analyze_content_for_geo(content)
        return analysis
    except Exception as e:
        logger.error(f"Error analyzing content: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============= Dashboard Summary Endpoint =============

@router.get("/dashboard/{audit_id}")
async def get_geo_dashboard(
    audit_id: int,
    db: Session = Depends(get_db)
):
    """Obtiene resumen completo de GEO para el dashboard."""
    try:
        # Citation tracking summary
        citation_history = CitationTrackerService.get_citation_history(db, audit_id, 30)
        
        # Query opportunities
        opportunities = QueryDiscoveryService.get_top_opportunities(db, audit_id, 5)
        
        # Competitor benchmark
        benchmark = CompetitorCitationService.get_citation_benchmark(db, audit_id)
        
        return {
            "audit_id": audit_id,
            "citation_tracking": {
                "citation_rate": citation_history.get('citation_rate', 0),
                "total_queries": citation_history.get('total_queries', 0),
                "mentions": citation_history.get('mentions', 0),
                "sentiment_breakdown": citation_history.get('sentiment_breakdown', {})
            },
            "top_opportunities": opportunities,
            "competitor_benchmark": {
                "has_data": benchmark.get('has_data', False),
                "your_mentions": benchmark.get('your_mentions', 0),
                "top_competitor": benchmark.get('competitors', [{}])[0].get('name') if benchmark.get('competitors') else None,
                "gap_analysis": benchmark.get('gap_analysis', {})
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting GEO dashboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))
