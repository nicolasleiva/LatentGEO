#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ag2_pipeline.py — Orquestador avanzado (v10.1)

Flujo:
- v10.1: CORREGIDO - Restaurados todos los imports locales para que
         el script funcione de forma independiente (soluciona errores Pylance).
         - Corregidos los fences de código (```json) internos en los strings
           (en REPORT_PROMPT_V10_PRO) por tildes (~~~json) para evitar
           romper el renderizado de Markdown.
- v10.0: Actualizado el prompt del Agente 2 (REPORT_PROMPT_V10_PRO)
         para integrar sugerencias avanzadas del usuario (snippets,
         matriz RACI, hoja de ruta GEO, métricas de CI/CD).
- v9.3:  CORREGIDO - Parseo del Agente 2 con delimitador '---START_FIX_PLAN---'.
- v9.2:  CORREGIDO - Error 'str' object has no attribute 'get' en filtro de competidores.
- v9.1:  Añadido filtro de competidores y prompt de Agente 1 mejorado.
"""
import os
import sys
import json
import argparse
import asyncio
import logging
import random
import re
import aiohttp
from urllib.parse import urlparse, quote_plus
from dotenv import load_dotenv

# Imports locales (de los otros archivos .py en la carpeta)
try:
    from utils import save_json
    from audit_local import run_local_audit
    from governance_generator import write_files as write_gov_files
    from crawler import crawl_site
    from create_pdf import create_comprehensive_pdf, FPDF_AVAILABLE
except ImportError as e:
    print(
        f"Error: No se pudo importar un módulo local. Asegúrate que todos los .py (utils, crawler, etc.) estén en la misma carpeta."
    )
    print(f"Detalle: {e}")
    sys.exit(1)


# Dependencias opcionales (autogen, genai)
try:
    from autogen import ConversableAgent, LLMConfig

    AG2_AVAILABLE = True
except Exception as e:
    logging.info("autogen (ag2) not importable or not installed: %s", e)
    ConversableAgent = None
    LLMConfig = None
    AG2_AVAILABLE = False

try:
    from google import genai

    GENAI_AVAILABLE = True
except Exception as e:
    logging.info("google.genai not importable or not installed: %s", e)
    GENAI_AVAILABLE = False


# --- Cargar variables de entorno ---
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
CSE_ID = os.getenv("CSE_ID")

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("ag2_pipeline")


# ----------------------------------------------------------------------
# 🤖 AGENTE 1: ANALISTA EXTERNO (v9.1)
# ----------------------------------------------------------------------

EXTERNAL_ANALYSIS_PROMPT = """
Eres un analista de inteligencia de mercado y experto en SEO/GEO. Recibirás un JSON de una auditoría web local ('target_audit').
Tu trabajo es (1) clasificar el sitio y (2) generar un plan de búsqueda (queries) para recopilar inteligencia externa.

Tu respuesta DEBE ser un único bloque de código JSON con la siguiente estructura:
{
  "is_ymyl": (bool),
  "category": (string, ej. "Consultoría de Growth B2B", "Software de IA", "Blog de Finanzas"),
  "queries_to_run": [
    { "id": "competitors", "query": (string) },
    { "id": "authority", "query": (string) }
  ]
}

Pasos a seguir:
1.  **Clasificar YMYL:** Basado en 'target_audit.url' y 'target_audit.structure.h1_check.details.example', determina si el sitio es "YMYL" (Your Money Your Life - finanzas, salud, legal, noticias importantes).
2.  **Clasificar Categoría:** Identifica la categoría de negocio específica (ej. "Agencia de Marketing Digital B2B", "E-commerce de moda").
3.  **Generar Query de Competidores:** Crea una query de Google Search MUY ESPECÍFICA para encontrar competidores directos. USA LA CATEGORÍA. (ej. 'mejores agencias de growth B2B', 'plataformas SaaS de IA para ventas').
4.  **Generar Query de Autoridad:** Crea una query de Google Search para encontrar menciones de la marca. (ej. '"[dominio]" -site:[dominio]').

JSON de entrada:
"""

# ----------------------------------------------------------------------
# 🤖 AGENTE 2: SINTETIZADOR DE REPORTE (v10.1 - CORREGIDO FENCE)
# ----------------------------------------------------------------------

REPORT_PROMPT_V10_PRO = """
Eres un Director de Consultoría SEO/GEO de élite. Recibirás un JSON gigante con cuatro claves: 'target_audit', 'external_intelligence', 'search_results' y 'competitor_audits'.
Tu trabajo es generar un INFORME DE AUDITORÍA COMPLETO (en Markdown) y un PLAN DE ACCIÓN (en JSON), siguiendo rigurosamente la plantilla y los requisitos de entregables.

Tu respuesta DEBE tener DOS PARTES separadas por un delimitador claro.
1.  Primero, escribe el "report_markdown" completo (siguiendo la plantilla de 9 puntos).
2.  Segundo, escribe el delimitador: ---START_FIX_PLAN---
3.  Tercero, escribe el JSON "fix_plan" (y NADA MÁS después).

--- REQUISITOS DEL "report_markdown" (Plantilla de 9 Puntos) ---

# 1. Resumen Ejecutivo (Enfoque de Negocio)
* Escribe 1-2 párrafos para la alta dirección. Enfócate en el impacto de negocio.
* **Hipótesis de Impacto:** Incluye una estimación de negocio (Ej. "Se estima que la corrección de los fallos críticos de E-E-A-T... podría incrementar la conversión de leads en un 15% en 12 meses.").
* **Tabla de Hallazgos (Cuantificada):** Genera una tabla Markdown con el resumen de problemas. ¡USA PORCENTAJES!
    | Categoría | Total Problemas | Críticos | % Páginas Afectadas |
    | :--- | :--- | :--- | :--- |
    | Estructura | (Calcula) | (Calcula) | (Ej. 100% (3/3)) |
    | Contenido/GEO | (Calcula) | (Calcula) | (Ej. 66% (2/3)) |
    | E-E-A-T | (Calcula) | (Calcula) | (Ej. 100% (3/3)) |
    | Schema.org | (Calcula) | (Calcula) | (Ej. 100% (3/3)) |

# 2. Metodología
* Escribe 1-2 párrafos describiendo la metodología.
* Menciona las fuentes de datos: 'target_audit' (auditoría local), 'external_intelligence' (clasificación YMYL), 'search_results' (análisis de autoridad y competidores) y 'competitor_audits' (análisis de schema de la competencia).

# 3. Inventario de Contenido (Muestra Auditada)
* Genera una tabla Markdown con las páginas auditadas.
    | URL (Path) | H1 Detectado |
    | :--- | :--- |
    | (De 'target_audit.audited_page_paths') | (De 'target_audit.structure.h1_check.examples') |

# 4. Diagnóstico Técnico & Semántico
* **4.1 Estructura Técnica:** Analiza 'target_audit.structure'. Unifica los hallazgos: si los H1 están 'pass', aclara que los problemas de jerarquía son H2-H6.
* **4.2 Estructura de Contenido para IA (GEO):** Analiza 'target_audit.content'. Discute 'fragment_clarity' (párrafos largos) y 'question_targeting' (FAQs). **Añade un ejemplo "Antes/Después"** de cómo fragmentar un párrafo denso en una lista Q&A.
* **4.3 Autoridad & Citabilidad (E-E-A-T):**
    * Usa 'external_intelligence.is_ymyl' para definir la gravedad.
    * Usa 'target_audit.eeat.author_presence' y 'content_freshness'.
    * **Evidencia Externa:** Lista 1-2 URLs concretas de 'search_results.authority.items' como evidencia de "Autoridad" externa.
* **4.4 Schema.org:** Analiza 'target_audit.schema.schema_presence'.

# 5. Brechas, Riesgos y Oportunidad (Análisis Competitivo)
* **5.1 Tabla Comparativa - GEO Score:** Genera una tabla Markdown. Calcula un "GEO Score" (0-10) para el cliente y los competidores ('competitor_audits') basado en 'schema_presence.status', 'semantic_html.score_percent' y 'conversational_tone.score'.
    | Sitio Web | GEO Score (0-10) | Schema Detectado |
    | :--- | :--- | :--- |
    | [Cliente] | (Calcula) | (Ej. Ausente) |
    | [Rival 1] | (Calcula) | (Ej. Organization, WebSite) |
* **5.2 Análisis de Gaps de Contenido:** Analiza los 'search_results.competitors.items.snippet' para identificar 2-3 temas o "gap topics" que los competidores cubren y el cliente no.
* **5.3 Análisis de Autoridad:** Identifica 1-2 dominios/URLs de la competencia que sirvan como objetivos de backlinks.

# 6. Plan de Acción & Prioridades
* **Prioridad 1: CRÍTICA (Acción Inmediata)**: Lista las tareas CRÍTICAS (ej. Implementar Schema 'Organization').
* **Prioridad 2: ALTA (Impacto Alto)**: Lista las tareas ALTAS (ej. Falla de Jerarquía H1->H3, crear plantillas de autor).
* **Prioridad 3: MEDIANA (Optimización)**: Lista las tareas MEDIANAS (ej. fragmentación de contenido).

# 7. Matriz de Implementación y Roadmap
* **7.1 Matriz de Tareas (RACI Simplificado):** Genera una tabla Markdown para el plan.
    | Tarea / Hallazgo | Prioridad | Esfuerzo (Est.) | Responsable (RACI) | Criterio de Éxito (KPI) |
    | :--- | :--- | :--- | :--- | :--- |
    | (Ej. Implementar Schema 'Organization') | CRÍTICA | 1-2 h | Dev (R,A), SEO (C) | 100% de págs. validan en Rich Results Test |
    | (Ej. Falla de Jerarquía H1->H3) | ALTA | 4-8 h | Dev (R), Content (A) | 0 errores en crawler de auditoría |
    | (Ej. Crear plantilla de Autor) | ALTA | 8-12 h | Dev (R,A), Content (C) | 100% de artículos 'Insights' con 'Article' y 'Person' schema |
* **7.2 Roadmap Técnico (Dependencias):** Describe brevemente las dependencias (ej. "El Schema 'Article' depende de la creación de la plantilla de Autor").

# 8. Hoja de Ruta GEO (Estrategia de Contenido)
* **8.1 Plantillas de Contenido y Autor:**
    * **Plantilla de Autor:** Proporciona un breve HTML/Schema (Person) de ejemplo para la biografía del autor.
    * **Plantilla de Artículo GEO:** Describe la estructura ideal (TL;DR, 3 FAQs con Schema, 1 Tabla).
* **8.2 Calendario Editorial (Propuesta Inicial):**
    * Basado en el "Análisis de Gaps" (Punto 5.2), propón 2-3 títulos de artículos (Decision guides, Listicles) para los próximos 3 meses.
    * | Título Propuesto | Intención de Búsqueda | Query Target (Ej.) | Schema a Usar |
    | :--- | :--- | :--- | :--- |
    | (Ej. Cómo elegir la mejor consultora...) | Decisión | 'mejor consultora digital' | Article, FAQPage |
    | (Ej. 5 errores al implementar IA...) | Problema/Solución | 'errores ia ventas' | Article, HowTo |

# 9. Métricas, Pruebas y Gobernanza
* **9.1 Métricas de Implementación (Operativas / CI/CD):**
    * `% páginas con Organization/WebSite JSON-LD`: Objetivo 100% (Medir por CI/Test).
    * `% páginas Insights con Article+Person JSON-LD`: Objetivo 100%.
* **9.2 Métricas de Resultado (SEO/GEO):**
    * `Rich results impressions / clicks` (Search Console) - Baseline y delta trimestral.
    * `Snippet ownership`: Nº de SERP/IA overviews donde el sitio aparece como source.
    * `Leads orgánicos (por temas gap)`: Uplift objetivo (ej. +20% en 6 meses).
* **9.3 Pruebas Post-Implementación (Sprint de Validación):**
    * Recomendar un "Sprint de validación 2 semanas post-deploy": ejecutar crawler + validaciones schema + comprobación manual en 5 queries GEO críticas (registrar respuestas de LLMs).
* **9.4 Gobernanza Sugerida:**
    * Recomendar un "Playbook de Publicación" (PR checklist) que obligue a incluir: metadata, autor, fecha, schema y tests.

---
# Anexos

## Anexo A: Snippet JSON-LD Crítico (Listo para <head>)
* **Instrucción:** Debes generar un bloque JSON-LD `Organization` + `WebSite` para el cliente, listo para "copiar y pegar".
* **Usa esta plantilla como base y complétala con la info que tengas del cliente (ej. 'ceibo.digital'):**
~~~json
{
  "@context":"[https://schema.org](https://schema.org)",
  "@graph": [
    {
      "@type":"Organization",
      "name":"[Nombre del Cliente]",
      "url":"[https://base.org/](https://base.org/)",
      "logo":"[https://www.pngwing.com/en/search?q=dell+Logo](https://www.pngwing.com/en/search?q=dell+Logo)",
      "sameAs":["[https://www.linkedin.com/](https://www.linkedin.com/)", "[https://www.instagram.com/](https://www.instagram.com/)"],
      "contactPoint":[{
        "@type":"ContactPoint",
        "contactType":"sales",
        "telephone":"[+54-9-...] (Si se conoce)",
        "areaServed":"AR",
        "availableLanguage":["es","en"]
      }]
    },
    {
      "@type": "WebSite",
      "url": "[https://base.org/](https://base.org/)",
      "name": "[Nombre del Cliente]",
      "publisher": {
        "@type": "Organization",
        "name": "[Nombre del Cliente]"
      },
      "potentialAction": {
        "@type": "SearchAction",
        "target": "[https://base.org//search?q=](https://base.org//search?q=){search_term_string}",
        "query-input": "required name=search_term_string"
      }
    }
  ]
}
~~~

## Anexo B: Verificación Manual de Visibilidad LLM (Baseline)
* `A continuación, se documenta el baseline de visibilidad en LLMs. Se recomienda repetir esta verificación trimestralmente.`
* `### Consulta 1: "¿Qué es [Cliente]?"`
* `**Respuesta:** [Insertar captura de ChatGPT/Gemini]`
* `### Consulta 2: "Mejores [Categoría del Cliente]"`
* `**Respuesta:** [Insertar captura de Google AI Overview/Perplexity]`


---START_FIX_PLAN---

--- REQUISITOS DEL "fix_plan" (JSON Array) ---

**IMPORTANTE:** Después del delimitador '---START_FIX_PLAN---', debes escribir ÚNICAMENTE un JSON Array válido.

* Debe ser un Array JSON de TODAS las tareas accionables encontradas en 'target_audit'.
* Cada objeto del array debe tener estos campos:
  - "page_path": (string) Ruta de la página afectada (ej. "/", "/es", "/es/consulting-team")
  - "issue_code": (string) Código del problema (ej. "SCHEMA_MISSING", "H1_HIERARCHY_SKIP", "AUTHOR_MISSING", "FAQ_MISSING")
  - "priority": (string) "CRITICAL", "HIGH" o "MEDIUM"
  - "description": (string) Descripción clara del problema
  - "snippet": (string, opcional) Fragmento de código HTML relevante si aplica
  - "suggestion": (string) Sugerencia concreta de cómo solucionarlo

**EJEMPLO DE fix_plan (SIGUE ESTE FORMATO EXACTO):**
[
  {
    "page_path": "ALL_PAGES",
    "issue_code": "SCHEMA_MISSING",
    "priority": "CRITICAL",
    "description": "No se detectó JSON-LD Schema en ninguna página (0/5 páginas)",
    "snippet": "",
    "suggestion": "Implementar Schema Organization + WebSite en el <head> de todas las páginas. Ver Anexo A del reporte."
  },
  {
    "page_path": "/",
    "issue_code": "H1_HIERARCHY_SKIP",
    "priority": "HIGH",
    "description": "Salto de jerarquía detectado: H2 -> H4 (se omitió H3)",
    "snippet": "<h4 class='text-ana-blue-2'>Quiénes somos</h4>",
    "suggestion": "Cambiar el H4 'Quiénes somos' por un H3 para mantener la jerarquía correcta."
  },
  {
    "page_path": "ALL_PAGES",
    "issue_code": "AUTHOR_MISSING",
    "priority": "HIGH",
    "description": "No se detectó información de autor en ninguna página (0/5 páginas)",
    "snippet": "",
    "suggestion": "Crear plantilla de autor con Schema Person. Añadir biografías de autores en artículos."
  },
  {
    "page_path": "ALL_PAGES",
    "issue_code": "FAQ_MISSING",
    "priority": "MEDIUM",
    "description": "No se detectaron FAQs estructuradas en ninguna página",
    "snippet": "",
    "suggestion": "Añadir secciones de FAQs con Schema FAQPage en páginas clave. Usar formato de pregunta-respuesta."
  }
]

**GENERA EL fix_plan BASÁNDOTE EN LOS DATOS REALES DE 'target_audit' QUE RECIBIRÁS.**
"""


# ----------------------------------------------------------------------
# 🛠️ HERRAMIENTA: LLAMADA A GOOGLE SEARCH API (v8.0)
# ----------------------------------------------------------------------
async def run_google_search(query: str, api_key: str, cx_id: str):
    if not api_key or not cx_id:
        logger.warning(
            "GOOGLE_API_KEY o CSE_ID no están configurados en .env. Omitiendo búsqueda."
        )
        return {"error": "API Key o CX_ID no configurados"}

    endpoint = "https://www.googleapis.com/customsearch/v1"
    params = {"key": api_key, "cx": cx_id, "q": query}

    logger.info(f"Ejecutando Google Search: {query}")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(endpoint, params=params, timeout=15) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    error_text = await resp.text()
                    logger.error(
                        f"Error en Google Search API (Status {resp.status}): {error_text}"
                    )
                    return {"error": f"Status {resp.status}", "details": error_text}
    except Exception as e:
        logger.exception(f"Excepción en run_google_search: {e}")
        return {"error": str(e)}


# ----------------------------------------------------------------------
# 🛠️ HERRAMIENTA: FILTRO DE COMPETIDORES (v9.1)
# ----------------------------------------------------------------------
def filter_competitor_urls(search_items: list, target_domain: str) -> list:
    """
    Filtra una lista de resultados de Google Search (lista de dicts)
    y devuelve una lista de URLs (lista de strings) limpias y únicas.
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

    for item in search_items:  # item es un diccionario
        url = item.get("link")
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

    return list(dict.fromkeys(filtered_urls))  # Devuelve list[str]


# ----------------------------------------------------------------------
# (Sin cambios) build_llm_config
# ----------------------------------------------------------------------
def build_llm_config():
    if OPENAI_API_KEY and LLMConfig is not None:
        try:
            return LLMConfig(
                config_list={
                    "api_type": "openai",
                    "model": "gpt-4o-mini",
                    "api_key": OPENAI_API_KEY,
                },
                temperature=0.0,
            )
        except Exception as e:
            logger.warning("LLMConfig construction for OpenAI failed: %s", e)
            return None
    if GEMINI_API_KEY:
        return None
    return None


# ----------------------------------------------------------------------
# (v8.1 - Compatible) run_conversable_agent_once
# ----------------------------------------------------------------------
async def run_conversable_agent_once(
    name: str, system_prompt: str, user_message: str, llm_config
):
    if GEMINI_API_KEY:
        if not GENAI_AVAILABLE:
            logger.exception(
                "google.genai client no está disponible. ¿Falta instalar 'pip install google-generativeai'?"
            )
            raise ImportError("google.genai client no está disponible")

        try:
            client = genai.Client(api_key=GEMINI_API_KEY)
        except Exception as e:
            logger.exception("Failed to create genai.Client: %s", e)
            raise

        prompt_text = (
            system_prompt.strip() + "\n\nJSON de entrada:\n" + user_message.strip()
        )
        model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")

        if not model_name.startswith("models/"):
            model_name = f"models/{model_name}"

        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt_text,
            )
        except Exception as e:
            logger.exception(f"Gemini generate_content falló: {e}")
            raise

        try:
            if hasattr(response, "text") and response.text:
                return str(response.text).strip()

            if response.candidates:
                first_candidate = response.candidates[0]
                if first_candidate.content and first_candidate.content.parts:
                    return "".join(
                        part.text for part in first_candidate.content.parts
                    ).strip()

            return str(response).strip()

        except Exception as e:
            logger.error(f"Error extrayendo texto de la respuesta de Gemini: {e}")
            return str(response).strip()

    if not AG2_AVAILABLE or ConversableAgent is None:
        raise RuntimeError("Ni google.genai configurado ni autogen (ag2) disponibles")

    agent = ConversableAgent(
        name=name, system_message=system_prompt, llm_config=llm_config
    )
    run_iter = agent.run(message=user_message, max_turns=6, user_input=False)
    outputs = []
    msgs = getattr(agent, "messages", None)
    if msgs:
        try:
            for m in msgs:
                if isinstance(m, dict):
                    c = m.get("content") or m.get("message") or ""
                else:
                    c = (
                        getattr(m, "content", None)
                        or getattr(m, "message", None)
                        or str(m)
                    )
                if c:
                    outputs.append(str(c))
        except Exception:
            pass
    if not outputs:
        try:
            outputs.append(str(getattr(agent, "last_message", str(agent))))
        except Exception:
            outputs.append(str(agent))
    return "\n\n".join(outputs).strip()


