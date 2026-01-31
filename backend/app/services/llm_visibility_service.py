"""
Servicio para análisis de visibilidad en LLMs.
Genera datos de menciones en plataformas de IA.
Core service for GEO (Generative Engine Optimization).
"""
import logging
from typing import List, Dict, Any
from urllib.parse import urlparse
from datetime import datetime, timezone
import asyncio

from ..core.llm_kimi import get_llm_function
from ..core.config import settings

logger = logging.getLogger(__name__)


class LLMVisibilityService:
    """Servicio para generar análisis de visibilidad en LLMs usando KIMI."""
    
    def __init__(self, db=None):
        """Inicializa el servicio (db es opcional)."""
        self.db = db
        self.llm = get_llm_function()
    
    @staticmethod
    async def generate_llm_visibility(keywords: List[Dict[str, Any]], url: str) -> List[Dict[str, Any]]:
        """
        Genera análisis de visibilidad en LLMs en BATCH para todas las keywords usando KIMI.
        """
        try:
            logger.info(f"Generating batch LLM visibility analysis for {url} with KIMI")
            
            domain = urlparse(url).netloc.replace('www.', '')
            brand = domain.split('.')[0]
            
            # Seleccionar top 5 keywords para análisis
            top_keywords = keywords[:5] if keywords else [{"term": f"mejor servicio de {brand}", "difficulty": 50}]
            
            keyword_terms = []
            for kw in top_keywords:
                term = kw.get('term', kw) if isinstance(kw, dict) else kw
                keyword_terms.append(term)
            
            service = LLMVisibilityService()
            batch_analysis = await service.analyze_batch_visibility_with_llm(brand, keyword_terms)
            
            results = []
            platforms = ["ChatGPT", "Gemini", "Perplexity"]
            
            for i, term in enumerate(keyword_terms):
                # Buscar el análisis para esta keyword específica en la respuesta batch
                # Intentar matchear por el término o por el índice
                term_key = term.lower()
                analysis = {}
                
                # Buscar en el dict de resultados (la respuesta batch debería ser un dict con los términos como llaves)
                if isinstance(batch_analysis, dict):
                    # Búsqueda flexible por llave
                    analysis = batch_analysis.get(term, batch_analysis.get(term_key, {}))
                    if not analysis:
                        # Si no se encontró por llave, intentar ver si es un array y usar el índice
                        if "results" in batch_analysis and isinstance(batch_analysis["results"], list) and i < len(batch_analysis["results"]):
                            analysis = batch_analysis["results"][i]
                
                for j, platform in enumerate(platforms):
                    plat_key = platform.lower()
                    plat_data = analysis.get(plat_key, {})
                    
                    is_visible = plat_data.get('visible', False)
                    rank = plat_data.get('rank', None)
                    citation = plat_data.get('citation', "No data")
                    
                    results.append({
                        "id": i * len(platforms) + j + 1,
                        "audit_id": 0,
                        "llm_name": platform,
                        "query": term,
                        "is_visible": is_visible,
                        "rank": rank,
                        "citation_text": citation,
                        "checked_at": datetime.now(timezone.utc).isoformat()
                    })
            
            logger.info(f"Generated {len(results)} LLM visibility entries for {url} (Batch Mode)")
            return results
            
        except Exception as e:
            logger.error(f"Error generating batch LLM visibility: {e}")
            return []
    
    async def analyze_batch_visibility_with_llm(self, brand: str, queries: List[str]) -> Dict[str, Any]:
        """
        Usa KIMI para ESTIMAR la visibilidad de la marca para múltiples queries en un solo llamado.
        """
        try:
            system_prompt = """Eres un experto en GEO (Generative Engine Optimization). 
            Tu tarea es ESTIMAR la visibilidad de una marca en las respuestas de IA (ChatGPT, Gemini, Perplexity).
            Analiza la probabilidad de que la marca sea mencionada para CADA una de las queries dadas.
            Devuelve un JSON con la estructura:
            {
                "QUERY_TEXT": {
                    "chatgpt": {"visible": bool, "rank": int|null, "citation": str},
                    "gemini": {"visible": bool, "rank": int|null, "citation": str},
                    "perplexity": {"visible": bool, "rank": int|null, "citation": str}
                },
                ...
            }
            Si prefieres, también puedes devolver un array de objetos bajo la llave "results".
            """
            
            user_prompt = f"""Marca: {brand}
            Queries a analizar: {json.dumps(queries, ensure_ascii=False)}
            
            Basado en tu conocimiento del mercado y la autoridad de la marca, estima su visibilidad para cada query.
            Sé realista. Si la marca es pequeña y la query es genérica, pon 'visible': false.
            Genera un fragmento de citación corto y simulado si es true.
            """
            
            from .pipeline_service import PipelineService
            response_text = await self.llm(system_prompt, user_prompt)
            
            # Usar el parser robusto de PipelineService
            return PipelineService.parse_agent_json_or_raw(response_text)
            
        except Exception as e:
            logger.error(f"Error in batch visibility analysis: {e}")
            return {}

    async def analyze_visibility_with_llm(self, brand: str, query: str) -> Dict[str, Any]:
        """
        DEPRECATED: Individual analysis replaced by analyze_batch_visibility_with_llm.
        """
        return {
            "chatgpt": {"visible": False, "rank": None, "citation": "Deprecated"},
            "gemini": {"visible": False, "rank": None, "citation": "Deprecated"},
            "perplexity": {"visible": False, "rank": None, "citation": "Deprecated"}
        }

    async def check_visibility(self, audit_id: int, brand_name: str, queries: List[str]) -> List[Dict[str, Any]]:
        """
        Analiza la visibilidad en LLMs y guarda los resultados en la base de datos.
        """
        try:
            logger.info(f"Checking LLM visibility for audit {audit_id}, brand {brand_name}")
            
            # Formatear queries como Keywords para generate_llm_visibility
            keywords = [{"term": q} for q in queries]
            
            # Obtener URL del audit para el dominio
            audit = None
            if self.db:
                from ..models import Audit
                audit = self.db.query(Audit).filter(Audit.id == audit_id).first()
            
            url = audit.url if audit else f"https://{brand_name}.com"
            
            # Generar visibilidad
            results = await self.generate_llm_visibility(keywords, url)
            
            # Guardar en DB si tenemos sesión
            if self.db and results:
                from ..models import LLMVisibility
                for res in results:
                    visibility = LLMVisibility(
                        audit_id=audit_id,
                        llm_name=res.get('llm_name'),
                        query=res.get('query'),
                        is_visible=res.get('is_visible', False),
                        rank=res.get('rank'),
                        citation_text=res.get('citation_text'),
                        checked_at=datetime.now(timezone.utc)
                    )
                    self.db.add(visibility)
                
                self.db.commit()
                logger.info(f"✅ Saved {len(results)} visibility results to DB for audit {audit_id}")
            
            return results
            
        except Exception as e:
            logger.error(f"Error in check_visibility: {e}")
            if self.db:
                self.db.rollback()
            return []

    def get_visibility(self, audit_id: int) -> List[Any]:
        """Obtiene la visibilidad guardada para una auditoría."""
        if not self.db:
            return []
        from ..models import LLMVisibility
        return self.db.query(LLMVisibility).filter(LLMVisibility.audit_id == audit_id).all()

