#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
content_generator_v2.py - Flujo de Agentes 1-3 (Versión Sólida)
Modificado para usar el endpoint NVIDIA (OpenAI-style client) en lugar de
usar exclusivamente Gemini. La API key del proveedor NVIDIA debe estar en .env
como NV_API_KEY. Si no está disponible, se intenta el flujo previo con GEMINI.
Código en inglés; comentarios en español.
"""

import os
import sys
import json
import argparse
import asyncio
import logging
import aiohttp
import re
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from dotenv import load_dotenv

# --- Dependencias de IA (copiadas de ag2_pipeline.py) ---
try:
    from google import genai
    from google.genai import types

    GENAI_AVAILABLE = True
except Exception as e:
    logging.info("google.genai no está instalado: %s", e)
    GENAI_AVAILABLE = False

# --- Dependencia NV / OpenAI-style (NVIDIA INTEGRATE) ---
try:
    from openai import OpenAI as NVOpenAI

    NV_OPENAI_AVAILABLE = True
except Exception as e:
    logging.info("openai NV client no está instalado: %s", e)
    NV_OPENAI_AVAILABLE = False

# --- IMPORTACIÓN CLAVE (reciclando tu código) ---
try:
    from crawler import crawl_site
except ImportError:
    print("Error: No se pudo encontrar 'crawler.py'.")
    print(
        "Asegúrate de que 'content_generator_v2.py' esté en la misma carpeta que 'crawler.py'."
    )
    sys.exit(1)
# --------------------------------------------------

# --- Cargar .env (copiado de ag2_pipeline.py) ---
load_dotenv()
# Google / CSE
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
CSE_ID = os.getenv("CSE_ID")

# NVIDIA / OpenAI-style integration
NV_API_KEY = os.getenv(
    "NV_API_KEY"
)  # <<--- la API key para el endpoint tipo OpenAI (NVIDIA)
NV_BASE_URL = os.getenv("NV_BASE_URL", "https://integrate.api.nvidia.com/v1")
NV_MODEL = os.getenv("NV_MODEL", "moonshotai/kimi-k2-instruct-0905")
NV_MAX_TOKENS = int(os.getenv("NV_MAX_TOKENS", "4096"))

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("ContentGeneratorV2")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
    " Chrome/91.0.4472.124 Safari/537.36"
}

# --- utilidades de scraping / crawling ---


async def fetch_and_parse(session, url: str) -> dict:
    """
    Función mejorada (inspirada en audit_local.py)
    para descargar y extraer H1 y texto principal de una URL.
    Devuelve un dict para un mejor contexto.
    """
    try:
        async with session.get(url, timeout=15) as resp:
            if resp.status != 200:
                logger.warning(f"Error {resp.status} al fetchear {url}")
                return {"url": url, "h1": "Error de Acceso", "corpus": ""}

            html = await resp.text(errors="ignore")
            soup = BeautifulSoup(html, "html.parser")

            h1 = soup.find("h1")
            h1_text = h1.get_text(strip=True) if h1 else ""

            main_content = soup.find("main")
            if not main_content:
                main_content = soup.find("article")
            if not main_content:
                main_content = soup.find("body")

            text_corpus = " ".join(
                main_content.get_text(separator=" ", strip=True).split()
            )

            return {
                "url": url,
                "h1": h1_text,
                "corpus": text_corpus[:2500],  # Limitar corpus por post
            }

    except Exception as e:
        logger.error(f"Error en fetch_and_parse({url}): {e}")
        return {"url": url, "h1": "Error de Scrapeo", "corpus": str(e)}


def filter_blog_urls(all_urls: list, base_url: str, max_sample=5) -> list:
    """
    (NUEVO) Filtra la lista del crawler para encontrar los
    artículos de blog más probables.
    """
    blog_indicators = [
        "/blog",
        "/post",
        "/news",
        "/insights",
        "/articulos",
        "/novedades",
    ]
    blog_urls = []
    other_urls = []

    base_domain = urlparse(base_url).netloc

    for url in all_urls:
        try:
            parsed = urlparse(url)
            # Asegurarse que es del mismo dominio (ignorar subdominios por simplicidad)
            if parsed.netloc.endswith(base_domain):
                path = parsed.path.lower()
                if any(indicator in path for indicator in blog_indicators):
                    blog_urls.append(url)
                else:
                    other_urls.append(url)
        except Exception:
            continue

    # Priorizar blog URLs, pero fall back a otras URLs si no se encuentran
    sample = list(dict.fromkeys(blog_urls))[:max_sample]

    remaining_needed = max_sample - len(sample)
    if remaining_needed > 0:
        logger.warning(
            f"No se encontraron suficientes posts. Añadiendo {remaining_needed} páginas generales."
        )
        # Sort by path depth, simple pages son menos útiles
        other_urls.sort(key=lambda u: u.count("/"), reverse=True)
        for url in other_urls:
            if (
                url not in sample
                and url != base_url
                and not url.endswith((".png", ".jpg", ".pdf"))
            ):
                sample.append(url)
                if len(sample) >= max_sample:
                    break

    logger.info(f"Seleccionadas {len(sample)} URLs para análisis de contexto: {sample}")
    return sample


async def run_google_search(query: str, api_key: str, cx_id: str, num=5):
    """
    Función de búsqueda (copiada de ag2_pipeline.py).
    """
    if not api_key or not cx_id:
        logger.warning("GOOGLE_API_KEY o CSE_ID no configurados. Omitiendo búsqueda.")
        return {"error": "API Key o CX_ID no configurados"}

    endpoint = "https://www.googleapis.com/customsearch/v1"
    params = {"key": api_key, "cx": cx_id, "q": query, "num": num}

    logger.info(f"Ejecutando Google Search: {query}")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(endpoint, params=params, timeout=15) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    simplified_items = []
                    if "items" in data:
                        for item in data["items"]:
                            simplified_items.append(
                                {
                                    "title": item.get("title"),
                                    "link": item.get("link"),
                                    "snippet": item.get("snippet"),
                                }
                            )
                    return {"query": query, "items": simplified_items}
                else:
                    error_text = await resp.text()
                    logger.error(
                        f"Error en Google Search API (Status {resp.status}): {error_text}"
                    )
                    return {"error": f"Status {resp.status}", "details": error_text}
    except Exception as e:
        logger.exception(f"Excepción en run_google_search: {e}")
        return {"error": str(e)}


# --- 🔴 INICIO DE LA MODIFICACIÓN: run_agent_llm usando NV (NVIDIA / OpenAI-style) 🔴 ---


async def run_agent_llm(system_prompt: str, user_message: str, use_json_output=True):
    """
    Función de LLM (v2.2 - Compatible con el endpoint OpenAI-style de NVIDIA).
    Prioriza NV_API_KEY + NVOpenAI si están disponibles. Si no, intenta el
    cliente google.genai (Gemini) como fallback.
    Devuelve texto (string) con la respuesta completa.
    """
    prompt_text = system_prompt.strip() + "\n\n" + user_message.strip()

    # --- Try NVIDIA / OpenAI-style client first ---
    if NV_API_KEY and NV_OPENAI_AVAILABLE:
        try:
            logger.info(f"Llamando NV/OpenAI-style client (model={NV_MODEL})...")
            nv_client = NVOpenAI(base_url=NV_BASE_URL, api_key=NV_API_KEY)

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ]

            completion = nv_client.chat.completions.create(
                model=NV_MODEL,
                messages=messages,
                temperature=0.1,
                top_p=0.9,
                max_tokens=NV_MAX_TOKENS,
            )

            # Extracción robusta del contenido
            content = None
            try:
                # Forma esperada: completion.choices[0].message.content
                content = completion.choices[0].message.content
            except Exception:
                try:
                    # Alternativa: completion.choices[0].message['content']
                    content = completion.choices[0].message.get("content")
                except Exception:
                    try:
                        # Algunos SDKs devuelven choices[0].text
                        content = completion.choices[0].text
                    except Exception:
                        content = None

            if isinstance(content, dict) and "parts" in content:
                # A veces viene dividido por partes
                parts = content.get("parts", [])
                content = "".join(p.get("text", "") for p in parts)

            if content is None:
                # Como fallback, stringify the whole response
                return str(completion).strip()

            return str(content).strip()

        except Exception as e:
            logger.exception(f"NV/OpenAI-style client falló: {e}")
            # continuar al fallback si existe

    # --- Fallback: google.genai (Gemini) si está disponible ---
    if GEMINI_API_KEY and GENAI_AVAILABLE:
        try:
            logger.info("Usando google.genai (Gemini) como fallback...")
            client = genai.Client(api_key=GEMINI_API_KEY)

            # Mantener compatibilidad con implementaciones previas que usan 'config'
            model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")
            if not model_name.startswith("models/"):
                model_name = f"models/{model_name}"

            config = types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json"
                if use_json_output
                else "text/plain",
            )

            response = client.models.generate_content(
                model=model_name, contents=prompt_text, config=config
            )

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
            logger.exception(f"Gemini generate_content falló: {e}")
            raise

    # --- Si no hay cliente disponible ---
    raise ImportError(
        "No hay cliente LLM disponible. Configura NV_API_KEY (y la librería 'openai') o GEMINI_API_KEY (y 'google-genai')."
    )


# --- 🔴 FIN DE LA MODIFICACIÓN 🔴 ---


def parse_json_from_llm(text: str):
    """
    Función de parseo (inspirada en parse_agent_json_or_raw)
    """
    text = (text or "").strip()
    # Añadido soporte para tildes (```) en caso de que el LLM las use
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    try:
        return json.loads(text)
    except Exception as e:
        logger.error(f"Fallo al parsear JSON del LLM: {e}\nTexto: {text[:500]}")
        return None


# --- Prompts (sin cambios) ---
AGENT_0_DISCOVERY_PROMPT = """
Actúa como un Analista de Negocios y Estratega de Contenidos (Agente 0 v2).
Te daré el texto crudo de la página de inicio (Homepage) y un análisis
de los títulos (H1) y corpus de sus artículos de blog.

