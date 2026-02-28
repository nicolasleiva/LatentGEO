#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
competitor_citation_service.py - Análisis de Citaciones de Competidores

Analiza quién es más citado que tú y por qué.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class CompetitorCitationService:
    """
    Servicio para analizar citaciones de competidores.

    Funcionalidades:
    - Comparar visibilidad en LLMs vs competidores
    - Analizar por qué competidores son más citados
    - Identificar gaps de contenido
    - Recomendar estrategias de mejora
    """

    _ALLOWED_ERROR_CATEGORIES = {"internal_error", "invalid_input", "unauthorized"}
    _ALLOWED_ERROR_CODES = {
        "workers_unavailable",
        "timeout",
        "dependency_error",
        "internal_error",
    }

    @staticmethod
    async def analyze_competitor_citations(
        db: Session,
        audit_id: int,
        brand_name: str,
        domain: str,
        competitor_domains: List[str],
        queries: List[str],
        llm_function: Optional[callable] = None,
    ) -> Dict[str, Any]:
        """
        Analiza citaciones de competidores.

        Args:
            db: Sesión de base de datos
            audit_id: ID del audit
            brand_name: Tu marca
            domain: Tu dominio
            competitor_domains: Dominios de competidores
            queries: Queries a analizar
            llm_function: Función LLM

        Returns:
            Análisis comparativo de citaciones
        """
        logger.info(
            f"Analizando citaciones para {brand_name} vs {len(competitor_domains)} competidores"
        )

        if not llm_function:
            from app.core.llm_kimi import get_llm_function

            llm_function = get_llm_function()

        # Resultados por competidor
        results = {
            "your_brand": {
                "name": brand_name,
                "domain": domain,
                "mentions": 0,
                "queries_mentioned": [],
                "avg_position": 0,
                "sentiment_breakdown": {},
            },
            "competitors": [],
        }

        # Analizar cada query
        for query in queries:
            try:
                response = await llm_function(query)

                if not response:
                    continue

                # Verificar tu marca
                your_mentioned = CompetitorCitationService._is_mentioned(
                    response, brand_name, domain
                )

                if your_mentioned:
                    results["your_brand"]["mentions"] += 1
                    results["your_brand"]["queries_mentioned"].append(query)

                    position = CompetitorCitationService._get_mention_position(
                        response, brand_name
                    )
                    results["your_brand"]["avg_position"] += position

                # Verificar competidores
                for comp_domain in competitor_domains:
                    comp_name = (
                        comp_domain.replace("www.", "")
                        .replace(".com", "")
                        .replace(".io", "")
                    )

                    comp_mentioned = CompetitorCitationService._is_mentioned(
                        response, comp_name, comp_domain
                    )

                    if comp_mentioned:
                        # Buscar o crear entrada del competidor
                        comp_data = next(
                            (
                                c
                                for c in results["competitors"]
                                if c["domain"] == comp_domain
                            ),
                            None,
                        )

                        if not comp_data:
                            comp_data = {
                                "name": comp_name,
                                "domain": comp_domain,
                                "mentions": 0,
                                "queries_mentioned": [],
                                "avg_position": 0,
                                "reasons": [],
                            }
                            results["competitors"].append(comp_data)

                        comp_data["mentions"] += 1
                        comp_data["queries_mentioned"].append(query)

                        position = CompetitorCitationService._get_mention_position(
                            response, comp_name
                        )
                        comp_data["avg_position"] += position

            except Exception as e:
                logger.error(f"Error analizando query '{query}': {e}")
                continue

        # Calcular posiciones promedio
        len(queries)

        if results["your_brand"]["mentions"] > 0:
            results["your_brand"]["avg_position"] /= results["your_brand"]["mentions"]

        for comp in results["competitors"]:
            if comp["mentions"] > 0:
                comp["avg_position"] /= comp["mentions"]

        # Ordenar competidores por menciones
        results["competitors"].sort(key=lambda x: x["mentions"], reverse=True)

        # Analizar por qué competidores son más citados
        results["gap_analysis"] = (
            await CompetitorCitationService._analyze_citation_gaps(
                results, queries, llm_function
            )
        )

        # Guardar en DB
        CompetitorCitationService._save_analysis(db, audit_id, results)

        logger.info(
            f"Análisis completado. Tu marca: {results['your_brand']['mentions']} menciones"
        )

        return results

    @staticmethod
    def _is_mentioned(text: str, brand_name: str, domain: str) -> bool:
        """Verifica si una marca está mencionada."""
        text_lower = text.lower()
        brand_lower = brand_name.lower()
        domain_clean = (
            domain.replace("www.", "").replace(".com", "").replace(".io", "").lower()
        )

        return brand_lower in text_lower or domain_clean in text_lower

    @staticmethod
    def _get_mention_position(text: str, brand_name: str) -> int:
        """Obtiene la posición de la mención (1=primero)."""
        sentences = text.split(".")
        brand_lower = brand_name.lower()

        for i, sentence in enumerate(sentences):
            if brand_lower in sentence.lower():
                return i + 1

        return 999  # No encontrado

    @staticmethod
    async def _analyze_citation_gaps(
        results: Dict, queries: List[str], llm_function: callable
    ) -> Dict[str, Any]:
        """
        Analiza por qué competidores son más citados.

        Usa LLM para generar insights.
        """
        try:
            # Preparar datos para el LLM
            your_mentions = results["your_brand"]["mentions"]
            top_competitors = results["competitors"][:3]

            if not top_competitors:
                return {
                    "has_gaps": False,
                    "message": "No hay competidores con mayor visibilidad",
                }

            comp_summary = "\n".join(
                [f"- {c['name']}: {c['mentions']} menciones" for c in top_competitors]
            )

            prompt = f"""Analiza por qué estos competidores tienen mejor visibilidad en IA que mi marca.

MI MARCA: {results['your_brand']['name']}
Menciones: {your_mentions}

COMPETIDORES MÁS VISIBLES:
{comp_summary}

Basado en esta información, proporciona:

1. **Posibles razones** por las que los competidores son más citados (máximo 3 razones)
2. **Acciones recomendadas** para mejorar mi visibilidad (máximo 3 acciones concretas)

Sé específico y accionable. Formato:

## Razones
1. [Razón]
2. [Razón]
3. [Razón]

## Acciones Recomendadas
1. [Acción]
2. [Acción]
3. [Acción]
"""

            analysis = await llm_function(prompt)

            return {
                "has_gaps": your_mentions < top_competitors[0]["mentions"],
                "citation_gap": top_competitors[0]["mentions"] - your_mentions,
                "top_competitor": top_competitors[0]["name"],
                "analysis": analysis,
                "recommendations": CompetitorCitationService._extract_recommendations(
                    analysis
                ),
            }

        except Exception as e:
            logger.exception("Error en análisis de gaps")
            return CompetitorCitationService._error_payload(
                error_code=CompetitorCitationService._resolve_error_code(e)
            )

    @staticmethod
    def _extract_recommendations(analysis_text: str) -> List[str]:
        """Extrae recomendaciones del análisis."""
        lines = analysis_text.split("\n")
        recommendations = []

        in_recommendations = False
        for line in lines:
            if "acciones" in line.lower() or "recomendadas" in line.lower():
                in_recommendations = True
                continue

            if in_recommendations and line.strip():
                # Limpiar numeración y formato
                rec = line.strip().lstrip("123456789.- *")
                if len(rec) > 10:
                    recommendations.append(rec)

        return recommendations[:5]

    @staticmethod
    def _save_analysis(db: Session, audit_id: int, results: Dict):
        """Guarda análisis en la base de datos."""
        try:
            import json

            from app.models import CompetitorCitationAnalysis

            analysis = CompetitorCitationAnalysis(
                audit_id=audit_id,
                your_mentions=results["your_brand"]["mentions"],
                competitor_data=json.dumps(results["competitors"]),
                gap_analysis=json.dumps(results.get("gap_analysis", {})),
                analyzed_at=datetime.utcnow(),
            )

            db.add(analysis)
            db.commit()
            logger.info("Análisis de competidores guardado en DB")
        except Exception as e:
            logger.error(f"Error guardando análisis: {e}")
            db.rollback()

    @staticmethod
    def _resolve_error_code(exc: Exception) -> str:
        message = str(exc).lower()
        if "timeout" in message:
            return "timeout"
        if "unavailable" in message or "worker" in message:
            return "workers_unavailable"
        return "dependency_error"

    @staticmethod
    def _sanitize_error_category(error_value: Any) -> str:
        if isinstance(error_value, str):
            normalized = error_value.strip().lower()
            if normalized in CompetitorCitationService._ALLOWED_ERROR_CATEGORIES:
                return normalized
        return "internal_error"

    @staticmethod
    def _sanitize_error_code(error_code_value: Any) -> str:
        if isinstance(error_code_value, str):
            normalized = error_code_value.strip().lower()
            if normalized in CompetitorCitationService._ALLOWED_ERROR_CODES:
                return normalized
        return "dependency_error"

    @staticmethod
    def _error_payload(error_code: str = "internal_error") -> Dict[str, Any]:
        safe_error_code = CompetitorCitationService._sanitize_error_code(error_code)
        return {
            "has_data": False,
            "has_gaps": None,
            "error": "internal_error",
            "error_code": safe_error_code,
        }

    @staticmethod
    def _sanitize_gap_analysis(payload: Any) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            return CompetitorCitationService._error_payload("dependency_error")

        if "error" in payload or "error_code" in payload:
            return {
                "has_data": False,
                "has_gaps": None,
                "error": CompetitorCitationService._sanitize_error_category(
                    payload.get("error")
                ),
                "error_code": CompetitorCitationService._sanitize_error_code(
                    payload.get("error_code")
                ),
            }

        has_gaps = payload.get("has_gaps")
        if isinstance(has_gaps, bool):
            payload["has_gaps"] = has_gaps
        else:
            payload["has_gaps"] = False
        return payload

    @staticmethod
    def get_citation_benchmark(db: Session, audit_id: int) -> Dict[str, Any]:
        """
        Obtiene benchmark de citaciones.

        Returns:
            Comparativa visual de tu marca vs competidores
        """
        try:
            from app.models import CompetitorCitationAnalysis

            analysis = (
                db.query(CompetitorCitationAnalysis)
                .filter(CompetitorCitationAnalysis.audit_id == audit_id)
                .order_by(CompetitorCitationAnalysis.analyzed_at.desc())
                .first()
            )

            if not analysis:
                return {
                    "has_data": False,
                    "has_gaps": None,
                    "message": "No hay análisis de competidores disponible",
                }

            import json

            competitors = json.loads(analysis.competitor_data)
            gap_analysis = json.loads(analysis.gap_analysis) if analysis.gap_analysis else {}
            gap_analysis = CompetitorCitationService._sanitize_gap_analysis(gap_analysis)

            # Preparar datos para visualización
            return {
                "has_data": True,
                "your_mentions": analysis.your_mentions,
                "competitors": competitors,
                "gap_analysis": gap_analysis,
                "timestamp": analysis.analyzed_at.isoformat(),
            }

        except Exception:
            logger.exception("Error obteniendo benchmark")
            return CompetitorCitationService._error_payload("internal_error")