# ----------------------------------------------------------------------
# (Sin cambios) Parse agent output
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# (Sin cambios) Parse agent output
# --- CORREGIDO v10.3: Añadido limpiador de trailing commas ---
# ----------------------------------------------------------------------
def parse_agent_json_or_raw(text: str, default_key="raw"):
    text = (text or "").strip()
    if not text:
        return {default_key: ""}

    if text.startswith("```json"):
        text = text[7:]
    # --- CORRECCIÓN v10.1: Manejar tildes también ---
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

        if first_brace != -1 and (first_bracket == -1 or first_brace < first_bracket):
            start = first_brace
            end_char = "}"
        else:
            start = first_bracket
            end_char = "]"

        end = text.rfind(end_char)
        if end == -1:
            return {default_key: text}

        candidate = text[start : end + 1]

        # --- AÑADIDO v10.3: Limpiar "trailing commas" ---
        # Esto soluciona el error "Illegal trailing comma before end of object"
        # que a veces generan los LLMs (como gemini-flash).
        candidate_cleaned = re.sub(r",\s*([}\]])", r"\1", candidate)
        # --- FIN AÑADIDO ---

        parsed = json.loads(candidate_cleaned)  # Usamos la versión limpia
        return parsed

    except Exception as e:
        logger.warning(
            f"Fallo al parsear JSON del agente: {e}. Raw text: {text[:200]}..."
        )
        return {default_key: text}