Tu tarea es devolver un JSON con tres claves:
1.  "company_description": Una descripción concisa (1-2 frases) de lo que
    hace la empresa, basado en la Homepage.
2.  "main_topic": El "tema principal" o categoría de la industria
    (ej. "Software de IA para Finanzas", "Agencia de Marketing Digital").
3.  "target_audience": El público objetivo inferido, basado en el tono
    y los temas de los artículos del blog (ej. "Directores de Marketing B2B",
    "Desarrolladores de software", "Inversores de AgTech").

Asegúrate de que el 'target_audience' sea específico y accionable.
Tu respuesta DEBE ser un bloque de código JSON válido y nada más.

Input:
"""

AGENT_1_KEYWORD_PROMPT = """
Actúa como un Estratega SEO experto (Agente 1 del Manual de Producción).
Mi empresa se dirige a: {AUDIENCIA_TARGET}
Mi tema principal es: {TEMA_PRINCIPAL}

Tu tarea es generar un plan de palabras clave completo. Identifica la intención de búsqueda principal (informativa, transaccional, de navegación) para cada grupo.

Genera la siguiente estructura en formato JSON (como en Prompt A1.1):
{{
  "palabra_clave_principal": "[Palabra clave semilla (ej. 'GEO vs SEO')]",
  "intencion_principal": "[Informativa/Transaccional]",
  "cluster_primario": [
    {{ "keyword": "[Keyword primaria 1]", "intencion": "[Intención]" }},
    {{ "keyword": "[Keyword primaria 2]", "intencion": "[Intención]" }}
  ],
  "cluster_long_tail": [
    {{ "keyword": "[Keyword long-tail 1 basada en pregunta (ej. 'cómo funciona GEO')]", "intencion": "Informativa" }},
    {{ "keyword": "[Keyword long-tail 2 basada en problema (ej. 'por qué mi IA no cita mi web')]", "intencion": "Informativa" }}
  ],
  "cluster_semantico_LSI": [
    {{ "termino": "Motores Generativos" }},
    {{ "termino": "SGE" }},
    {{ "termino": "E-E-A-T" }}
  ],
  "tags_sugeridos_blog": [
    "GEO", "SEO", "Estrategia de Contenido", "IA"
  ]
}}

