"""
GEO Score Service - Comprehensive LLM Optimization Scoring

Calcula qué tan optimizado está un sitio/contenido para ser descubierto y citado
por Grandes Modelos de Lenguaje (LLMs) como ChatGPT, Gemini, Claude.

Basado en el manual de GEO (Generative Engine Optimization).
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from ..core.logger import get_logger
from .citation_tracker_service import CitationTrackerService

logger = get_logger(__name__)


class GEOScoreService:
    """
    Servicio principal para calcular y analizar GEO (Generative Engine Optimization)

    GEO es diferente de SEO:
    - SEO: Optimizar para aparecer en SERP (lista de links)
    - GEO: Optimizar para ser CITADO en respuestas de IA
    """

    def __init__(self, db: Session):
        self.db = db
        # Note: These services don't take db in constructor
        # They will be initialized when needed
        self.citation_tracker = None
        self.query_discovery = None

    async def calculate_site_geo_score(
        self, url: str, audit_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Calcula GEO Score completo de un sitio

        Args:
            url: URL del sitio a analizar
            audit_id: ID de auditoría existente (opcional)

        Returns:
            Dict con score global y breakdown por categoría
        """
        logger.info(f"Calculating GEO score for {url}")

        # 1. Obtener datos de auditoría si existe
        audit_data = None
        if audit_id:
            from ..models import Audit

            audit = self.db.query(Audit).filter(Audit.id == audit_id).first()
            if audit:
                audit_data = {
                    "url": audit.url,
                    "fix_plan": audit.fix_plan or [],
                    "external_intelligence": audit.external_intelligence or {},
                    "target_audit": audit.target_audit or {},
                }

        # 2. Calcular scores por categoría
        structure_score = await self._calculate_structure_score(audit_data)
        eeat_score = await self._calculate_eeat_score(url, audit_data)
        schema_score = await self._calculate_schema_score(audit_data)
        content_score = await self._calculate_content_score(audit_data)
        technical_score = await self._calculate_technical_score(audit_data)
        citation_score = await self._calculate_citation_score(url, audit_id)

        # 3. Calcular score global (promedio ponderado)
        weights = {
            "structure": 0.20,
            "eeat": 0.25,  # E-E-A-T es crítico para LLMs
            "schema": 0.15,
            "content": 0.20,
            "technical": 0.10,
            "citation": 0.10,
        }

        overall_score = (
            structure_score * weights["structure"]
            + eeat_score * weights["eeat"]
            + schema_score * weights["schema"]
            + content_score * weights["content"]
            + technical_score * weights["technical"]
            + citation_score * weights["citation"]
        )

        # 4. Generar recomendaciones priorizadas
        recommendations = self._generate_recommendations(
            {
                "structure": structure_score,
                "eeat": eeat_score,
                "schema": schema_score,
                "content": content_score,
                "technical": technical_score,
                "citation": citation_score,
            }
        )

        # 5. Calcular potencial de citación
        citation_potential = self._calculate_citation_potential(overall_score)

        return {
            "overall_score": round(overall_score, 1),
            "grade": self._score_to_grade(overall_score),
            "citation_potential": citation_potential,
            "breakdown": {
                "structure": {
                    "score": round(structure_score, 1),
                    "description": "Fragmentación, Q&A, listas, tablas",
                    "weight": weights["structure"],
                },
                "eeat": {
                    "score": round(eeat_score, 1),
                    "description": "Experiencia, Expertise, Autoridad, Confiabilidad",
                    "weight": weights["eeat"],
                },
                "schema": {
                    "score": round(schema_score, 1),
                    "description": "Schema.org markup (datos estructurados)",
                    "weight": weights["schema"],
                },
                "content": {
                    "score": round(content_score, 1),
                    "description": "Conversacional, original, respuestas directas",
                    "weight": weights["content"],
                },
                "technical": {
                    "score": round(technical_score, 1),
                    "description": "HTML semántico, metadata, accesibilidad",
                    "weight": weights["technical"],
                },
                "citation": {
                    "score": round(citation_score, 1),
                    "description": "Citaciones actuales en LLMs",
                    "weight": weights["citation"],
                },
            },
            "recommendations": recommendations,
            "analyzed_at": datetime.utcnow().isoformat(),
        }

    async def _calculate_structure_score(self, audit_data: Optional[Dict]) -> float:
        """
        Score de estructura (0-100)

        Evalúa:
        - Uso de fragmentos (snippet-level clarity)
        - Formato Q&A
        - Listas y tablas
        - Jerarquía de headings
        """
        if not audit_data:
            return 50.0  # Score neutral sin datos

        score = 100.0
        fix_plan = audit_data.get("fix_plan", [])

        # Penalizar por issues estructurales
        for fix in fix_plan:
            issue = fix.get("issue", "").lower()

            if "h1" in issue or "heading" in issue:
                score -= 15
            if "structure" in issue or "broken" in issue:
                score -= 10

        return max(0, min(100, score))

    async def _calculate_eeat_score(
        self, url: str, audit_data: Optional[Dict]
    ) -> float:
        """
        Score de E-E-A-T (0-100)
        """
        score = 40.0  # Base neutral

        if audit_data:
            # Bonus por tener datos de auditoría
            score += 10

            # Bonus por inteligencia externa
            external_intel = audit_data.get("external_intelligence", {})
            if external_intel:
                score += 15

            # Penalizaciones basadas en fix_plan
            fix_plan = audit_data.get("fix_plan", [])

            # Author issues
            if any("author" in fix.get("issue", "").lower() for fix in fix_plan):
                score -= 25
            else:
                score += 10  # Bonus por tener autor (o no tener issues de autor)

        # Bonus por domain authority
        if any(ext in url for ext in [".edu", ".gov", ".org"]):
            score += 20

        return max(0, min(100, score))

    async def _calculate_schema_score(self, audit_data: Optional[Dict]) -> float:
        """
        Score de Schema markup (0-100)
        """
        if not audit_data:
            return 0.0

        score = 70.0  # Base si no se detectan problemas

        fix_plan = audit_data.get("fix_plan", [])

        # Check si hay issues de schema
        schema_issues = [
            fix
            for fix in fix_plan
            if "schema" in fix.get("issue", "").lower()
            or "structured data" in fix.get("issue", "").lower()
        ]

        if schema_issues:
            # Si hay muchos issues, bajar más el score
            score -= len(schema_issues) * 20
        else:
            # Si no hay issues detectados, es muy bueno
            score = 95.0

        return max(0, min(100, score))

    async def _calculate_content_score(self, audit_data: Optional[Dict]) -> float:
        """
        Score de calidad de contenido (0-100)

        Evalúa:
        - Lenguaje conversacional
        - Respuestas directas
        - Contenido original
        - Longitud apropiada
        """
        if not audit_data:
            return 50.0

        score = 70.0  # Base optimista

        fix_plan = audit_data.get("fix_plan", [])

        # Penalizar por issues de contenido
        for fix in fix_plan:
            issue = fix.get("issue", "").lower()

            if "thin content" in issue or "short" in issue:
                score -= 15
            if "duplicate" in issue:
                score -= 20
            if "keyword stuffing" in issue:
                score -= 10

        return max(0, min(100, score))

    async def _calculate_technical_score(self, audit_data: Optional[Dict]) -> float:
        """
        Score técnico (0-100)

        Evalúa:
        - HTML semántico
        - Metadata completa
        - Velocidad
        - Mobile-friendly
        """
        if not audit_data:
            return 70.0

        score = 80.0

        fix_plan = audit_data.get("fix_plan", [])

        # Penalizar por issues técnicos
        for fix in fix_plan:
            issue = fix.get("issue", "").lower()

            if "meta description" in issue:
                score -= 10
            if "title" in issue and "missing" in issue:
                score -= 15
            if "slow" in issue or "performance" in issue:
                score -= 15

        return max(0, min(100, score))

    async def _calculate_citation_score(
        self, url: str, audit_id: Optional[int] = None
    ) -> float:
        """
        Score de citaciones actuales (0-100)

        Evalúa cuántas veces el sitio es citado en LLMs
        """
        try:
            if audit_id:
                # Get citation history from CitationTrackerService
                history = CitationTrackerService.get_citation_history(
                    db=self.db, audit_id=audit_id, days=30
                )

                if history and history.get("total_queries", 0) > 0:
                    citation_rate = history.get("citation_rate", 0)
                    mentions = history.get("mentions", 0)

                    # Calculate score based on citation rate and mentions
                    # Scale: 0-100 based on citation_rate (0-100%)
                    # Bonus for having actual mentions
                    base_score = citation_rate

                    # Bonus points for number of mentions (max +20)
                    mention_bonus = min(20, mentions * 2)

                    score = base_score + mention_bonus
                    logger.debug(
                        f"Citation score calculated: {score} (rate: {citation_rate}%, mentions: {mentions})"
                    )
                    return min(100.0, score)

            # If no audit_id or no history, return neutral score
            logger.debug(
                f"No citation history available for {url}, returning neutral score"
            )
            return 50.0

        except Exception as e:
            logger.error(f"Error calculating citation score: {e}")
            return 50.0  # Return neutral score on error

    def _generate_recommendations(
        self, scores: Dict[str, float]
    ) -> List[Dict[str, Any]]:
        """Genera recomendaciones priorizadas basadas en scores"""
        recommendations = []

        # Ordenar categorías por score (peores primero)
        sorted_categories = sorted(scores.items(), key=lambda x: x[1])

        for category, score in sorted_categories:
            if score < 70:  # Solo recomendar si está por debajo de 70
                priority = (
                    "CRITICAL" if score < 40 else "HIGH" if score < 60 else "MEDIUM"
                )

                rec = {
                    "category": category,
                    "current_score": score,
                    "priority": priority,
                    "actions": self._get_category_actions(category),
                }
                recommendations.append(rec)

        return recommendations[:5]  # Top 5 recomendaciones

    def _get_category_actions(self, category: str) -> List[str]:
        """Devuelve acciones específicas por categoría"""
        actions_map = {
            "structure": [
                "Agregar secciones FAQ con formato Q&A",
                "Dividir contenido largo en listas numeradas",
                "Usar tablas para comparaciones",
                "Implementar jerarquía clara de H1/H2/H3",
            ],
            "eeat": [
                "Agregar firmas de autor con biografía",
                "Citar fuentes autoritativas con enlaces",
                "Publicar investigación o datos originales",
                "Obtener backlinks de sitios .edu o .gov",
            ],
            "schema": [
                "Implementar Article schema en blogs",
                "Agregar FAQPage schema a secciones Q&A",
                "Usar Organization schema en homepage",
                "Implementar Breadcrumb schema",
            ],
            "content": [
                "Escribir respuestas directas al inicio (pirámide invertida)",
                "Usar lenguaje conversacional y natural",
                "Extender contenido thin (mínimo 800 palabras)",
                "Agregar estadísticas únicas o estudios de caso",
            ],
            "technical": [
                "Agregar meta descriptions a todas las páginas",
                "Optimizar títulos (50-60 caracteres)",
                "Mejorar velocidad de carga",
                "Usar HTML semántico (<article>, <section>)",
            ],
            "citation": [
                "Crear contenido citable (datos originales, guías)",
                "Participar en foros relevantes (Reddit, Quora)",
                "Publicar en plataformas de IA (Medium, Dev.to)",
                "Configurar robots.txt para permitir GPTBot",
            ],
        }

        return actions_map.get(category, [])

    def _calculate_citation_potential(self, overall_score: float) -> str:
        """Calcula potencial de ser citado por LLMs"""
        if overall_score >= 85:
            return "Muy Alto - Contenido premium listo para LLMs"
        elif overall_score >= 70:
            return "Alto - Buena probabilidad de citación"
        elif overall_score >= 55:
            return "Medio - Necesita mejoras para destacar"
        elif overall_score >= 40:
            return "Bajo - Requiere optimización significativa"
        else:
            return "Muy Bajo - Invisible para LLMs"

    def _score_to_grade(self, score: float) -> str:
        """Convierte score numérico a letra"""
        if score >= 90:
            return "A+"
        elif score >= 85:
            return "A"
        elif score >= 80:
            return "A-"
        elif score >= 75:
            return "B+"
        elif score >= 70:
            return "B"
        elif score >= 65:
            return "B-"
        elif score >= 60:
            return "C+"
        elif score >= 55:
            return "C"
        elif score >= 50:
            return "C-"
        elif score >= 45:
            return "D+"
        elif score >= 40:
            return "D"
        else:
            return "F"

    def _extract_brand_from_url(self, url: str) -> str:
        """Extrae nombre de marca de URL"""
        # Simple extraction
        domain = re.sub(r"https?://(www\.)?", "", url)
        domain = domain.split("/")[0]
        domain = domain.split(".")[0]
        return domain.title()

    async def compare_with_competitors(
        self, url: str, competitor_urls: List[str]
    ) -> Dict[str, Any]:
        """
        Compara GEO score con competidores

        Returns:
            Análisis comparativo con gaps y opportunities
        """
        # Score propio
        own_score = await self.calculate_site_geo_score(url)

        # Scores de competidores
        competitor_scores = []
        for comp_url in competitor_urls:
            try:
                comp_score = await self.calculate_site_geo_score(comp_url)
                competitor_scores.append(
                    {
                        "url": comp_url,
                        "score": comp_score["overall_score"],
                        "breakdown": comp_score["breakdown"],
                    }
                )
            except Exception:  # nosec B112
                continue

        # Análisis de gaps
        gaps = []
        if competitor_scores:
            avg_competitor_score = sum(c["score"] for c in competitor_scores) / len(
                competitor_scores
            )

            if own_score["overall_score"] < avg_competitor_score:
                gap = avg_competitor_score - own_score["overall_score"]
                gaps.append(
                    {
                        "type": "overall",
                        "gap": round(gap, 1),
                        "message": f"Estás {gap:.1f} puntos por debajo del promedio de competidores",
                    }
                )

        return {
            "your_score": own_score,
            "competitors": competitor_scores,
            "gaps": gaps,
            "rank": self._calculate_rank(own_score["overall_score"], competitor_scores),
        }

    def _calculate_rank(self, own_score: float, competitors: List[Dict]) -> int:
        """Calcula ranking vs competidores"""
        all_scores = [own_score] + [c["score"] for c in competitors]
        all_scores.sort(reverse=True)
        return all_scores.index(own_score) + 1