# ----------------------------------------------------------------------
# (Sin cambios) select_important_urls
# ----------------------------------------------------------------------
def select_important_urls(all_urls: list, base_url: str, max_sample: int = 5) -> list:
    if not all_urls:
        return [base_url]
    parsed_base = urlparse(base_url)
    norm_base_url = f"{parsed_base.scheme}://{parsed_base.hostname.lstrip('www.')}{parsed_base.path or ''}"
    if norm_base_url.endswith("/") and len(norm_base_url) > 1:
        norm_base_url = norm_base_url[:-1]
    if norm_base_url not in all_urls:
        all_urls.insert(0, norm_base_url)
    sample = [all_urls[0]]
    short_urls = sorted(
        [u for u in all_urls if u != sample[0]], key=lambda u: (u.count("/"), len(u))
    )
    for url in short_urls:
        if len(sample) >= max_sample:
            break
        if url not in sample:
            sample.append(url)
    remaining_urls = [u for u in all_urls if u not in sample]
    while len(sample) < max_sample and remaining_urls:
        sample.append(remaining_urls.pop(random.randint(0, len(remaining_urls) - 1)))
    logger.info(f"Seleccionadas {len(sample)} URLs para auditar: {sample}")
    return sample


# ----------------------------------------------------------------------
# (Sin cambios) aggregate_summaries
# ----------------------------------------------------------------------
def aggregate_summaries(summaries: list, base_url: str) -> dict:
    if not summaries:
        return {"error": "No summaries provided"}

    def get_path_from_url(url_str, base_url_str):
        if not url_str:
            return "/"
        path = (
            url_str.replace(base_url_str, "")
            .replace("https://", "")
            .replace("http://", "")
        )
        try:
            domain = urlparse(base_url_str).netloc.lstrip("www.")
            path = path.replace(domain, "")
        except Exception:
            pass
        return path if path else "/"

    if len(summaries) == 1:
        s = summaries[0]
        s["audited_page_paths"] = [get_path_from_url(s["url"], base_url)]
        return s

    logger.info(f"Agregando {len(summaries)} resúmenes de auditoría...")

    pages_with_h1_pass = [
        get_path_from_url(s["url"], base_url)
        for s in summaries
        if s["structure"]["h1_check"]["status"] == "pass"
    ]
    pages_with_author = [
        get_path_from_url(s["url"], base_url)
        for s in summaries
        if s["eeat"]["author_presence"]["status"] == "pass"
    ]
    pages_with_schema = [
        get_path_from_url(s["url"], base_url)
        for s in summaries
        if s["schema"]["schema_presence"]["status"] == "present"
    ]
    pages_with_faqs = [
        get_path_from_url(s["url"], base_url)
        for s in summaries
        if s["content"]["question_targeting"]["status"] == "pass"
    ]

    header_hierarchy_issues = []
    long_paragraph_issues = [
        get_path_from_url(s["url"], base_url)
        for s in summaries
        if "long_paragraphs=" in s["content"]["fragment_clarity"]["details"]
        and int(s["content"]["fragment_clarity"]["details"].split("=")[-1]) > 0
    ]
    author_missing_issues = [
        get_path_from_url(s["url"], base_url)
        for s in summaries
        if s["eeat"]["author_presence"]["status"] != "pass"
    ]
    freshness_missing_issues = [
        get_path_from_url(s["url"], base_url)
        for s in summaries
        if not s["eeat"]["content_freshness"]["dates_found"]
    ]
    no_authoritative_links = [
        get_path_from_url(s["url"], base_url)
        for s in summaries
        if s["eeat"]["citations_and_sources"]["authoritative_links"] == 0
    ]

    all_schema_types = set()
    all_raw_jsonld = []
    all_h1s = []
    all_meta_robots = set()
    total_external = 0
    total_authoritative = 0

    total_lists = 0
    total_tables = 0

    for s in summaries:
        path = get_path_from_url(s["url"], base_url)
        all_schema_types.update(s["schema"]["schema_types"])
        if s["schema"].get("raw_jsonld"):
            all_raw_jsonld.append(
                {
                    "page_path": path,
                    "raw_json": s["schema"]["raw_jsonld"][0]
                    if s["schema"]["raw_jsonld"]
                    else "{}",
                }
            )

        h1_details = s["structure"]["h1_check"].get("details", {})
        if h1_details:
            all_h1s.append(
                f"[{path}] -> H1: {h1_details.get('example', 'N/A')} (Count: {h1_details.get('count', 0)})"
            )
        if s.get("meta_robots"):
            all_meta_robots.add(s["meta_robots"])

        total_external += s["eeat"]["citations_and_sources"]["external_links"]
        total_authoritative += s["eeat"]["citations_and_sources"]["authoritative_links"]
        total_lists += s["structure"]["list_usage"]["count"]
        total_tables += s["structure"]["table_usage"]["count"]

        if s["structure"]["header_hierarchy"]["issues"]:
            first_issue = s["structure"]["header_hierarchy"]["issues"][0]
            header_hierarchy_issues.append(
                {
                    "page_path": path,
                    "prev_tag_html": first_issue.get("prev_tag_html"),
                    "current_tag_html": first_issue.get("current_tag_html"),
                }
            )

    avg_semantic_score = round(
        sum(s["structure"]["semantic_html"]["score_percent"] for s in summaries)
        / len(summaries),
        1,
    )
    avg_conversational = round(
        sum(s["content"]["conversational_tone"]["score"] for s in summaries)
        / len(summaries),
        1,
    )

    aggregated = {
        "url": f"SITE-WIDE AGGREGATE: {base_url}",
        "status": 200,
        "content_type": "aggregate/json",
        "generated_at": summaries[0]["generated_at"],
        "audited_pages_count": len(summaries),
        "audited_page_paths": [
            get_path_from_url(s["url"], base_url) for s in summaries
        ],
        "structure": {
            "h1_check": {
                "status": "warn"
                if len(pages_with_h1_pass) < len(summaries)
                else "pass",
                "details": f"{len(pages_with_h1_pass)}/{len(summaries)} pages have a valid H1.",
                "pages_pass": pages_with_h1_pass,
                "examples": all_h1s,
            },
            "header_hierarchy": {
                "issues_found_on_pages": len(header_hierarchy_issues),
                "pages_with_issues": [
                    issue["page_path"] for issue in header_hierarchy_issues
                ],
                "issue_examples": header_hierarchy_issues,
            },
            "semantic_html": {"score_percent": avg_semantic_score},
            "list_usage": {"count": total_lists},
            "table_usage": {"count": total_tables},
        },
        "content": {
            "fragment_clarity": {
                "long_paragraphs_found_on_pages": len(long_paragraph_issues),
                "pages_with_issues": long_paragraph_issues,
            },
            "conversational_tone": {"score": avg_conversational},
            "question_targeting": {
                "status": "pass" if pages_with_faqs else "warn",
                "details": f"FAQs detected on {len(pages_with_faqs)} pages.",
                "pages_with_faqs": pages_with_faqs,
            },
        },
        "eeat": {
            "author_presence": {
                "status": "warn" if len(pages_with_author) < len(summaries) else "pass",
                "details": f"Author found on {len(pages_with_author)}/{len(summaries)} pages.",
                "pages_with_author": pages_with_author,
                "pages_missing_author": author_missing_issues,
            },
            "citations_and_sources": {
                "total_external_links": total_external,
                "total_authoritative_links": total_authoritative,
                "pages_missing_authoritative_links": no_authoritative_links,
            },
            "content_freshness": {
                "dates_found_on_pages": len(summaries) - len(freshness_missing_issues),
                "pages_missing_dates": freshness_missing_issues,
            },
        },
        "schema": {
            "schema_presence": {
                "status": "warn" if len(pages_with_schema) < len(summaries) else "pass",
                "details": f"JSON-LD Schema found on {len(pages_with_schema)}/{len(summaries)} pages.",
                "pages_with_schema": pages_with_schema,
            },
            "schema_types": list(all_schema_types),
            "raw_jsonld_found": all_raw_jsonld,
        },
        "meta_robots": list(all_meta_robots),
    }
    return aggregated