Tu respuesta DEBE ser un bloque de código JSON válido y nada más.
"""

AGENT_2_COMPETITOR_PROMPT = """
Actúa como un Analista SEO de élite (Agente 2 del Manual de Producción).
Estoy analizando la SERP para la palabra clave principal: "{KEYWORD_PRINCIPAL}"

He recopilado los resultados de Google Search (título, link, snippet).
Analiza estos *snippets* para identificar patrones y brechas.

Tu tarea es devolver un análisis en formato JSON (como en Prompt A2.1, pero basado en snippets):
{{
  "keyword_analizada": "{KEYWORD_PRINCIPAL}",
  "intencion_dominante_detectada": "[Informativa (Definición), Informativa (Comparación), etc.]",
  "patrones_recurrentes_snippets": [
    "[Patrón 1 (ej. 'Mencionan listas numeradas (Top 5)')]",
    "[Patrón 2 (ej. 'Comparan X vs Y')]",
    "[Patrón 3 (ej. 'Usan el año actual en el título')]"
  ],
  "entidades_mencionadas_repetidamente": [
    "[Concepto/Herramienta/Persona 1]",
    "[Concepto/Herramienta/Persona 2]"
  ],
  "must_cover_elements": [
    "[Subtema que DEBEMOS cubrir, basado en los snippets (ej. 'Definición de GEO')]",
    "[Subtema 2 (ej. 'La diferencia clave con SEO')]",
    "[Subtema 3 (ej. 'Importancia de E-E-A-T')]"
  ],
  "content_gaps_differentiators": [
    "[Oportunidad no vista en los snippets (ej. 'Nadie menciona el impacto en el SEO Local')]",
    "[Oportunidad 2 (ej. 'Faltan estudios de caso prácticos')]"
  ]
}}

