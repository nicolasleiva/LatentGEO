#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pipeline_service.py - Servicio de Orquestación Pipeline (Agentes 1 y 2)

Integra la lógica de ag2_pipeline.py en servicios modulares reutilizables.

Proporciona:
- Agente 1: Análisis de Inteligencia Externa
- Agente 2: Sintetizador de Reportes
- Orquestación completa del pipeline
- Búsqueda de competidores
- Auditoría de competidores
"""

import asyncio
import json
import logging
import re
import aiohttp
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urlparse
from datetime import datetime

logger = logging.getLogger(__name__)


class PipelineService:
    """
    Servicio de Orquestación Pipeline.

    Coordina Agente 1, Agente 2, búsqueda de competidores,
    y generación de reportes completos.
    """

    # --- PROMPTS DE AGENTES ---

    EXTERNAL_ANALYSIS_PROMPT = """
Eres un analista de inteligencia de mercado y experto en SEO/GEO. Recibirás un JSON de una auditoría web local.
Tu trabajo es (1) clasificar el sitio y (2) generar un plan de búsqueda para recopilar inteligencia externa.

Tu respuesta DEBE ser un único bloque de código JSON con esta estructura:
{
  "is_ymyl": (bool),
  "category": (string, ej. "Consultoría de Growth B2B"),
  "queries_to_run": [
    { "id": "competitors", "query": "string query para encontrar competidores" },
    { "id": "authority", "query": "string query para encontrar menciones de marca" }
  ]
}

Pasos:
1. Determina si es YMYL (Your Money Your Life): finanzas, salud, legal, noticias
2. Identifica la categoría de negocio específica
3. Genera query específica para encontrar competidores
4. Genera query para encontrar menciones de marca

JSON de entrada:
"""

    REPORT_PROMPT_V10_PRO = """
Eres un Director de Consultoría SEO/GEO de élite. Recibirás un JSON con:
'target_audit', 'external_intelligence', 'search_results', 'competitor_audits'.

Tu respuesta DEBE tener DOS PARTES separadas por: ---START_FIX_PLAN---

PARTE 1: Reporte Markdown (estructura de 9 puntos):
1. Resumen Ejecutivo con hipótesis de impacto y tabla de hallazgos
2. Metodología
3. Inventario de Contenido (tabla con URLs y H1s detectados)
4. Diagnóstico Técnico & Semántico
5. Brechas, Riesgos y Oportunidades (análisis competitivo)
6. Plan de Acción & Prioridades
7. Matriz de Implementación (RACI simplificado)
8. Hoja de Ruta GEO (estrategia de contenido)
9. Métricas, Pruebas y Gobernanza

Incluye:
- Tablas con datos cuantitativos
- GEO Scores comparativos (0-10)
- Gaps de contenido vs competidores
- Análisis de E-E-A-T
- Snippets JSON-LD listos para usar

PARTE 2: Fix Plan (JSON Array)
Después del delimitador ---START_FIX_PLAN---, escribe el JSON del plan de correcciones.

Cada elemento debe tener:
- "page_path": Ruta de la página
- "issue_code": Código del issue
- "priority": CRITICAL, HIGH, MEDIUM, LOW
- "description": Descripción del problema
- "suggestion": Sugerencia de solución

