"""
Servicio para análisis de visibilidad en LLMs.
Genera datos de menciones en plataformas de IA.
Core service for GEO (Generative Engine Optimization).
"""
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from ..core.llm_kimi import (
    KimiGenerationError,
    KimiUnavailableError,
    get_llm_function,
    is_kimi_configured,
)

logger = logging.getLogger(__name__)


class LLMVisibilityService:
    """Servicio para generar análisis de visibilidad en LLMs usando KIMI."""

    def __init__(self, db=None):
        """Inicializa el servicio (db es opcional)."""
        self.db = db
        self.llm = get_llm_function()

    @staticmethod
    def _extract_term(raw_keyword: Any) -> str:
        if isinstance(raw_keyword, str):
            return raw_keyword.strip()
        if isinstance(raw_keyword, dict):
            for key in ("term", "keyword", "query"):
                value = raw_keyword.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return ""

    @staticmethod
    def _extract_analysis_for_term(
        batch_analysis: Any, term: str, index: int
    ) -> Dict[str, Any]:
        if isinstance(batch_analysis, dict):
            lowered_map = {
                str(k).strip().lower(): v
                for k, v in batch_analysis.items()
                if isinstance(k, str)
            }
            direct = lowered_map.get(term.lower())
            if isinstance(direct, dict):
                return direct
            results = batch_analysis.get("results")
            if isinstance(results, list) and index < len(results):
                row = results[index]
                if isinstance(row, dict):
                    return row
        if isinstance(batch_analysis, list) and index < len(batch_analysis):
            row = batch_analysis[index]
            if isinstance(row, dict):
                return row
        return {}

    @staticmethod
    def _sanitize_citation(raw: Any) -> Optional[str]:
        if not isinstance(raw, str):
            return None
        text = raw.strip()
        if not text:
            return None
        lowered = text.lower()
        invalid_markers = {
            "no data",
            "n/a",
            "none",
            "null",
            "simulated",
            "estimado",
            "estimada",
            "estimated",
            "unknown",
            "insufficient data",
        }
        if lowered in invalid_markers:
            return None
        return text

    @staticmethod
    def _normalize_platform_data(raw: Any) -> Dict[str, Any]:
        return raw if isinstance(raw, dict) else {}

    @staticmethod
    async def generate_llm_visibility(
        keywords: List[Dict[str, Any]], url: str
    ) -> List[Dict[str, Any]]:
        """
        Genera análisis de visibilidad en LLMs en BATCH para keywords reales.
        Nunca inventa citas: si no hay evidencia clara, devuelve no visible.
        """
        logger.info(f"Generating batch LLM visibility analysis for {url} with KIMI")

        domain = urlparse(url).netloc.replace("www.", "")
        brand = domain.split(".")[0]

        keyword_terms: List[str] = []
        for kw in (keywords or [])[:10]:
            term = LLMVisibilityService._extract_term(kw)
            if term:
                keyword_terms.append(term)

        if not keyword_terms:
            logger.info("No keywords provided for LLM visibility analysis.")
            return []

        service = LLMVisibilityService()
        batch_analysis = await service.analyze_batch_visibility_with_llm(
            brand, keyword_terms
        )

        results = []
        platforms = ["ChatGPT", "Gemini", "Perplexity"]

        for i, term in enumerate(keyword_terms):
            analysis = LLMVisibilityService._extract_analysis_for_term(
                batch_analysis=batch_analysis,
                term=term,
                index=i,
            )

            for j, platform in enumerate(platforms):
                plat_key = platform.lower()
                plat_data = LLMVisibilityService._normalize_platform_data(
                    analysis.get(plat_key, {})
                )

                citation = LLMVisibilityService._sanitize_citation(
                    plat_data.get("citation")
                )
                is_visible = bool(plat_data.get("visible", False)) and bool(citation)

                raw_rank = plat_data.get("rank")
                rank: Optional[int] = None
                if isinstance(raw_rank, int) and raw_rank > 0:
                    rank = raw_rank
                elif isinstance(raw_rank, str) and raw_rank.isdigit():
                    parsed_rank = int(raw_rank)
                    rank = parsed_rank if parsed_rank > 0 else None

                if not is_visible:
                    rank = None

                results.append(
                    {
                        "id": i * len(platforms) + j + 1,
                        "audit_id": 0,
                        "llm_name": platform,
                        "query": term,
                        "is_visible": is_visible,
                        "rank": rank,
                        "citation_text": citation,
                        "evidence_status": "verified"
                        if is_visible
                        else "insufficient_data",
                        "checked_at": datetime.now(timezone.utc).isoformat(),
                    }
                )

        logger.info(
            f"Generated {len(results)} LLM visibility entries for {url} (Batch Mode)"
        )
        return results

    async def analyze_batch_visibility_with_llm(
        self, brand: str, queries: List[str]
    ) -> Dict[str, Any]:
        """
        Usa KIMI para evaluar visibilidad sin fabricar datos.
        Si no hay evidencia clara, debe marcar visible=false.
        """
        if not is_kimi_configured() or not self.llm:
            raise KimiUnavailableError(
                "Kimi provider is not configured. Set NV_API_KEY_ANALYSIS or NVIDIA_API_KEY or NV_API_KEY."
            )

        try:
            system_prompt = """You are a GEO analyst with strict evidence discipline.
            Task: evaluate whether a brand is likely to be cited for each query across ChatGPT, Gemini, and Perplexity.
            Rules:
            - Do NOT fabricate citations.
            - Do NOT simulate quotes.
            - If uncertain, set visible=false, rank=null, citation=null.
            Return JSON with this structure:
            {
                "QUERY_TEXT": {
                    "chatgpt": {"visible": bool, "rank": int|null, "citation": str|null},
                    "gemini": {"visible": bool, "rank": int|null, "citation": str|null},
                    "perplexity": {"visible": bool, "rank": int|null, "citation": str|null}
                },
                ...
            }
            You may return {"results":[...]} only if each item maps 1:1 to the query order.
            """

            user_prompt = f"""Brand: {brand}
            Queries: {json.dumps(queries, ensure_ascii=False)}

            Evaluate each query with conservative confidence.
            If there is no reliable evidence signal, output visible=false and citation=null.
            """

            from .pipeline_service import PipelineService

            response_text = await self.llm(system_prompt, user_prompt)
            if not isinstance(response_text, str) or not response_text.strip():
                raise KimiGenerationError("Kimi returned empty visibility response.")

            # Usar el parser robusto de PipelineService
            parsed = PipelineService.parse_agent_json_or_raw(response_text)
            if parsed in ({}, []):
                raise KimiGenerationError(
                    "Kimi returned invalid JSON payload for LLM visibility."
                )
            return parsed

        except KimiUnavailableError:
            raise
        except KimiGenerationError:
            raise
        except Exception as e:
            logger.error(f"Error in batch visibility analysis: {e}")
            raise KimiGenerationError(f"LLM visibility generation failed: {e}") from e

    async def analyze_visibility_with_llm(
        self, brand: str, query: str
    ) -> Dict[str, Any]:
        """
        DEPRECATED: Individual analysis replaced by analyze_batch_visibility_with_llm.
        """
        return {
            "chatgpt": {"visible": False, "rank": None, "citation": None},
            "gemini": {"visible": False, "rank": None, "citation": None},
            "perplexity": {"visible": False, "rank": None, "citation": None},
        }

    async def check_visibility(
        self, audit_id: int, brand_name: str, queries: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Analiza la visibilidad en LLMs y guarda los resultados en la base de datos.
        """
        try:
            logger.info(
                f"Checking LLM visibility for audit {audit_id}, brand {brand_name}"
            )

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
                        llm_name=res.get("llm_name"),
                        query=res.get("query"),
                        is_visible=res.get("is_visible", False),
                        rank=res.get("rank"),
                        citation_text=res.get("citation_text"),
                        checked_at=datetime.now(timezone.utc),
                    )
                    self.db.add(visibility)

                self.db.commit()
                logger.info(
                    f"Saved {len(results)} visibility results to DB for audit {audit_id}"
                )

            return results
        except Exception as e:
            logger.error(f"Error in check_visibility: {e}")
            if self.db:
                self.db.rollback()
            raise

    def get_visibility(self, audit_id: int) -> List[Any]:
        """Obtiene la visibilidad guardada para una auditoría."""
        if not self.db:
            return []
        from ..models import LLMVisibility

        return (
            self.db.query(LLMVisibility)
            .filter(LLMVisibility.audit_id == audit_id)
            .all()
        )
