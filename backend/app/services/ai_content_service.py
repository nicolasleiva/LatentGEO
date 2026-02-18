"""
Servicio para sugerencias de contenido AI.
Genera recomendaciones de contenido basadas en keywords y gaps.
"""
import json
import logging
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from ..core.llm_kimi import (
    KimiGenerationError,
    KimiUnavailableError,
    get_llm_function,
    is_kimi_configured,
)
from ..models import AIContentSuggestion

logger = logging.getLogger(__name__)


class AIContentService:
    """Servicio para generar sugerencias de contenido."""

    def __init__(self, db: Session):
        self.db = db
        self.llm_function = get_llm_function()

    async def generate_suggestions(
        self, audit_id: int, domain: str, topics: List[str]
    ) -> List[AIContentSuggestion]:
        """
        Genera sugerencias de contenido usando IA basándose en el contexto real del negocio.

        Args:
            audit_id: ID de la auditoría
            domain: Dominio del sitio
            topics: Lista de topics adicionales a analizar

        Returns:
            Lista de sugerencias guardadas
        """
        logger.info(
            f"Generating AI content suggestions for {domain} with topics: {topics}"
        )

        # Cargar contexto completo de la auditoría
        from ..models import Audit

        audit = self.db.query(Audit).filter(Audit.id == audit_id).first()

        # Extraer información del negocio
        business_context = self._extract_business_context(audit, domain)

        suggestions = []
        brand = domain.replace("www.", "").split(".")[0]

        if not is_kimi_configured() or not self.llm_function:
            logger.error("Kimi provider is not configured for AI content suggestions.")
            raise KimiUnavailableError(
                "Kimi provider is not configured. Set NV_API_KEY_ANALYSIS or NVIDIA_API_KEY or NV_API_KEY."
            )

        try:
            prompt = f"""
            Actúa como experto en Content Marketing y SEO.
            
            **CONTEXTO DEL NEGOCIO:**
            - Sitio web: {domain}
            - Marca: {brand}
            - Categoría de negocio: {business_context['category']}
            - Descripción: {business_context['description']}
            - Público objetivo: {business_context['audience']}
            - Competidores: {', '.join(business_context['competitors'][:3]) if business_context['competitors'] else 'No identificados'}
            - Keywords principales: {', '.join(business_context['top_keywords'][:5]) if business_context['top_keywords'] else 'No disponibles'}
            
            **TOPICS ADICIONALES A INCLUIR:** {', '.join(topics) if topics else 'Ninguno especificado'}
            
            **TU TAREA:**
            Genera 5 ideas de contenido que:
            1. Sean RELEVANTES para el negocio real ({business_context['category']})
            2. Combinen el core del negocio con los topics adicionales si los hay
            3. Ayuden a posicionar la marca como autoridad en su nicho
            4. Sean atractivas para el público objetivo
            
            Para cada idea incluye:
            - title: Título atractivo y específico
            - content_type: guide, comparison, tutorial, case_study, faq, listicle
            - target_keyword: Keyword principal (relevante al negocio)
            - priority: high, medium, low
            - outline: Array con 5 secciones

            Responde SOLO con JSON:
            [
                {{
                    "title": "...",
                    "content_type": "guide",
                    "target_keyword": "...",
                    "priority": "high",
                    "outline": ["Sección 1", "Sección 2", ...]
                }}
            ]
            """

            response = await self.llm_function(
                system_prompt="Eres un experto en SEO y Content Marketing. Responde solo con JSON válido.",
                user_prompt=prompt,
            )

            # Parsear respuesta
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]

            ai_suggestions = json.loads(response.strip())
            if not isinstance(ai_suggestions, list):
                raise KimiGenerationError(
                    "Kimi returned invalid JSON payload for AI content suggestions."
                )

            for idx, sugg in enumerate(ai_suggestions[:5]):
                suggestion = AIContentSuggestion(
                    audit_id=audit_id,
                    topic=sugg.get("title", f"Content Idea {idx+1}"),
                    suggestion_type=sugg.get("content_type", "guide"),
                    content_outline={
                        "target_keyword": sugg.get("target_keyword", ""),
                        "sections": sugg.get("outline", []),
                        "business_context": business_context["category"],
                    },
                    priority=sugg.get("priority", "medium"),
                )
                self.db.add(suggestion)
                suggestions.append(suggestion)

        except KimiUnavailableError:
            self.db.rollback()
            raise
        except KimiGenerationError:
            self.db.rollback()
            raise
        except json.JSONDecodeError as e:
            self.db.rollback()
            logger.error(f"Invalid JSON from Kimi for AI suggestions: {e}")
            raise KimiGenerationError(
                "Kimi returned invalid JSON payload for AI content suggestions."
            ) from e
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error generating AI suggestions: {e}")
            raise KimiGenerationError(
                f"AI content suggestion generation failed: {e}"
            ) from e

        self.db.commit()
        for s in suggestions:
            self.db.refresh(s)

        logger.info(
            f"Generated {len(suggestions)} content suggestions for {business_context['category']}"
        )
        return suggestions

    def _extract_business_context(self, audit, domain: str) -> Dict[str, Any]:
        """Extrae el contexto del negocio desde la auditoría."""
        context = {
            "category": "General",
            "description": "",
            "audience": "General",
            "competitors": [],
            "top_keywords": [],
            "is_ymyl": False,
        }

        if not audit:
            return context

        # Extraer categoría desde external_intelligence o category
        if audit.category:
            context["category"] = audit.category

        ext_intel = audit.external_intelligence or {}
        if ext_intel:
            context["category"] = ext_intel.get("category", context["category"])
            context["is_ymyl"] = ext_intel.get("is_ymyl", False)
            context["description"] = ext_intel.get("business_description", "")
            context["audience"] = ext_intel.get("target_audience", "General")

        # Extraer competidores
        if audit.competitors:
            context["competitors"] = (
                audit.competitors if isinstance(audit.competitors, list) else []
            )

        comp_audits = audit.competitor_audits or []
        if comp_audits:
            for comp in comp_audits[:3]:
                if isinstance(comp, dict) and comp.get("url"):
                    context["competitors"].append(comp["url"])

        # Extraer keywords desde la BD
        if hasattr(audit, "keywords") and audit.keywords:
            context["top_keywords"] = [k.term for k in audit.keywords[:10]]

        # Extraer keywords desde target_audit
        target_audit = audit.target_audit or {}
        if target_audit:
            # Intentar obtener keywords del contenido analizado
            content = target_audit.get("content", {})
            if content.get("main_topics"):
                context["top_keywords"].extend(content.get("main_topics", [])[:5])

        logger.info(
            f"Extracted business context: category={context['category']}, keywords={len(context['top_keywords'])}"
        )
        return context

    def get_suggestions(self, audit_id: int) -> List[AIContentSuggestion]:
        """Obtiene sugerencias existentes para una auditoría."""
        return (
            self.db.query(AIContentSuggestion)
            .filter(AIContentSuggestion.audit_id == audit_id)
            .all()
        )

    @staticmethod
    def generate_content_suggestions(
        keywords: List[Dict[str, Any]], url: str
    ) -> List[Dict[str, Any]]:
        """
        Genera sugerencias de contenido basadas en keywords.
        Returns empty list if no real data available.
        """
        return []