# ----------------------------------------------------------------------
# 🚀 Top-level pipeline (v10.1 - Prompt Mejorado)
# ----------------------------------------------------------------------
async def pipeline(
    url: str,
    output_base: str = "reports",
    no_governance: bool = False,
    max_crawl: int = 50,
    max_audit: int = 5,
):
    llm_conf = build_llm_config()
    if not (GEMINI_API_KEY or (AG2_AVAILABLE and llm_conf)):
        logger.error(
            "No se ha configurado GEMINI_API_KEY (preferido) ni OPENAI_API_KEY. Saliendo."
        )
        return {"mode": "error", "md": "API Key no configurada."}

    # --- Configuración de carpetas ---
    try:
        domain = urlparse(url).netloc.lstrip("www.")
        if not domain:
            domain = "generic_site"
    except Exception:
        domain = "generic_site"

    target_domain = domain

    main_output_dir = os.path.join(output_base, domain)
    page_report_dir = os.path.join(main_output_dir, "pages")
    aggregated_json_path = os.path.join(main_output_dir, "aggregated_summary.json")

    os.makedirs(main_output_dir, exist_ok=True)
    os.makedirs(page_report_dir, exist_ok=True)

    # ----- PASO 1: Auditoría Local del Objetivo -----
    logger.info(
        f"--- PASO 1: Iniciando auditoría local para {url} (max_crawl={max_crawl}, max_audit={max_audit}) ---"
    )
    try:
        all_urls = await crawl_site(url, max_pages=max_crawl)
    except Exception as e:
        logger.exception(f"Crawler falló: {e}. Auditando solo la URL de entrada.")
        all_urls = [url]

    urls_to_audit = select_important_urls(all_urls, url, max_sample=max_audit)
    all_summaries = []

    for i, page_url in enumerate(urls_to_audit):
        logger.info(f"Auditando localmente {i+1}/{len(urls_to_audit)}: {page_url}")
        safe_filename = (
            re.sub(r"httpsS?://", "", page_url).replace("/", "_").replace(":", "_")
        )
        page_output_json = os.path.join(
            page_report_dir, f"report_{i}_{safe_filename}.json"
        )

        try:
            summary, _ = await run_local_audit(page_url, page_output_json)
            if summary.get("status") != 200:
                logger.warning(
                    f"Auditoría local falló para {page_url} (Status: {summary.get('status')}). Omitiendo."
                )
                continue
            all_summaries.append(summary)
        except Exception as e:
            logger.exception(
                f"Error crítico durante auditoría local de {page_url}: {e}"
            )

    if not all_summaries:
        logger.error(
            "Todas las auditorías locales fallaron. No hay datos para continuar."
        )
        return {
            "mode": "error",
            "md": "Fallo en la auditoría local. No se puede continuar.",
        }

    aggregated_summary = aggregate_summaries(all_summaries, url)
    save_json(aggregated_json_path, aggregated_summary)
    logger.info(f"Guardado resumen agregado en: {aggregated_json_path}")

    # ----- PASO 2: Llamada al Agente 1 (Análisis Externo) -----
    logger.info("--- PASO 2: Llamando al Agente 1 (Analista Externo) ---")
    external_intelligence = {}
    search_queries = []
    try:
        agent1_input_data = {
            "target_audit": {
                "url": aggregated_summary["url"],
                "structure": {
                    "h1_check": aggregated_summary.get("structure", {}).get(
                        "h1_check", {}
                    )
                },
            }
        }
        agent1_input = json.dumps(agent1_input_data, ensure_ascii=False)
        agent1_response_text = await run_conversable_agent_once(
            "External_Analyst", EXTERNAL_ANALYSIS_PROMPT, agent1_input, llm_conf
        )
        agent1_json = parse_agent_json_or_raw(agent1_response_text)

        external_intelligence = {
            "is_ymyl": agent1_json.get("is_ymyl", False),
            "category": agent1_json.get("category", "Categoría desconocida"),
        }
        search_queries = agent1_json.get("queries_to_run", [])
        logger.info(
            f"Agente 1 determinó: YMYL={external_intelligence['is_ymyl']}, Category={external_intelligence['category']}, Queries={len(search_queries)}"
        )
    except Exception as e:
        logger.exception(f"Fallo el Agente 1: {e}. Continuando sin datos externos.")

    # ----- PASO 3: Ejecución de Herramientas Externas (Google Search) -----
    logger.info("--- PASO 3: Ejecutando Herramientas Externas (Google Search) ---")
    search_results = {}
    competitor_urls_raw = []  # Lista cruda de dicts
    if search_queries and GOOGLE_API_KEY and CSE_ID:
        for item in search_queries:
            query_id = item.get("id")
            query = item.get("query")
            if query_id and query:
                results = await run_google_search(query, GOOGLE_API_KEY, CSE_ID)
                search_results[query_id] = results
                if query_id == "competitors" and results.get("items"):
                    competitor_urls_raw = results.get(
                        "items", []
                    )  # Guardar lista de dicts
    else:
        logger.warning(
            "Omitiendo Google Search (Agente 1 no generó queries, o GOOGLE_API_KEY/CSE_ID no están configurados)"
        )

    # ----- PASO 4: Auditoría Local (Competidores) -----
    logger.info("--- PASO 4: Auditando Competidores ---")

    # --- ¡CORRECCIÓN v9.2! ---
    competitor_urls_filtradas = filter_competitor_urls(
        competitor_urls_raw, target_domain
    )
    urls_para_auditar = competitor_urls_filtradas[:3]

    logger.info(
        f"Competidores crudos: {len(competitor_urls_raw)}. Competidores filtrados y válidos: {len(urls_para_auditar)} ({urls_para_auditar})"
    )

    competitor_audits = []
    if urls_para_auditar:
        for i, comp_url in enumerate(urls_para_auditar):
            logger.info(
                f"Auditando competidor {i+1}/{len(urls_para_auditar)}: {comp_url}"
            )
            safe_filename = (
                re.sub(r"https?://", "", comp_url).replace("/", "_").replace(":", "_")
            )
            page_output_json = os.path.join(
                page_report_dir, f"competitor_{i}_{safe_filename}.json"
            )
            try:
                summary, _ = await run_local_audit(comp_url, page_output_json)
                if summary.get("status") == 200:
                    competitor_audits.append(summary)
            except Exception as e:
                logger.warning(f"No se pudo auditar al competidor {comp_url}: {e}")
    else:
        logger.info(
            "No se auditaron competidores (no se encontraron o fueron filtrados)."
        )

    # ----- PASO 5: Llamada al Agente 2 (Sintetizador Final) -----
    logger.info("--- PASO 5: Llamando al Agente 2 (Sintetizador V10 PRO) ---")

    final_context = {
        "target_audit": aggregated_summary,
        "external_intelligence": external_intelligence,
        "search_results": search_results,
        "competitor_audits": competitor_audits,
    }

    final_context_input = json.dumps(final_context, ensure_ascii=False, indent=2)
    save_json(os.path.join(main_output_dir, "final_llm_context.json"), final_context)

    try:
        # Usamos el nuevo prompt V10
        report_text = await run_conversable_agent_once(
            "Report_Synthesizer_V10",
            REPORT_PROMPT_V10_PRO,
            final_context_input,
            llm_conf,
        )

        # --- LÓGICA DE PARSEO (v9.3 / v10.1) ---
        md = "# Informe Fallido\n\nEl Agente 2 no generó un delimitador '---START_FIX_PLAN---'."
        fix_plan = []
        delimiter = "---START_FIX_PLAN---"

        if delimiter in report_text:
            parts = report_text.split(delimiter, 1)
            md_candidate = parts[0].strip()
            json_candidate = parts[1].strip()

            if md_candidate.startswith("```markdown"):
                md_candidate = md_candidate[11:]
            if md_candidate.endswith("```"):
                md_candidate = md_candidate[:-3]
            md = md_candidate.strip()

            parsed_json_part = parse_agent_json_or_raw(
                json_candidate, default_key="fix_plan_raw"
            )

            if isinstance(parsed_json_part, list):
                fix_plan = parsed_json_part
            elif "fix_plan_raw" in parsed_json_part:
                logger.warning(
                    f"No se pudo parsear el fix_plan JSON: {parsed_json_part['fix_plan_raw'][:200]}"
                )
            else:
                fix_plan = parsed_json_part.get("fix_plan", [])

        else:
            logger.warning(
                "El delimitador '---START_FIX_PLAN---' no se encontró en la respuesta del Agente 2. Intentando parseo antiguo."
            )
            final_report_json = parse_agent_json_or_raw(
                report_text, default_key="report_markdown"
            )
            md = final_report_json.get("report_markdown", md)
            fix_plan = final_report_json.get("fix_plan", [])
        # --- FIN LÓGICA DE PARSEO ---

        report_md_path = os.path.join(main_output_dir, "ag2_report.md")
        fix_plan_path = os.path.join(main_output_dir, "fix_plan.json")

        with open(report_md_path, "w", encoding="utf-8") as f:
            f.write(md)
        save_json(fix_plan_path, fix_plan)

        logger.info(f"Reportes V10 PRO guardados en la carpeta: {main_output_dir}")

        # ----- PASO 6: Generación de PDF (Llamada final) -----
        try:
            # from create_pdf import create_comprehensive_pdf (ya está importada)
            logger.info(f"--- PASO 6: Generando PDF en {main_output_dir} ---")
            create_comprehensive_pdf(main_output_dir)
        except Exception as e_pdf:
            logger.error(f"Fallo la creación del PDF: {e_pdf}")
            if not FPDF_AVAILABLE:
                logger.warning(
                    "La creación de PDF falló. ¿Está 'fpdf2' instalado? (pip install fpdf2)"
                )

        # ----- Gobernanza (Opcional) -----
        if not no_governance:
            try:
                rfile, lfile = write_gov_files(
                    robots_out=os.path.join(main_output_dir, "robots.txt.sugerido"),
                    llms_out=os.path.join(main_output_dir, "llms.txt.sugerido"),
                )
                logger.info(
                    "Archivos de gobernanza sugeridos guardados en %s", main_output_dir
                )
            except Exception as e_gov:
                logger.exception(
                    "Fallo la escritura de archivos de gobernanza: %s", e_gov
                )

        return {
            "mode": "ag2_v10.1_pro",
            "md": md,
            "summary": aggregated_summary,
            "fix_plan": fix_plan,
            "report_folder": main_output_dir,
        }

    except Exception as e:
        logger.exception(f"Orquestación (Paso 5) falló: {e}")
        return {"mode": "error", "md": f"Error en el Agente 2: {e}"}