JSON de entrada:
"""

    @staticmethod
    def now_iso() -> str:
        """Retorna timestamp ISO 8601 actual."""
        return datetime.utcnow().isoformat() + "Z"

    @staticmethod
    def filter_competitor_urls(
        search_items: List[Dict], target_domain: str
    ) -> List[str]:
        """
        Filtra una lista de resultados de Google Search y devuelve URLs limpias.

        Args:
            search_items: Lista de items de Google Search API
            target_domain: Dominio objetivo (para excluir)

        Returns:
            Lista de URLs filtradas y únicas
        """
        if not search_items:
            return []

        bad_patterns = [
            "linkedin.com",
            "facebook.com",
            "twitter.com",
            "x.com",
            "youtube.com",
            "instagram.com",
            "pinterest.com",
            "tiktok.com",
            ".gov",
            ".edu",
            ".org",
            "wikipedia.org",
            "medium.com",
            "reddit.com",
            "quora.com",
            "g.page",
            "goo.gl",
            "maps.google.com",
            "github.com",
            "zoom.info",
            "crunchbase.com",
            "amazon.com",
            "ebay.com",
            "mercadolibre.com",
            "clarin.com",
            "lanacion.com",
            target_domain,
        ]

        filtered_urls = []

        for item in search_items:
            url = item.get("link") if isinstance(item, dict) else None
            if not url:
                continue

            try:
                parsed_url = urlparse(url)
                domain = parsed_url.netloc.lstrip("www.")

                is_bad = False
                for pattern in bad_patterns:
                    if pattern in domain or pattern in url:
                        is_bad = True
                        break

                if not is_bad:
                    filtered_urls.append(url)

            except Exception:
                continue

        # Retornar únicos manteniendo orden
        return list(dict.fromkeys(filtered_urls))

    @staticmethod
    def parse_agent_json_or_raw(text: str, default_key: str = "raw") -> Dict[str, Any]:
        """
        Parsea JSON de la respuesta del agente.

        Maneja:
        - Bloques ```json ... ```
        - Bloques ~~~json ... ~~~
        - Trailing commas (error común en LLMs)

        Args:
            text: Texto a parsear
            default_key: Clave por defecto si falla el parseo

        Returns:
            Diccionario parseado o con fallback
        """
        text = (text or "").strip()
        if not text:
            return {default_key: ""}

        # Remover bloques de código
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("~~~json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.startswith("~~~"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        if text.endswith("~~~"):
            text = text[:-3]
        text = text.strip()

        try:
            first_brace = text.find("{")
            first_bracket = text.find("[")

            start = -1
            end_char = "}"

            if first_brace == -1 and first_bracket == -1:
                return {default_key: text}

            if first_brace != -1 and (
                first_bracket == -1 or first_brace < first_bracket
            ):
                start = first_brace
                end_char = "}"
            else:
                start = first_bracket
                end_char = "]"

            end = text.rfind(end_char)
            if end == -1:
                return {default_key: text}

            candidate = text[start : end + 1]

            # Limpiar trailing commas (error común en LLMs)
            candidate_cleaned = re.sub(r",\s*([}\]])", r"\1", candidate)

            parsed = json.loads(candidate_cleaned)
            return parsed

        except Exception as e:
            logger.warning(f"Fallo parsear JSON: {e}. Raw: {text[:200]}...")
            return {default_key: text}

    @staticmethod
    async def run_google_search(query: str, api_key: str, cx_id: str) -> Dict[str, Any]:
        """
        Ejecuta una búsqueda de Google Custom Search.

        Args:
            query: Query a buscar
            api_key: API Key de Google
            cx_id: Custom Search Engine ID

        Returns:
            Resultado de la API o error
        """
        if not api_key or not cx_id:
            logger.warning(
                "GOOGLE_API_KEY o CSE_ID no configurados. Omitiendo búsqueda."
            )
            return {"error": "API Key o CX_ID no configurados"}

        endpoint = "https://www.googleapis.com/customsearch/v1"
        params = {"key": api_key, "cx": cx_id, "q": query}

        logger.info(f"Google Search: {query}")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(endpoint, params=params, timeout=15) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    else:
                        error_text = await resp.text()
                        logger.error(
                            f"Google Search API Error {resp.status}: {error_text}"
                        )
                        return {"error": f"Status {resp.status}", "details": error_text}
        except Exception as e:
            logger.exception(f"Excepción en Google Search: {e}")
            return {"error": str(e)}

    @staticmethod
    async def analyze_external_intelligence(
        target_audit: Dict[str, Any], llm_function: Optional[callable] = None
    ) -> Tuple[Dict[str, Any], List[Dict[str, str]]]:
        """
        Ejecuta Agente 1: Análisis de Inteligencia Externa.

        Args:
            target_audit: Auditoría local del sitio objetivo
            llm_function: Función LLM (debe ser async y retornar string)

        Returns:
            Tupla (external_intelligence, search_queries)
        """
        external_intelligence = {}
        search_queries = []

        try:
            agent1_input_data = {
                "target_audit": {
                    "url": target_audit.get("url"),
                    "structure": {
                        "h1_check": target_audit.get("structure", {}).get(
                            "h1_check", {}
                        )
                    },
                }
            }

            agent1_input = json.dumps(agent1_input_data, ensure_ascii=False)

            if llm_function is None:
                logger.warning(
                    "No LLM function provided. Usando fallback para Agente 1."
                )
                # Fallback: determinar YMYL y generar queries genéricas
                is_ymyl = any(
                    keyword in target_audit.get("url", "").lower()
                    for keyword in ["finance", "health", "legal", "bank", "medical"]
                )
                external_intelligence = {
                    "is_ymyl": is_ymyl,
                    "category": "Categoría Desconocida",
                }
                search_queries = [
                    {
                        "id": "competitors",
                        "query": f"competitors {target_audit.get('url', '')}",
                    },
                    {"id": "authority", "query": f'"{target_audit.get("url", "")}"'},
                ]
            else:
                # Llamar LLM (Gemini, OpenAI, etc.)
                agent1_response_text = await llm_function(
                    system_prompt=PipelineService.EXTERNAL_ANALYSIS_PROMPT,
                    user_prompt=agent1_input,
                )

                agent1_json = PipelineService.parse_agent_json_or_raw(
                    agent1_response_text
                )

                external_intelligence = {
                    "is_ymyl": agent1_json.get("is_ymyl", False),
                    "category": agent1_json.get("category", "Categoría Desconocida"),
                }
                search_queries = agent1_json.get("queries_to_run", [])

            logger.info(
                f"Agente 1: YMYL={external_intelligence['is_ymyl']}, "
                f"Category={external_intelligence['category']}, "
                f"Queries={len(search_queries)}"
            )

            return external_intelligence, search_queries

        except Exception as e:
            logger.exception(f"Error en Agente 1: {e}")
            return {"is_ymyl": False, "category": "Error"}, []

    @staticmethod
    async def generate_competitor_audits(
        competitor_urls: List[str], audit_local_function: Optional[callable] = None
    ) -> List[Dict[str, Any]]:
        """
        Audita localmente un conjunto de URLs de competidores.

        Args:
            competitor_urls: Lista de URLs a auditar
            audit_local_function: Función para ejecutar auditoría local

        Returns:
            Lista de resúmenes de auditoría
        """
        competitor_audits = []

        if not competitor_urls or audit_local_function is None:
            logger.warning("Sin URLs de competidores o función de auditoría.")
            return []

        for i, comp_url in enumerate(competitor_urls[:3]):  # Max 3 competidores
            logger.info(
                f"Auditando competidor {i+1}/{min(len(competitor_urls), 3)}: {comp_url}"
            )
            try:
                summary, _ = await audit_local_function(comp_url)
                if summary.get("status") == 200:
                    competitor_audits.append(summary)
                else:
                    logger.warning(
                        f"Auditoría de {comp_url} retornó status {summary.get('status')}"
                    )
            except Exception as e:
                logger.warning(f"No se pudo auditar competidor {comp_url}: {e}")

        logger.info(f"Auditados {len(competitor_audits)} competidores exitosamente.")
        return competitor_audits

    @staticmethod
    async def generate_report(
        target_audit: Dict[str, Any],
        external_intelligence: Dict[str, Any],
        search_results: Dict[str, Any],
        competitor_audits: List[Dict[str, Any]],
        llm_function: Optional[callable] = None,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Ejecuta Agente 2: Sintetizador de Reportes.

        Args:
            target_audit: Auditoría local del sitio objetivo
            external_intelligence: Datos de Agente 1
            search_results: Resultados de búsqueda
            competitor_audits: Auditorías de competidores
            llm_function: Función LLM

        Returns:
            Tupla (markdown_report, fix_plan_list)
        """
        markdown_report = "# Informe de Auditoría GEO\n\n*Informe fallido: No se pudo generar reporte.*"
        fix_plan = []

        try:
            final_context = {
                "target_audit": target_audit,
                "external_intelligence": external_intelligence,
                "search_results": search_results,
                "competitor_audits": competitor_audits,
            }

            final_context_input = json.dumps(
                final_context, ensure_ascii=False, indent=2
            )

            if llm_function is None:
                logger.warning("No LLM function provided. Generando reporte fallback.")
                # Fallback: generar reporte básico
                markdown_report = f"""
# Informe de Auditoría GEO - {target_audit.get('url')}

## Resumen Ejecutivo

Se realizó una auditoría del sitio objetivo.

**YMYL:** {external_intelligence.get('is_ymyl', False)}
**Categoría:** {external_intelligence.get('category', 'Desconocida')}

## Diagnóstico

### Estructura
- H1: {target_audit.get('structure', {}).get('h1_check', {}).get('status', 'Unknown')}

### E-E-A-T
- Autor: {target_audit.get('eeat', {}).get('author_presence', {}).get('status', 'Unknown')}

### Schema.org
- Presencia: {target_audit.get('schema', {}).get('schema_presence', {}).get('status', 'Unknown')}

## Plan de Acción

Se requiere:
1. Revisar estructura H1/headers
2. Añadir información de autor
3. Implementar Schema.org
"""
                fix_plan = []
            else:
                # Llamar LLM
                report_text = await llm_function(
                    system_prompt=PipelineService.REPORT_PROMPT_V10_PRO,
                    user_prompt=final_context_input,
                )

                # Parsear respuesta (buscar delimitador)
                delimiter = "---START_FIX_PLAN---"

                if delimiter in report_text:
                    parts = report_text.split(delimiter, 1)
                    md_candidate = parts[0].strip()
                    json_candidate = parts[1].strip()

                    # Limpiar bloques de código del markdown
                    if md_candidate.startswith("```markdown"):
                        md_candidate = md_candidate[11:]
                    if md_candidate.endswith("```"):
                        md_candidate = md_candidate[:-3]
                    markdown_report = md_candidate.strip()

                    # Parsear JSON del fix plan
                    parsed_json_part = PipelineService.parse_agent_json_or_raw(
                        json_candidate, default_key="fix_plan_raw"
                    )

                    if isinstance(parsed_json_part, list):
                        fix_plan = parsed_json_part
                    else:
                        fix_plan = parsed_json_part.get("fix_plan", [])

                else:
                    logger.warning(
                        "Delimitador no encontrado. Intentando parseo antiguo."
                    )
                    markdown_report = report_text[:2000]  # Tomar primeros 2000 chars
                    fix_plan = []

            logger.info("Agente 2: Reporte generado exitosamente")
            return markdown_report, fix_plan

        except Exception as e:
            logger.exception(f"Error en Agente 2: {e}")
            return markdown_report, []

    @staticmethod
    async def run_complete_audit(
        url: str,
        target_audit: Dict[str, Any],
        crawler_service: Optional[callable] = None,
        audit_local_service: Optional[callable] = None,
        llm_function: Optional[callable] = None,
        google_api_key: Optional[str] = None,
        google_cx_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Ejecuta el pipeline completo de auditoría.

        Pasos:
        1. Rastrear sitio (si no hay auditoría)
        2. Auditar páginas localmente
        3. Análisis externo (Agente 1)
        4. Búsqueda de competidores
        5. Auditar competidores
        6. Generar reporte (Agente 2)

        Args:
            url: URL a auditar
            target_audit: Auditoría preexistente (opcional)
            crawler_service: Servicio de rastreo
            audit_local_service: Servicio de auditoría local
            llm_function: Función LLM
            google_api_key: API Key de Google
            google_cx_id: Custom Search Engine ID

        Returns:
            Diccionario con resultado completo
        """
        logger.info(f"=== Iniciando Pipeline Completo para {url} ===")

        # PASO 1: Usar auditoría preexistente o generar nueva
        if target_audit is None or not target_audit:
            if audit_local_service is None:
                logger.error("No hay auditoría preexistente ni función audit_local")
                return {"error": "No audit data available"}

            try:
                target_audit, _ = await audit_local_service(url)
                logger.info("Auditoría local completada")
            except Exception as e:
                logger.exception(f"Error en auditoría local: {e}")
                return {"error": f"Local audit failed: {e}"}

        # PASO 2: Análisis Externo (Agente 1)
        (
            external_intelligence,
            search_queries,
        ) = await PipelineService.analyze_external_intelligence(
            target_audit, llm_function
        )

        # PASO 3: Búsqueda de Competidores
        search_results = {}
        competitor_urls_raw = []

        if search_queries and google_api_key and google_cx_id:
            for item in search_queries:
                query_id = item.get("id")
                query = item.get("query")
                if query_id and query:
                    results = await PipelineService.run_google_search(
                        query, google_api_key, google_cx_id
                    )
                    search_results[query_id] = results
                    if query_id == "competitors" and results.get("items"):
                        competitor_urls_raw = results.get("items", [])
        else:
            logger.warning(
                "Omitiendo búsqueda de Google (queries vacías o APIs no configuradas)"
            )

        # PASO 4: Filtrar y Auditar Competidores
        target_domain = urlparse(url).netloc.lstrip("www.")
        competitor_urls_filtradas = PipelineService.filter_competitor_urls(
            competitor_urls_raw, target_domain
        )
        logger.info(
            f"Competidores: {len(competitor_urls_raw)} crudos, "
            f"{len(competitor_urls_filtradas)} después de filtrar"
        )

        competitor_audits = await PipelineService.generate_competitor_audits(
            competitor_urls_filtradas, audit_local_service
        )

        # PASO 5: Generar Reporte (Agente 2)
        markdown_report, fix_plan = await PipelineService.generate_report(
            target_audit,
            external_intelligence,
            search_results,
            competitor_audits,
            llm_function,
        )

        logger.info("=== Pipeline Completado Exitosamente ===")

        return {
            "url": url,
            "timestamp": PipelineService.now_iso(),
            "target_audit": target_audit,
            "external_intelligence": external_intelligence,
            "search_results": search_results,
            "competitor_audits": competitor_audits,
            "report_markdown": markdown_report,
            "fix_plan": fix_plan,
            "status": "completed",
        }


# Funciones de compatibilidad
async def run_complete_audit(
    url: str,
    target_audit: Optional[Dict[str, Any]] = None,
    crawler_service: Optional[callable] = None,
    audit_local_service: Optional[callable] = None,
    llm_function: Optional[callable] = None,
    google_api_key: Optional[str] = None,
    google_cx_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Wrapper para compatibilidad con código existente."""
    return await PipelineService.run_complete_audit(
        url,
        target_audit,
        crawler_service,
        audit_local_service,
        llm_function,
        google_api_key,
        google_cx_id,
    )