Tu respuesta DEBE ser un bloque de código JSON válido y nada más.

Input (Resultados de Google Search):
"""

AGENT_3_OUTLINE_PROMPT = """
Actúa como un Arquitecto de Contenido SEO y un experto en E-E-A-T (Agente 3 del Manual de Producción).
Tu tarea es crear la estructura (outline) detallada para un artículo de blog "perfecto" que domine en SEO y GEO.

**Instrucciones de la Estructura (Prompt A3.1):**
1.  El H1 debe ser una variación convincente de la palabra clave principal.
2.  La estructura debe seguir un orden lógico, cubriendo todos los "must_cover_elements" (de A2).
3.  La estructura DEBE integrar estratégicamente los "content_gaps_differentiators" (de A2) para superar a la competencia.
4.  Cada sección H2 o H3 debe incluir las palabras clave secundarias y semánticas relevantes (de A1) de forma natural.
5.  **Requisito GEO:** Donde sea apropiado (definiciones, listas), incluye notas de "[Formato GEO: Lista de viñetas]" o "[Formato GEO: Tabla Comparativa]".
6.  **Requisito E-E-A-T:** Inserta marcadores de posición donde el redactor debe añadir experiencia. Usa "[Nota E-E-A-T: Insertar anécdota/caso de estudio real aquí]" o "[Nota E-E-A-T: Citar fuente de autoridad]".
7.  Incluye una sección de "Preguntas Frecuentes" (FAQ) al final, utilizando las palabras clave long-tail (de A1).