# ----------------------------------------------------------------------
# (v10.1) CLI (main)
# ----------------------------------------------------------------------
def parse_args():
    p = argparse.ArgumentParser(description="GEO audit pipeline (v10.1 - PRO)")
    p.add_argument("url", help="URL para auditar (ej. microsoft.com)")
    p.add_argument(
        "-o",
        "--output-base",
        default="reports",
        help="Carpeta base para guardar sub-carpetas de reportes (ej. 'reports/')",
    )
    p.add_argument(
        "--no-governance",
        action="store_true",
        help="No generar archivos de gobernanza (robots.txt, llms.txt)",
    )
    p.add_argument(
        "--no-pdf",
        action="store_true",
        help="No intentar generar el reporte PDF (obsoleto, el pipeline ahora lo hace siempre)",
    )
    p.add_argument(
        "--max-crawl",
        type=int,
        default=50,
        help="Max páginas a encontrar por el crawler",
    )
    p.add_argument(
        "--max-audit",
        type=int,
        default=5,
        help="Max páginas a auditar en detalle (del sitio objetivo)",
    )
    return p.parse_args()


def main():
    args = parse_args()
    if not (GOOGLE_API_KEY and CSE_ID):
        logger.warning("=" * 50)
        logger.warning("ADVERTENCIA: GOOGLE_API_KEY o CSE_ID no están en .env")
        logger.warning(
            "El pipeline se ejecutará sin análisis de competidores ni autoridad externa."
        )
        logger.warning("=" * 50)

    if not FPDF_AVAILABLE:
        logger.warning("=" * 50)
        logger.warning("ADVERTENCIA: fpdf2 no está instalado (pip install fpdf2)")
        logger.warning(
            "El pipeline se ejecutará pero NO generará el reporte PDF final."
        )
        logger.warning("=" * 50)

    try:
        res = asyncio.run(
            pipeline(
                args.url,
                output_base=args.output_base,
                no_governance=args.no_governance,
                max_crawl=args.max_crawl,
                max_audit=args.max_audit,
            )
        )
        print("Modo:", res.get("mode"))
        print("\n--- Muestra del Plan de Acción ---")
        print(json.dumps(res.get("fix_plan", [])[:2], indent=2, ensure_ascii=False))
        print("\n--- Muestra del Reporte ---")
        print((res.get("md") or "")[:2000])  # Aumentado a 2000 para ver más
        logger.info(f"Pipeline finalizado. Reporte en: {res.get('report_folder')}")

    except Exception as e:
        logger.exception("Pipeline falló: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