**Formato de Salida (Markdown):**
(Debes devolver SOLAMENTE el Markdown del outline, empezando por el H1. No incluyas '```markdown' al inicio ni '```' al final.)

---
INPUTS DE MATERIALES:

1.  **JSON de Clústeres (de A1):**
{JSON_CLUSTERS}

2.  **Informe de Oportunidad (de A2):**
{OPPORTUNITY_REPORT}
"""


# --- función principal (sin cambios de flujo) ---
async def main_pipeline_v2(url: str, output_dir: str):
    """
    Orquesta el flujo de Agentes 0-3, descubriendo automáticamente la audiencia.
    """
    if not (GOOGLE_API_KEY and CSE_ID):
        logger.error("Faltan GOOGLE_API_KEY y CSE_ID en .env. El Agente 2 fallará.")
        return

    # Aceptamos NV_API_KEY o GEMINI_API_KEY para poder correr
    if not (NV_API_KEY or GEMINI_API_KEY):
        logger.error(
            "Falta NV_API_KEY o GEMINI_API_KEY en .env. El script no puede funcionar."
        )
        return

    os.makedirs(output_dir, exist_ok=True)
    logger.info(f"Resultados se guardarán en: {output_dir}")

    async with aiohttp.ClientSession(headers=HEADERS) as session:
        # --- AGENTE 0: Descubrimiento (Crawl + Scrape + Infer) ---
        logger.info(f"--- 🕵️ Agente 0: Iniciando Descubrimiento para {url} ---")

        # 0.1: Crawl
        try:
            logger.info("Ejecutando crawler para encontrar posts del blog...")
            all_urls = await crawl_site(url, max_pages=50)
        except Exception as e:
            logger.error(f"El crawler falló: {e}. Se intentará solo con la homepage.")
            all_urls = [url]

        # 0.2: Filter & Scrape
        urls_to_analyze = filter_blog_urls(all_urls, url, max_sample=5)

        logger.info("Scrapeando homepage y posts para contexto...")
        homepage_data_task = fetch_and_parse(session, url)
        analysis_tasks = [
            fetch_and_parse(session, u) for u in urls_to_analyze if u != url
        ]

        homepage_data = await homepage_data_task
        blog_data_list = await asyncio.gather(*analysis_tasks)

        # 0.3: Build Context & Run Agent 0
        combined_input_data = {
            "homepage_context": homepage_data,
            "blog_post_samples": blog_data_list,
        }
        combined_input_text = json.dumps(
            combined_input_data, indent=2, ensure_ascii=False
        )

        agent_0_output_text = await run_agent_llm(
            AGENT_0_DISCOVERY_PROMPT, combined_input_text, use_json_output=True
        )
        agent_0_data = parse_json_from_llm(agent_0_output_text)

        if not agent_0_data or "main_topic" not in agent_0_data:
            logger.error("Agente 0 falló. No se pudo inferir el tema o la audiencia.")
            logger.error(f"Raw output: {agent_0_output_text}")
            return

        main_topic = agent_0_data.get("main_topic")
        target_audience = agent_0_data.get("target_audience")

        logger.info(f"✅ Tema Principal Descubierto: {main_topic}")
        logger.info(f"✅ Audiencia Objetivo Descubierta: {target_audience}")
        with open(
            os.path.join(output_dir, "A0_discovery.json"), "w", encoding="utf-8"
        ) as f:
            json.dump(agent_0_data, f, indent=2, ensure_ascii=False)

        # --- AGENTE 1: Estratega de Keywords ---
        logger.info("--- 🧠 Agente 1: Generando Clústeres de Keywords ---")
        prompt_a1 = AGENT_1_KEYWORD_PROMPT.format(
            AUDIENCIA_TARGET=target_audience, TEMA_PRINCIPAL=main_topic
        )

        agent_1_output_text = await run_agent_llm(
            prompt_a1, f"Analizar tema: {main_topic}", use_json_output=True
        )
        agent_1_data = parse_json_from_llm(agent_1_output_text)
        if not agent_1_data:
            logger.error("Agente 1 falló. No se pudo parsear el clúster de keywords.")
            return

        primary_keyword = agent_1_data.get("palabra_clave_principal", main_topic)
        logger.info(f"Keyword principal seleccionada: {primary_keyword}")
        with open(
            os.path.join(output_dir, "A1_keyword_clusters.json"), "w", encoding="utf-8"
        ) as f:
            json.dump(agent_1_data, f, indent=2, ensure_ascii=False)

        # --- AGENTE 2: Analista Competitivo ---
        logger.info("--- 📈 Agente 2: Analizando Competencia (SERPs) ---")
        search_results = await run_google_search(
            primary_keyword, GOOGLE_API_KEY, CSE_ID
        )

        prompt_a2 = AGENT_2_COMPETITOR_PROMPT.format(KEYWORD_PRINCIPAL=primary_keyword)
        input_a2 = json.dumps(search_results, indent=2, ensure_ascii=False)

        agent_2_output_text = await run_agent_llm(
            prompt_a2, input_a2, use_json_output=True
        )
        agent_2_data = parse_json_from_llm(agent_2_output_text)
        if not agent_2_data:
            logger.error(
                "Agente 2 falló. No se pudo parsear el análisis de competencia."
            )
            return

        logger.info(f"Análisis de 'must-cover' completado.")
        with open(
            os.path.join(output_dir, "A2_opportunity_report.json"),
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(agent_2_data, f, indent=2, ensure_ascii=False)

        # --- AGENTE 3: Arquitecto de Contenido ---
        logger.info("--- 🏗️ Agente 3: Construyendo el Esqueleto del Artículo ---")

        json_clusters_str = json.dumps(agent_1_data, indent=2, ensure_ascii=False)
        opportunity_report_str = json.dumps(agent_2_data, indent=2, ensure_ascii=False)

        prompt_a3 = AGENT_3_OUTLINE_PROMPT.format(
            JSON_CLUSTERS=json_clusters_str, OPPORTUNITY_REPORT=opportunity_report_str
        )

        # Para el Agente 3, queremos Markdown, no JSON.
        final_outline_md = await run_agent_llm(prompt_a3, "", use_json_output=False)

        if not final_outline_md.startswith("#"):
            logger.warning(
                "La salida del Agente 3 no parece un Markdown. Se guardará igualmente."
            )
            final_outline_md = (
                "## H1 (Posible error del Agente 3)\n\n" + final_outline_md
            )

        logger.info("--- ✅ ¡Flujo Completado! ---")
        print("\n" + "=" * 50)
        print(f"OUTLINE GENERADO (Guardado en {output_dir}/A3_final_outline.md)")
        print("=" * 50 + "\n")
        print(final_outline_md)

        with open(
            os.path.join(output_dir, "A3_final_outline.md"), "w", encoding="utf-8"
        ) as f:
            f.write(final_outline_md)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generador de Contenido IA v2 (Descubrimiento Automático)"
    )
    parser.add_argument("url", help="URL de la empresa (ej. 'microsoft.com')")

    if len(sys.argv) < 2:
        parser.print_help()
        print("\nEjemplo de uso:")
        print('python content_generator_v2.py "https://www.sapucai.com"')
        sys.exit(1)

    args = parser.parse_args()

    # Limpiar URL
    if not args.url.startswith("http"):
        url = "https://" + args.url
    else:
        url = args.url

    try:
        domain = urlparse(url).netloc.lstrip("www.")
        output_folder = os.path.join("content_production", domain.replace(".", "_"))
    except Exception:
        output_folder = "content_production/default"

    try:
        asyncio.run(main_pipeline_v2(url, output_folder))
    except ImportError as e:
        logger.error(
            f"Error: {e}. Asegúrate de tener 'pip install openai google-generativeai aiohttp beautifulsoup4 python-dotenv' (según la integración que desees usar)"
        )
    except Exception as e:
        logger.exception(f"Error fatal en el pipeline: {e}")
