#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
blog.py (content_generator_v9_ceibo)
Versión 9.8 (API Timeout Fix)

CHANGELOG v9.8:
- FIX (API Hang): Se añade un 'timeout' de 120 segundos a la llamada
  'nv_client.chat.completions.create' dentro de 'run_agent_llm'.
- FIX (Error Handling): Se añade manejo de 'Timeout' en el bloque try/except
  de 'run_agent_llm' para que el script continúe si la API se cuelga,
  insertando el fallback (instrucciones) en lugar de la prosa.
- (Anteriores) v9.7: Lógica de Scrapeo Garantizado.
- (Anteriores) v9.6: Límite de contexto (1000 chars) y fix de JSON.
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
from urllib.parse import urlparse, urljoin
from datetime import datetime
from dotenv import load_dotenv
from functools import partial

# --- Dependencias de IA (NVIDIA / OpenAI-style) ---
try:
    from openai import OpenAI as NVOpenAI

    NV_OPENAI_AVAILABLE = True
except Exception as e:
    logging.fatal(
        f"openai NV client no está instalado: {e}. Ejecuta 'pip install openai'"
    )
    NV_OPENAI_AVAILABLE = False
    sys.exit(1)

# --- Importar Crawler ---
try:
    from crawler import crawl_site
except ImportError:

    async def crawl_site(url, max_pages=1):
        logger.warning("Usando crawl_site dummy.")
        return [url]


# --- Cargar .env ---
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
CSE_ID = os.getenv("CSE_ID")
NV_API_KEY = os.getenv("NV_API_KEY")
NV_BASE_URL = os.getenv("NV_BASE_URL", "https://integrate.api.nvidia.com/v1").strip()
NV_MODEL = os.getenv("NV_MODEL", "moonshotai/kimi-k2-instruct-0905")

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("ContentGeneratorV9_8")  # v9.8

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    )
}


# --- Util: reemplazo seguro de placeholders ---
def fill_prompt(template: str, mapping: dict) -> str:
    """Reemplaza placeholders {KEY} por valores."""
    out = template
    for k, v in mapping.items():
        placeholder = "{" + k + "}"
        out = out.replace(placeholder, str(v) if v is not None else "")
    return out


# --- LLM Call ---
# 🟢 INICIO: CÓDIGO ACTUALIZADO (v9.8 - API Timeout)
async def run_agent_llm(
    system_prompt: str,
    user_message: str,
    use_json_output=False,
    stream=False,
    max_tokens_override=None,
):
    """Llamada LLM con manejo de contexto y truncado."""
    if not NV_API_KEY or not NV_OPENAI_AVAILABLE:
        raise ImportError("NV_API_KEY no configurada o cliente no disponible.")

    sys_prompt = (system_prompt or "").strip()
    if use_json_output:
        sys_prompt += (
            "\n\nINSTRUCCIONES JSON OBLIGATORIAS:\n"
            "Devuelve ÚNICAMENTE un objeto JSON válido. Sin explicaciones, sin markdown.\n"
        )

    model_name = NV_MODEL or "moonshotai/kimi-k2-instruct-0905"
    temperature = 0.2
    top_p = 0.9

    # Gestión de contexto (v7.5)
    MODEL_MAX_CONTEXT = 8192
    SAFE_BUFFER = 512
    USABLE_CONTEXT = MODEL_MAX_CONTEXT - SAFE_BUFFER  # ~7680

    estimated_prompt_tokens = int(
        len((system_prompt or "") + (user_message or "")) / 2.5
    )

    if estimated_prompt_tokens >= USABLE_CONTEXT:
        logger.error(
            f"Error: Prompt (est. {estimated_prompt_tokens} tokens) excede el límite usable ({USABLE_CONTEXT})."
        )
        overshoot_tokens = estimated_prompt_tokens - USABLE_CONTEXT
        chars_to_cut = int(overshoot_tokens * 2.5) + SAFE_BUFFER

        if chars_to_cut >= len(user_message):
            logger.error(
                "Error crítico: El system_prompt por sí solo es demasiado grande."
            )
            # Cortar incluso el system prompt si es necesario (último recurso)
            if chars_to_cut >= len(system_prompt):
                logger.error("Error catastrófico: No se puede truncar lo suficiente.")
                system_prompt = system_prompt[:100]
            else:
                system_prompt = system_prompt[:-chars_to_cut]
            user_message = user_message[:100]
        else:
            user_message = user_message[:-chars_to_cut]

        logger.warning(
            f"Prompt truncado (se cortaron {chars_to_cut} caracteres del user_message) para que quepa."
        )
        estimated_prompt_tokens = int(len((system_prompt or "") + user_message) / 2.5)

    available_completion_tokens = max(0, USABLE_CONTEXT - estimated_prompt_tokens)

    request_max_tokens = None
    if max_tokens_override:
        if max_tokens_override > available_completion_tokens:
            logger.warning(
                f"max_tokens_override reducido de {max_tokens_override} a {available_completion_tokens}"
            )
            request_max_tokens = available_completion_tokens
        else:
            request_max_tokens = max_tokens_override
    else:
        request_max_tokens = available_completion_tokens

    if request_max_tokens < 100:
        logger.error(
            f"Espacio de completado insuficiente ({request_max_tokens}). Forzando a 100."
        )
        request_max_tokens = 100

    # 🟢 FIX v9.8: Añadir timeout de 120 segundos a la llamada de API
    timeout_seconds = 120.0

    def nv_call_sync():
        nv_client = NVOpenAI(base_url=NV_BASE_URL, api_key=NV_API_KEY)
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_message or ""},
        ]

        create_kwargs = dict(
            model=model_name,
            messages=messages,
            temperature=temperature,
            top_p=top_p,
            max_tokens=request_max_tokens,
            timeout=timeout_seconds,  # <<< ¡LA LÍNEA CLAVE!
        )
        completion = nv_client.chat.completions.create(**create_kwargs)
        return str(completion.choices[0].message.content)

    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(None, nv_call_sync)
    except Exception as exc:
        logger.exception(f"Error LLM: {exc}")

        # 🟢 FIX v9.8: Manejar el error de Timeout
        if "Timeout" in str(exc) or "timed out" in str(exc):
            logger.error(
                f"❌ Error de Timeout de API ({timeout_seconds}s) para el prompt. Devolviendo fallback."
            )
            return ""  # Devolver vacío para que el pipeline ponga las instrucciones

        if "maximum context length" in str(exc) and request_max_tokens:
            logger.warning(
                f"Context length excedido. Reintentando con {request_max_tokens // 2} tokens..."
            )
            return await run_agent_llm(
                system_prompt,
                user_message,
                use_json_output,
                stream,
                request_max_tokens // 2,
            )
        raise
    return result.strip()


# 🟢 FIN: CÓDIGO ACTUALIZADO (v9.8)


# --- Parser JSON Robusto ---
def parse_json_from_llm(text: str):
    """Parser JSON tolerante a errores comunes de LLMs."""
    text = (text or "").strip()

    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    if text.startswith("{{") and text.endswith("}}"):
        text = text[1:-1]

    start_index = text.find("{")
    end_index = text.rfind("}")

    if start_index != -1 and end_index != -1 and end_index > start_index:
        json_text = text[start_index : end_index + 1]
        try:
            json_text = re.sub(r"\{\{", "{", json_text)
            json_text = re.sub(r"\}\}", "}", json_text)
            return json.loads(json_text)
        except Exception as e:
            logger.error(f"Fallo JSON greedy: {e}\nTexto: {json_text[:500]}")

    try:
        return json.loads(text)
    except Exception as e:
        logger.error(f"Fallo JSON original: {e}\nTexto: {text[:500]}")
        return None


# --- Scraping ---
# 🟢 INICIO: CÓDIGO ACTUALIZADO (v9.6)
async def fetch_and_parse(session, url: str) -> dict:
    """Scrapea URL y extrae h1 y corpus (Versión Robusta de test_agent_2_5)."""
    try:
        # 🟢 FIX: Añadir logging y headers=HEADERS explícitamente
        logger.info(f"  > [A2.5] Scrapeando URL: {url}")
        # 🟢 FIX v9.6: Aumentar timeout de 15 a 20
        async with session.get(url, timeout=20, headers=HEADERS) as resp:
            if resp.status != 200:
                # 🟢 FIX: Añadir logging
                logger.warning(
                    f"  > [A2.5] Fallo al scrapear (Status {resp.status}): {url}"
                )
                return {"url": url, "h1": "Error de Acceso", "corpus": ""}

            html = await resp.text(errors="ignore")
            soup = BeautifulSoup(html, "html.parser")
            h1 = soup.find("h1")
            h1_text = h1.get_text(strip=True) if h1 else ""
            main_content = (
                soup.find("main") or soup.find("article") or soup.find("body")
            )
            text_corpus = (
                " ".join(main_content.get_text(separator=" ", strip=True).split())
                if main_content
                else ""
            )

            # 🟢 FIX: Añadir logging
            logger.info(f"  > [A2.5] Scrapeo OK (H1: {h1_text[:50]}...)")
            # 🟢 FIX v9.6: Reducir corpus de 2000 a 1000 para evitar overflow
            return {"url": url, "h1": h1_text, "corpus": text_corpus[:1000]}

    except Exception as e:
        # 🟢 FIX: Añadir logging
        logger.error(f"  > [A2.5] Error en fetch_and_parse ({url}): {e}")
        return {"url": url, "h1": "Error de Scrapeo", "corpus": str(e)}


# 🟢 FIN: CÓDIGO ACTUALIZADO


def filter_target_urls(all_urls: list, base_url: str, max_sample=3) -> list:
    """Filtra URLs con insights: casos de estudio, servicios, proyectos."""
    insight_indicators = [
        "/blog",
        "/insights",
        "/articulos",
        "/novedades",
        "/casos-de-estudio",
        "/casos",
        "/proyectos",
        "/clientes",
        "/servicios",
        "/soluciones",
        "/plataformas",
    ]

    insight_urls, other_urls = [], []
    base_domain = urlparse(base_url).netloc
    for url in all_urls:
        try:
            parsed = urlparse(url)
            if parsed.netloc.endswith(base_domain):
                path = parsed.path.lower()
                if any(indicator in path for indicator in insight_indicators):
                    insight_urls.append(url)
                else:
                    other_urls.append(url)
        except Exception:
            continue

    sample = list(dict.fromkeys(insight_urls))[:max_sample]
    remaining = max_sample - len(sample)

    if remaining > 0:
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
    return sample


# 🟢 INICIO: CÓDIGO ACTUALIZADO (2025-11-05 - Fix URL Markdown)
async def run_google_search(query: str, api_key: str, cx_id: str, num=5):
    """Búsqueda Google Custom Search (Versión Corregida de test_agent_2_5)."""
    if not api_key or not cx_id:
        # 🟢 FIX: Añadir logging de error
        logger.error("[A2.5] API Key o CX_ID no configurados en .env")
        return {"error": "API Key o CX_ID no configurados"}

    # 🟢 FIX: Corregir la URL rota. ESTA ES LA LÍNEA DEL ERROR.
    # Asegúrate de que esta línea sea una CADENA DE TEXTO simple.
    endpoint = "https://www.googleapis.com/customsearch/v1"

    params = {"key": api_key, "cx": cx_id, "q": query, "num": num}

    # 🟢 FIX: Añadir logging de la búsqueda
    logger.info(f"--- 📞 [A2.5] Iniciando Búsqueda en Google ---")
    logger.info(f"Query: {query}")
    logger.info(f"CSE_ID: {cx_id[:5]}...")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(endpoint, params=params, timeout=15) as resp:
                # 🟢 FIX: Añadir logging de respuesta
                logger.info(f"[A2.5] Respuesta de Google API: {resp.status}")

                if resp.status == 200:
                    data = await resp.json()
                    simplified_items = []
                    # 🟢 FIX: Mejorar chequeo de 'items'
                    if "items" in data and len(data["items"]) > 0:
                        logger.info(
                            f"✅ [A2.5] Google encontró {len(data['items'])} items."
                        )
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
                        # 🟢 FIX: Añadir logging de 'no items'
                        logger.warning(
                            "[A2.5] Google devolvió 200 OK, pero 'items' está vacío."
                        )
                        return {"query": query, "items": []}
                else:
                    # 🟢 FIX: Añadir logging de error
                    error_text = await resp.text()
                    logger.error(f"❌ [A2.5] Google API devolvió error {resp.status}")
                    logger.error(f"Respuesta: {error_text}")
                    return {"error": f"Status {resp.status}", "details": error_text}

    except Exception as e:
        logger.exception(f"[A2.5] Error de red en run_google_search: {e}")
        return {"error": str(e)}


# 🟢 FIN: CÓDIGO ACTUALIZADO


# --- 🟢 Agente 2.5: Insights Externos (v9.7 - Lógica de Scrapeo Garantizado) ---
async def fetch_external_insight_context(
    session, keyword: str, api_key: str, cx_id: str
) -> tuple:
    """
    Busca insights externos e intenta activamente conseguir un MÍNIMO de 3 fuentes.
    Si falla, vuelve a buscar en Google hasta 3 veces.
    RETORNA: (str_json, list[dict_scrapeado], list[dict_snippet])
    """
    MIN_SUCCESSFUL_SCRAPES = 3
    GOOGLE_QUERIES_PER_LOOP = 3  # Reducido de 5 a 3 para no agotar la API
    GOOGLE_RESULTS_PER_QUERY = 3  # Aumentado de 2 a 3
    MAX_LOOPS = 3  # (1 Búsqueda inicial + 2 re-intentos)

    if not api_key or not cx_id:
        logger.warning("Agente 2.5 omitido: Faltan credenciales Google.")
        return ("{}", [], [])

    successful_scrapes = []
    all_google_items = []
    urls_to_try = set()
    urls_attempted = set()
    loop_count = 0

    # (v9.2) Consultas mucho más amplias para asegurar resultados
    base_search_queries = [
        f"{keyword} estadísticas ROI",
        f"{keyword} benchmarks industria 2024 2025",
        f"{keyword} informe tendencias datos",
        f"{keyword} caso de estudio datos",
        f"{keyword} statistics report",
    ]

    # --- INICIO: Bucle de Scrapeo Garantizado ---
    while len(successful_scrapes) < MIN_SUCCESSFUL_SCRAPES and loop_count < MAX_LOOPS:
        loop_count += 1
        logger.info(
            f"--- [A2.5 Loop {loop_count}/{MAX_LOOPS}] Inciando ciclo. Meta: {len(successful_scrapes)}/{MIN_SUCCESSFUL_SCRAPES} fuentes."
        )

        # 1. Revisar si necesitamos más URLs
        available_urls = list(urls_to_try - urls_attempted)

        if not available_urls:
            logger.info(
                f"--- [A2.5 Loop {loop_count}] Pool de URLs vacío. Buscando en Google."
            )

            # Para el loop 2+, añadir "top" o "mejores" para variar
            query_modifier = ""
            if loop_count > 1:
                query_modifier = " top" if loop_count == 2 else " mejores"

            current_queries = [
                q + query_modifier
                for q in base_search_queries[:GOOGLE_QUERIES_PER_LOOP]
            ]

            search_tasks = [
                run_google_search(q, api_key, cx_id, num=GOOGLE_RESULTS_PER_QUERY)
                for q in current_queries
            ]
            search_results_list = await asyncio.gather(*search_tasks)

            new_urls_found_this_loop = 0
            for result in search_results_list:
                if result and result.get("items"):
                    all_google_items.extend(result["items"])
                    for item in result["items"]:
                        if item.get("link"):
                            urls_to_try.add(item.get("link"))
                            new_urls_found_this_loop += 1

            logger.info(
                f"--- [A2.5 Loop {loop_count}] Google encontró {new_urls_found_this_loop} URLs nuevas."
            )
            available_urls = list(urls_to_try - urls_attempted)

            # Si Google no devuelve nada nuevo, no podemos continuar.
            if not available_urls:
                logger.warning(
                    f"--- [A2.5 Loop {loop_count}] Google no devolvió más URLs. Finalizando búsqueda."
                )
                break  # Salir del while loop

        # 2. Determinar cuántos scrapes necesitamos e intentar
        needed = MIN_SUCCESSFUL_SCRAPES - len(successful_scrapes)
        urls_for_this_batch = available_urls[
            :needed
        ]  # Intentar solo los que necesitamos

        if not urls_for_this_batch:
            logger.warning(
                f"--- [A2.5 Loop {loop_count}] No hay más URLs disponibles para intentar. {len(urls_attempted)} ya intentadas."
            )
            break  # Salir del while loop

        logger.info(
            f"--- [A2.5 Loop {loop_count}] Necesitamos {needed} fuentes. Intentando scrapear {len(urls_for_this_batch)} URLs..."
        )

        scrape_tasks = [fetch_and_parse(session, url) for url in urls_for_this_batch]
        urls_attempted.update(urls_for_this_batch)  # Marcar como intentadas

        scraped_data_list = await asyncio.gather(*scrape_tasks)

        # 3. Procesar resultados del batch
        for data in scraped_data_list:
            if data and data.get("corpus") and "Error" not in data.get("h1"):
                source_entry = {
                    "title": data.get("h1", "Fuente Externa"),
                    "url": data.get("url"),
                    "data": data.get("corpus"),
                }
                # Evitar duplicados (por si Google dio la misma URL 2 veces)
                if source_entry["url"] not in [s["url"] for s in successful_scrapes]:
                    successful_scrapes.append(source_entry)
                    logger.info(
                        f"--- [A2.5 Loop {loop_count}] ✅ ÉXITO Scrape: {source_entry['url']} ({len(successful_scrapes)}/{MIN_SUCCESSFUL_SCRAPES})"
                    )

            # Si ya tenemos suficientes, no añadir más de este batch
            if len(successful_scrapes) >= MIN_SUCCESSFUL_SCRAPES:
                break

    # --- FIN: Bucle de Scrapeo Garantizado ---

    if len(successful_scrapes) < MIN_SUCCESSFUL_SCRAPES:
        logger.warning(
            f"--- [A2.5 Final] No se pudo alcanzar la meta de {MIN_SUCCESSFUL_SCRAPES} fuentes. Se obtuvieron {len(successful_scrapes)}."
        )
    else:
        logger.info(
            f"--- [A2.5 Final] Meta alcanzada. Se obtuvieron {len(successful_scrapes)} fuentes."
        )

    context_json = json.dumps(successful_scrapes, ensure_ascii=False, indent=2)

    # Devolver snippets crudos (all_google_items) es vital para v9.5 (Grounding-First)
    return (context_json, successful_scrapes, all_google_items)


# 🟢 FIN: CÓDIGO ACTUALIZADO (v9.7)


# --- Extracción de Outline (v8.1) ---
def extract_from_outline(outline_md: str) -> dict:
    """Extrae H1, body y FAQs del outline."""
    h1 = "Artículo sin Título"
    faqs = []

    cleaned_md = outline_md.strip()
    if cleaned_md.startswith("```markdown"):
        cleaned_md = cleaned_md[11:]
    if cleaned_md.endswith("```"):
        cleaned_md = cleaned_md[:-3]
    cleaned_md = cleaned_md.strip()

    # Patrones H1
    h1_atx_match = re.search(r"^\s*#\s+(.*)", cleaned_md, re.MULTILINE)
    h1_setext_match = re.search(r"^(.*)\n\s*(=+|-+)\s*(\n|$)", cleaned_md, re.MULTILINE)
    h1_bold_match = re.search(r"^\s*\*\*(.*)\*\*\s*(\n|$)", cleaned_md, re.MULTILINE)

    h1_found_at_index = -1

    if h1_atx_match:
        h1 = h1_atx_match.group(1).strip().replace("*", "")
        h1_found_at_index = h1_atx_match.end()
    elif h1_setext_match:
        h1 = h1_setext_match.group(1).strip().replace("*", "")
        h1_found_at_index = h1_setext_match.end()
    elif h1_bold_match:
        h1 = h1_bold_match.group(1).strip().replace("*", "")
        h1_found_at_index = h1_bold_match.end()
    else:
        first_line_match = re.search(r"^(.*)(\n|$)", cleaned_md)
        if first_line_match:
            h1 = first_line_match.group(1).strip().replace("*", "")
            h1_found_at_index = first_line_match.end()
            logger.warning(f"H1 no formateado. Usando primera línea: '{h1}'")

    if h1_found_at_index != -1:
        outline_body = cleaned_md[h1_found_at_index:].strip()
    else:
        outline_body = cleaned_md

    # Buscar FAQs
    faq_section_match = re.search(
        r"##\s+(Preguntas Frecuentes|FAQ|FAQs)\b.*",
        outline_body,
        re.IGNORECASE | re.DOTALL,
    )
    if faq_section_match:
        faq_text = faq_section_match.group(0)
        faq_matches = re.findall(r"^\s*###+\s+(.*)", faq_text, re.MULTILINE)
        faqs = [
            q.strip().replace("[", "").replace("]", "")
            for q in faq_matches
            if not q.strip().startswith("[RESPUESTA_FAQ")
        ]

    return {"h1": h1, "outline_body": outline_body, "faqs": faqs}


# (v8.2) Eliminados is_outline_like y check_for_repetition


# --- 🟢 NUEVO: Verificador de Calidad de Citas ---
def check_citation_quality(text: str, external_sources: list) -> dict:
    """
    Verifica si el texto contiene citas a fuentes externas.
    Retorna: {"has_citations": bool, "citation_count": int, "missing_sources": list}
    """
    citation_count = len(re.findall(r"\[([^\]]+)\]\(https?://[^\)]+\)", text))

    missing_sources = []
    for source in external_sources:
        source_title = source.get("title", "")
        source_url = source.get("url", "")

        domain = urlparse(source_url).netloc.replace("www.", "") if source_url else ""

        # Buscar por dominio o título
        if (domain and domain in text.lower()) or (
            source_title and source_title.lower() in text.lower()
        ):
            if source_url not in text:
                missing_sources.append(
                    {
                        "title": source_title,
                        "url": source_url,
                        "mentioned_but_not_linked": True,
                    }
                )

    return {
        "has_citations": citation_count > 0,
        "citation_count": citation_count,
        "total_external_sources_found": len(external_sources),
        "missing_sources": missing_sources,
    }


# ---
# 🤖 PROMPTS ACTUALIZADOS (v9.5 - Grounding-First)
# ---

AGENT_0_DISCOVERY_PROMPT = """
Actúa como Analista de Negocios (Agente 0).
Analiza el contenido de la homepage y páginas de servicio para extraer:
1. "company_description": Descripción concisa (1-2 frases)
2. "main_topic": Tema principal / industria
3. "target_audience": Público objetivo

Devuelve JSON puro sin explicaciones.
"""

AGENT_1_KEYWORD_PROMPT = """
Actúa como Estratega SEO (Agente 1).
Audiencia: {AUDIENCIA_TARGET}
Tema: {TEMA_PRINCIPAL}

Genera plan de keywords en JSON:
{{
  "palabra_clave_principal": "[Keyword semilla]",
  "intencion_principal": "[Informativa/Transaccional]",
  "cluster_primario": [{{"keyword": "[Keyword primaria]", "intencion": "[Intención]"}}],
  "cluster_long_tail": [{{"keyword": "[Pregunta long-tail]", "intencion": "Informativa"}}],
  "cluster_semantico_LSI": [{{"termino": "Termino LSI"}}]
}}
"""

AGENT_2_COMPETITOR_PROMPT = """
Actúa como Analista SEO (Agente 2).
Keyword: "{KEYWORD_PRINCIPAL}"

Analiza los snippets de Google y devuelve JSON:
{{
  "keyword_analizada": "{KEYWORD_PRINCIPAL}",
  "intencion_dominante_detectada": "[Tipo de intención]",
  "patrones_recurrentes_snippets": ["[Patrón 1]"],
  "entidades_mencionadas_repetidamente": ["[Concepto 1]"],
  "must_cover_elements": ["[Subtema obligatorio]"],
  "content_gaps_differentiators": ["[Oportunidad única]"]
}}
"""

# 🟢 NUEVO: Prompt A3 con Instrucciones de Citación (v9.5 - Grounding-First)
AGENT_3_OUTLINE_PROMPT = """
Actúa como Director de Consultoría SEO/GEO (Agente 3).
Crea el outline detallado para un artículo de blog optimizado.

**REGLAS DE ESTRUCTURA:**
1. UN SOLO H1 (título). H2 para secciones. H3 para subsecciones.
2. Tono de insight (NO definiciones básicas).
3. **INTEGRACIÓN DE DATOS OBLIGATORIA:**
   * `CLIENT_INSIGHT_CONTEXT`: Para casos de estudio propios
   * `EXTERNAL_INSIGHT_CONTEXT`: (Prioridad 1) Para estadísticas y fuentes externas (scrapeado)
   * `GOOGLE_SNIPPET_CONTEXT`: (Prioridad 2) Para snippets de Google (usar si el scrapeo está vacío)
   
4. **CITAS (CRÍTICO v9.5 - Grounding-First):**
   * NO INVENTES DATOS.
   * Busca un dato en el CONTEXTO (P1: External, P2: Snippets).
   * Coloca el dato encontrado en el outline usando este formato estricto:
     `[DATO_CITADO: (Escribe aquí la estadística textual del CONTEXTO) (Fuente: [Nombre de la Fuente](URL_del_CONTEXTO))]`
   * SI AMBOS ESTÁN VACÍOS, omite las citas externas.
   
5. **ESTRUCTURA FINAL:**
   * ## Introducción
     * [DATO_CITADO: (Dato de P1 o P2) (Fuente: [Fuente](URL))]
     * [[PÍLDORA_EXPERIENCIA: Conectar estadística con nuestra experiencia]]
   * ## Caso de Estudio Propio (Basado en el Sitio del Cliente)
     * [DATO: Extraer servicio o caso del cliente de CLIENT_INSIGHT_CONTEXT]
     * [[PÍLDORA_EXPERIENCIA: Analizar por qué es valioso]]
   * ## KPIs con Benchmarks
     * [TABLA DE KPIS] (Si EXTERNAL/GOOGLE_SNIPPET está vacío, escribe: 'No hay benchmarks externos disponibles.')
   * ## Checklist de Implementación
     * [CHECKLIST DE IMPLEMENTACIÓN]
   * ## Fuentes Clave para Verificadores IA
     * [LISTA DE FUENTES CLAVE] (Si EXTERNAL/GOOGLE_SNIPPET está vacío, omite esta sección H2 completa)
   * ## Preguntas Frecuentes (FAQ)
     * ### {Pregunta 1 de JSON_CLUSTERS}
     * [RESPUESTA_FAQ: Generar respuesta <= 90 palabras]
     * ### {Pregunta 2 de JSON_CLUSTERS}
     * [RESPUESTA_FAQ: Generar respuesta <= 90 palabras]
   * ## Conclusión y CTA
     * [[PÍLDORA_CTA: Cierre y CTA claro]]
   * ## Sobre el Autor
     * [BIOGRAFÍA DEL AUTOR]

Devuelve SOLO el Markdown del outline.
"""

# 🟢 NUEVO: Prompt A4 con Forzado de Enlaces (v9.5 - Grounding-First)
AGENT_4_PROSE_WRITER_PROMPT = """
Actúas como Redactor Elite (Agente 4.1).
Convierte las instrucciones en prosa profesional y citada.

**Contexto General (Solo para tu información):**
{base_context}

**Tarea Específica (Contexto de Sección + Instrucciones):**
{user_message}

**REGLAS OBLIGATORIAS (v9.5):**
1. **EVITAR REPETICIÓN:** Varía estructuras. No empieces párrafos igual.
2. **TONO INSIGHT:** NO definiciones. SÍ valor estratégico.
3. **PÁRRAFOS CORTOS:** 3-4 oraciones máximo (móvil-friendly).
4. **SOLO PROSA (CRÍTICO):** DEVUELVE SÓLO PROSA. El 'user_message' contiene el encabezado de la sección (ej. '## KPIs') y las instrucciones. NO repitas el encabezado de la sección en tu respuesta.

5. **CITAS OBLIGATORIAS (CRÍTICO v9.5 - NO ALUCINAR):**
   * TU REGLA MÁS IMPORTANTE: No puedes inventar estadísticas, datos numéricos o porcentajes.
   * TU PROCESO:
       1. MIRA PRIMERO el `GOOGLE_SNIPPET_CONTEXT` y `EXTERNAL_INSIGHT_CONTEXT` (Datos Scrapeados).
       2. EXTRAE un dato específico (ej. "70% ROI", "reporte de Gartner").
       3. ESCRIBE prosa que utilice ESE DATO.
       4. CITA ESE DATO con su 'link' o 'url' correspondiente.
   * Formato: "...un estudio reciente (Fuente: [NombreFuente](URL_del_CONTEXTO)) demostró un 70% de ROI..."
   * **SI EL CONTEXTO ESTÁ VACÍO:** No inventes datos. Escribe prosa basada en la experiencia (ej. "En nuestra práctica...") o en el `CLIENT_INSIGHT_CONTEXT`.
   
6. **CITAS INTERNAS OBLIGATORIAS (CRÍTICO v9.4):**
   * **Regla 6a (Genérica):** Si mencionas la empresa (ej. "En Ceibo Digital...") o sus servicios (ej. "nuestra consultoría..."), DEBES enlazar.
   * Formato: `...en [Ceibo Digital](https://{base_url}/es)...`
   * **Regla 6b (Clúster/Posts):** Revisa el `INVENTARIO DE LINKS INTERNOS (Post/Servicios del Sitio v9.4)`.
   * Si el texto que escribes se relaciona con un tema de ese inventario, INSERTA un enlace interno de forma natural.
   * Intenta insertar 1-2 enlaces de clúster relevantes por sección (H2).
   * Formato: `...aprende más sobre [consultores digitales](URL_DEL_INVENTARIO)...`
   * Usa `Enlaces Internos (Propios)` del contexto (para páginas de servicio) y `INVENTARIO DE LINKS INTERNOS` (para posts).
   
7. **E-E-A-T:** * [[PÍLDORA_EXPERIENCIA]]: Escribe esto como prosa (ej. "En nuestra práctica...")
   * [[PÍLDORA_CTA]]: Escribe esto como prosa (ej. "Contacta con nosotros...")
   
8. **GROUNDING:** Basa insights en CLIENT_INSIGHT_CONTEXT y estadísticas en EXTERNAL/GOOGLE_SNIPPET.

9. **IGNORAR MARCADORES:** [TABLA...], [CHECKLIST...], etc. (excepto [RESPUESTA_FAQ], [[PÍLDORA...]] y [DATO_CITADO:...]).

Devuelve texto limpio sin markdown de código.
"""

AGENT_4_ROBO_REPLACER_PROMPT = """
Actúas como Asistente de Markdown (Agente 4.2).
Genera SOLO el bloque de Markdown solicitado. Sin intro, sin explicaciones.

**Contexto General:**
{base_context}

**Tarea Específica (Instrucciones):**
{user_message}

**CRÍTICO (v9.3 - CITAS):**
* [TABLA DE KPIS]: Usa datos de `FUENTES EXTERNAS PARA CITAR` (P1) o `GOOGLE_SNIPPET_CONTEXT` (P2) para benchmarks y CITA la URL en cada fila.
  Formato: `| KPI | Descripción | 45% en 2025 | [Fuente](URL) |`
  Si AMBOS están vacíos, escribe: 'No hay benchmarks externos disponibles.'
* [LISTA DE FUENTES CLAVE]: Lista TODAS las URLs de 'FUENTES EXTERNAS PARA CITAR' y 'GOOGLE_SNIPPET_CONTEXT'.
  Formato: `* [Título de Fuente](URL completa)`
  Si está vacío, no escribas nada.
"""

AGENT_5_TITLE_PROMPT = """
Experto en Títulos (Agente 5.1).
Keyword: "{primary_keyword}"
H1: "{article_h1}"

Genera 5 títulos (< 60 chars, front-loading, modificadores fuertes).
JSON:
{{
  "titles": [
    {{"title": "Título optimizado", "char_count": X}}
  ]
}}
"""

AGENT_5_META_PROMPT = """
Copywriter SEO (Agente 5.2).
Keyword: "{primary_keyword}"
H1: "{article_h1}"

Escribe 3 meta descriptions (150-160 chars, keyword incluida, CTA claro).
JSON:
{{
  "metas": [
    {{"desc": "Descripción optimizada", "char_count": X}}
  ]
}}
"""

# 🟢 NUEVO: Prompt A5 (v9.6 - Robusto)
AGENT_5_SCHEMA_PROMPT = """
Especialista Schema.org (Agente 5).
Genera JSON-LD combinando Article y BreadcrumbList.
Datos:
* URL: {article_url}
* H1: {article_h1}
* Meta: {meta_description}
* Autor: {author_name} ({author_url})
* Publisher: {publisher_name} ({publisher_url}, logo: {publisher_logo_url})
* FAQs: {faq_list}
* Fecha: {today_date}

INSTRUCCIONES:
1. Genera un "@graph" que contenga "Article" y "BreadcrumbList".
2. Si {faq_list} NO ESTÁ VACÍO, incluye también "FAQPage" en el "@graph".
3. Si incluyes "FAQPage", genera respuestas cortas (<= 90 palabras) para cada FAQ.
4. Si {faq_list} ESTÁ VACÍO, NO incluyas "FAQPage".
Devuelve SOLO el JSON.
"""

AGENT_6_GEO_SNIPPET_PROMPT = """
Experto GEO (Agente 6).
Genera snippet optimizado para motores de IA.
JSON:
{{
  "geo_snippet": "[Resumen 2-3 frases (TL;DR)]",
  "citable_bullets": [
    "[Dato clave 1]",
    "[Beneficio principal]",
    "[Estadística accionable]"
  ]
}}
Input (H1 e Intro):
{article_introduction_text}
"""

# ---
# 🚀 PIPELINE PRINCIPAL (v9.7)
# ---


async def main_pipeline_v9(
    url: str, output_dir: str, author_name: str, author_url: str
):
    """
    Orquesta el flujo completo de Agentes 0-6 con sistema de citas.
    v9.7 - Guaranteed Scrape Loop
    """
    if not NV_API_KEY or not NV_OPENAI_AVAILABLE:
        logger.error("NV_API_KEY no configurada.")
        return

    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    logger.info(f"📁 Resultados en: {output_dir}")

    # Paths
    path_a0 = os.path.join(output_dir, "A0_discovery.json")
    path_a0_5_context = os.path.join(output_dir, "A0_5_client_insight_context.json")
    path_a1 = os.path.join(output_dir, "A1_keyword_clusters.json")
    path_a2 = os.path.join(output_dir, "A2_opportunity_report.json")
    path_a2_5 = os.path.join(output_dir, "A2_5_external_insight_context.json")
    path_a2_5_sources = os.path.join(output_dir, "A2_5_structured_sources.json")
    path_a3 = os.path.join(output_dir, "A3_final_outline.md")
    path_a4 = os.path.join(output_dir, "A4_FINAL_ARTICLE.md")
    path_a4_quality = os.path.join(output_dir, "A4_quality_report.json")
    path_a5_meta = os.path.join(output_dir, "A5_FINAL_METADATA.json")
    path_a5_schema = os.path.join(output_dir, "A5_FINAL_SCHEMA.jsonld")
    path_a6_geo = os.path.join(output_dir, "A6_GEO_SNIPPETS.json")

    # State
    a0_data, a1_data, a2_data = {}, {}, {}
    a0_5_client_insight_str = ""
    a2_5_external_insight_str = ""
    external_sources_structured = []
    a2_5_google_snippets = []
    internal_links_inventory = []  # <<< NUEVO v9.4
    a3_outline_body, a3_h1 = "", "Artículo sin Título"
    a3_faqs = []
    client_site_data_list = []
    search_results = {}

    full_article_md = ""
    best_title = ""
    best_meta = ""
    a5_schema_data = {}
    a6_geo_data = {}

    quality_report = {}  # 🟢 FIX v9.6: Inicializar para evitar error al final

    BANNED_PHRASE = "las organizaciones que integran"  # Solo para chequeo ligero

    try:
        async with aiohttp.ClientSession(headers=HEADERS) as session:
            # --- AGENTE 0: Descubrimiento ---
            logger.info(f"🕵️ AGENTE 0: Descubrimiento para {url}")
            all_urls = await crawl_site(url, max_pages=50)

            # --- 🟢 NUEVO (v9.4): Construir Inventario de Links Internos ---
            insight_indicators = [
                "/blog",
                "/insights",
                "/articulos",
                "/novedades",
                "/casos-de-estudio",
                "/casos",
                "/proyectos",
                "/clientes",
                "/servicios",
                "/soluciones",
                "/plataformas",
            ]
            base_domain = urlparse(url).netloc
            all_internal_links = []
            for u in all_urls:
                try:
                    parsed = urlparse(u)
                    parsed_path = parsed.path.lower()
                    # Asegurarse que es del mismo dominio y está en un path de "insights"
                    if parsed.netloc.endswith(base_domain) and any(
                        indicator in parsed_path for indicator in insight_indicators
                    ):
                        # Excluir las páginas de índice (ej. /blog/) y incluir posts (ej. /blog/mi-post)
                        if parsed_path.count("/") > 1 or (
                            parsed_path.count("/") == 1
                            and not parsed_path.endswith("/")
                        ):
                            all_internal_links.append(u)
                except Exception:
                    continue
            internal_links_inventory = list(dict.fromkeys(all_internal_links))[
                :20
            ]  # Limitar a 20 para el prompt
            logger.info(
                f"✅ v9.4: Encontrados {len(internal_links_inventory)} links internos (posts/servicios) para inyección."
            )

            urls_to_analyze = filter_target_urls(all_urls, url, max_sample=3)

            homepage_data = await fetch_and_parse(session, url)
            if urls_to_analyze:
                client_site_data_list = await asyncio.gather(
                    *[fetch_and_parse(session, u) for u in urls_to_analyze if u != url]
                )

            combined_input_data = {
                "homepage_context": homepage_data,
                "client_case_studies_services": client_site_data_list,
            }
            a0_5_client_insight_str = json.dumps(
                combined_input_data, indent=2, ensure_ascii=False
            )

            with open(path_a0_5_context, "w", encoding="utf-8") as f:
                f.write(a0_5_client_insight_str)
            logger.info(f"✅ Contexto cliente guardado: {path_a0_5_context}")

            a0_text = await run_agent_llm(
                AGENT_0_DISCOVERY_PROMPT, a0_5_client_insight_str, use_json_output=True
            )
            a0_data = parse_json_from_llm(a0_text) or {}

            with open(path_a0, "w", encoding="utf-8") as f:
                json.dump(a0_data, f, indent=2, ensure_ascii=False)

            logger.info(
                f"✅ AGENTE 0: Tema='{a0_data.get('main_topic')}' | Audiencia='{a0_data.get('target_audience')}'"
            )

            # --- AGENTE 1: Keywords ---
            logger.info("🧠 AGENTE 1: Generando keywords")
            prompt_a1 = fill_prompt(
                AGENT_1_KEYWORD_PROMPT,
                {
                    "AUDIENCIA_TARGET": a0_data.get("target_audience") or "",
                    "TEMA_PRINCIPAL": a0_data.get("main_topic") or "",
                },
            )
            a1_text = await run_agent_llm(prompt_a1, "", use_json_output=True)
            a1_data = parse_json_from_llm(a1_text) or {}

            with open(path_a1, "w", encoding="utf-8") as f:
                json.dump(a1_data, f, indent=2, ensure_ascii=False)

            primary_keyword = (
                a1_data.get("palabra_clave_principal")
                or a0_data.get("main_topic")
                or "transformación digital"
            )
            logger.info(f"✅ AGENTE 1: Keyword Principal='{primary_keyword}'")

            # --- AGENTE 2: Competencia ---
            if GOOGLE_API_KEY and CSE_ID:
                logger.info("📈 AGENTE 2: Analizando SERPs")
                search_results = await run_google_search(
                    primary_keyword, GOOGLE_API_KEY, CSE_ID
                )

                prompt_a2 = fill_prompt(
                    AGENT_2_COMPETITOR_PROMPT, {"KEYWORD_PRINCIPAL": primary_keyword}
                )
                a2_text = await run_agent_llm(
                    prompt_a2,
                    json.dumps(search_results, ensure_ascii=False),
                    use_json_output=True,
                )
                a2_data = parse_json_from_llm(a2_text) or {}

                with open(path_a2, "w", encoding="utf-8") as f:
                    json.dump(a2_data, f, indent=2, ensure_ascii=False)

                logger.info("✅ AGENTE 2: Análisis SERP completado")
            else:
                logger.warning(
                    "⚠️ GOOGLE_API_KEY/CSE_ID no configurados. Omitiendo Agente 2."
                )
                a2_data = {
                    "must_cover_elements": [primary_keyword],
                    "content_gaps_differentiators": ["Caso de estudio práctico"],
                    "entidades_mencionadas_repetidamente": [],
                }
                search_results = {"items": []}

            # --- 🟢 AGENTE 2.5: Insights Externos (v9.7) 🟢 ---
            logger.info(
                "🔎 AGENTE 2.5: Buscando insights externos (v9.7 - Bucle Garantizado)"
            )
            (
                a2_5_external_insight_str,
                external_sources_structured,
                a2_5_google_snippets,
            ) = await fetch_external_insight_context(
                session, primary_keyword, GOOGLE_API_KEY, CSE_ID
            )

            try:
                external_data = json.loads(a2_5_external_insight_str)
                with open(path_a2_5, "w", encoding="utf-8") as f:
                    json.dump(external_data, f, indent=2, ensure_ascii=False)
            except Exception:
                with open(path_a2_5, "w", encoding="utf-8") as f:
                    f.write(a2_5_external_insight_str)

            with open(path_a2_5_sources, "w", encoding="utf-8") as f:
                json.dump(external_sources_structured, f, indent=2, ensure_ascii=False)

            logger.info(
                f"✅ AGENTE 2.5: {len(external_sources_structured)} fuentes (scrape) | {len(a2_5_google_snippets)} (snippets)"
            )

            # --- 🔴 AGENTE 3: Outline (v9.5) 🔴 ---
            logger.info("🏗️ AGENTE 3: Generando outline")

            try:
                client_insight_data = json.loads(a0_5_client_insight_str)
            except Exception:
                client_insight_data = {
                    "error": "Parse failed",
                    "raw": a0_5_client_insight_str,
                }

            try:
                external_insight_data = json.loads(a2_5_external_insight_str)
            except Exception:
                external_insight_data = {
                    "error": "Parse failed",
                    "raw": a2_5_external_insight_str,
                }

            user_data_a3_dict = {
                "JSON_CLUSTERS": a1_data,
                "OPPORTUNITY_REPORT": a2_data,
                "CLIENT_INSIGHT_CONTEXT": client_insight_data,
                "EXTERNAL_INSIGHT_CONTEXT": external_insight_data,
                "GOOGLE_SNIPPET_CONTEXT": a2_5_google_snippets,  # <<< NUEVO
            }
            user_data_a3_str = json.dumps(
                user_data_a3_dict, indent=2, ensure_ascii=False
            )

            system_prompt_a3 = fill_prompt(
                AGENT_3_OUTLINE_PROMPT, {"KEYWORD_PRINCIPAL": primary_keyword}
            )

            a3_outline_md_raw = await run_agent_llm(
                system_prompt_a3,
                user_data_a3_str,
                use_json_output=False,
                max_tokens_override=3072,
            )

            outline_info = extract_from_outline(a3_outline_md_raw)
            a3_h1 = outline_info.get("h1") or "Artículo sin Título"
            a3_outline_body = outline_info.get("outline_body") or ""
            a3_faqs = outline_info.get("faqs") or []

            if a3_h1 == "Artículo sin Título" or not a3_outline_body:
                logger.error(
                    f"❌ AGENTE 3: Outline inválido. Preview:\n{a3_outline_md_raw[:800]}"
                )
                raise Exception("Agente 3 falló: H1 o body vacíos")

            with open(path_a3, "w", encoding="utf-8") as f:
                f.write(f"# {a3_h1}\n\n{a3_outline_body}")

            logger.info(f"✅ AGENTE 3: H1='{a3_h1}' | {len(a3_faqs)} FAQs")

            # --- 🔴 AGENTE 4: Redacción (Pipeline v9.5) 🔴 ---
            logger.info("✍️ AGENTE 4: Redacción sección por sección (v9.5)")

            sections = re.split(
                r"(^\s*#{2,4}\s+.*)", a3_outline_body, flags=re.MULTILINE
            )
            full_article_parts = []
            full_article_parts.append(f"# {a3_h1}\n\n")

            base_domain = urlparse(url).netloc.lstrip("www.")
            base_url_for_links = urlparse(url).netloc

            dynamic_source_links = [
                b.get("url")
                for b in client_site_data_list
                if b.get("url") and base_domain in b.get("url")
            ]

            external_source_urls = [
                s.get("url") for s in external_sources_structured if s.get("url")
            ]
            serp_urls = [
                it.get("link")
                for it in search_results.get("items", [])
                if it.get("link")
            ]
            all_external_urls = list(dict.fromkeys(external_source_urls + serp_urls))

            # Contexto base para todos los agentes (v9.5)
            base_context = (
                f"URL Base: {base_url_for_links}\n\n"
                f"CLIENT_INSIGHT_CONTEXT (Datos Cliente):\n{a0_5_client_insight_str}\n\n"
                f"🟢 INVENTARIO DE LINKS INTERNOS (Post/Servicios del Sitio v9.4):\n"  # <<< NUEVO v9.4
                f"{json.dumps(internal_links_inventory, ensure_ascii=False, indent=2)}\n\n"  # <<< NUEVO v9.4
                f"EXTERNAL_INSIGHT_CONTEXT (Datos Google Scrapeados):\n{a2_5_external_insight_str}\n\n"
                f"🟢 GOOGLE_SNIPPET_CONTEXT (Datos Google SIN Scrapear v9.3):\n"
                f"{json.dumps(a2_5_google_snippets, ensure_ascii=False, indent=2)}\n\n"
                f"🟢 FUENTES EXTERNAS PARA CITAR (Datos Scrapeados v9.1):\n"
                f"{json.dumps(external_sources_structured, ensure_ascii=False, indent=2)}\n\n"
                f"Keywords: {', '.join([k.get('keyword') if isinstance(k, dict) else k for k in a1_data.get('cluster_primario', [])][:3]) if a1_data else ''}\n"
                f"Autoridades E-E-A-T: {json.dumps(a2_data.get('entidades_mencionadas_repetidamente', []), ensure_ascii=False)}\n"
                f"Enlaces Internos (Propios): {json.dumps(dynamic_source_links, ensure_ascii=False)}\n\n"
                f"Autor: {author_name} ({author_url})\n\n"
            )

            current_heading_context = f"Contexto H1: {a3_h1}"
            first_prose_written = ""

            for i, section_text in enumerate(sections):
                section_text = section_text.strip()
                if not section_text:
                    continue

                is_heading = section_text.startswith("##")

                if is_heading:
                    current_heading_context = section_text
                    full_article_parts.append(f"{section_text}\n\n")
                    logger.info(f"   📍 Procesando: {section_text[:70]}...")
                else:
                    instructions_raw = section_text
                    instructions_upper = instructions_raw.upper()

                    is_robot_task = False
                    robot_prompt_system = AGENT_4_ROBO_REPLACER_PROMPT
                    robot_user_message = ""

                    # --- v9.0 "Robot-First" Logic ---
                    if "[TABLA DE KPIS]" in instructions_upper:
                        logger.info("   🤖 Robot: [TABLA DE KPIS]")
                        is_robot_task = True
                        robot_user_message = (
                            f"MARCADOR: `[TABLA DE KPIS]`\n"
                            f"TAREA: Genera tabla Markdown con (KPI | Qué mide | Benchmark 2025 | Fuente).\n"
                            f"Incluye 3-4 filas (ej. Adopción IA, ROI Automatización).\n"
                            f"🟢 CRÍTICO: CITA benchmarks de 'FUENTES EXTERNAS PARA CITAR' (P1) o 'GOOGLE_SNIPPET_CONTEXT' (P2) con URL completa en cada fila.\n"
                            f"Formato: `| KPI | Descripción | 45% en 2025 | [Fuente](URL) |`\n"
                            f"Si AMBOS están vacíos, escribe: 'No hay benchmarks externos disponibles.'"
                        )

                    elif "[CHECKLIST DE IMPLEMENTACIÓN]" in instructions_upper:
                        logger.info("   🤖 Robot: [CHECKLIST]")
                        is_robot_task = True
                        robot_user_message = (
                            f"MARCADOR: `[CHECKLIST DE IMPLEMENTACIÓN]`\n"
                            f"TAREA: Lista Markdown de 6-8 pasos numerados.\n"
                            f"Ejemplo: 1. Definir Visión, 2. Análisis Situacional, 3. Estrategia Digital..."
                        )

                    elif "[LISTA DE FUENTES CLAVE]" in instructions_upper:
                        logger.info("   🤖 Robot: [FUENTES CLAVE]")
                        is_robot_task = True
                        robot_user_message = (
                            f"MARCADOR: `[LISTA DE FUENTES CLAVE]`\n"
                            f"🟢 TAREA CRÍTICA: Lista TODAS las URLs de 'FUENTES EXTERNAS PARA CITAR' (P1) y 'GOOGLE_SNIPPET_CONTEXT' (P2).\n"
                            f"Formato: `* [Título de Fuente](URL completa)`\n"
                            f"DEBES incluir TODAS las fuentes. Si está vacío, no escribas nada."
                        )

                    elif "[BIOGRAFÍA DEL AUTOR]" in instructions_upper:
                        logger.info("   🤖 Robot: [BIOGRAFÍA]")
                        is_robot_task = True
                        try:
                            import locale

                            try:
                                locale.setlocale(locale.LC_TIME, "es_ES.UTF-8")
                            except locale.Error:
                                try:
                                    locale.setlocale(locale.LC_TIME, "es_AR.UTF-8")
                                except locale.Error:
                                    locale.setlocale(locale.LC_TIME, "")
                            today_formatted = datetime.now().strftime("%d de %B de %Y")
                        except Exception:
                            today_formatted = datetime.now().strftime("%Y-%m-%d")

                        robot_user_message = (
                            f"MARCADOR: `[BIOGRAFÍA DEL AUTOR]`\n"
                            f"TAREA: Biografía con fecha de actualización.\n"
                            f"Formato:\n"
                            f"*(Última actualización: {today_formatted})*\n\n"
                            f"Redactado por **{author_name}**, [credencial]. "
                            f"Experto en {a0_data.get('main_topic', 'estrategia digital')}. "
                            f"[LinkedIn]({author_url})."
                        )

                    # --- Ejecutar Tareas ---
                    if is_robot_task:
                        written_content = await run_agent_llm(
                            AGENT_4_ROBO_REPLACER_PROMPT,
                            f"{base_context}\n\n{robot_user_message}",
                            use_json_output=False,
                        )
                        if not written_content:
                            logger.error(
                                f"   ❌ Robot falló. Usando fallback (instrucciones)."
                            )
                            written_content = instructions_raw
                        full_article_parts.append(f"{written_content}\n\n")

                    # Tarea de Prosa (A4.1)
                    else:
                        logger.info(f"   ✍️ Prosa: {current_heading_context[:70]}...")

                        is_faq_task = "[RESPUESTA_FAQ:" in instructions_upper

                        if is_faq_task:
                            prose_user_message = (
                                f"TAREA: Respuesta experta (<= 90 palabras).\n"
                                f"PREGUNTA: {current_heading_context}\n"
                                f"INSTRUCCIÓN: {instructions_raw}\n"
                                f"NO repitas la pregunta. NO uses markdown."
                            )
                        else:
                            prose_user_message = (
                                f"Contexto Sección (NO REPETIR): {current_heading_context}\n"
                                f"Instrucciones:\n{instructions_raw}\n\n"
                                f"🟢 CRÍTICO (v9.5): ¡NO INVENTES DATOS! Usa solo datos de los contextos. CITA fuentes externas (Regla 5) Y enlaces internos (Regla 6b).\n\n"
                                f"Escribe SOLO prosa."
                            )

                        prose_system_prompt = (
                            f"{base_context}\n{AGENT_4_PROSE_WRITER_PROMPT}"
                        )

                        # (v9.2) Sin reintentos, confiar en el LLM
                        written_content = await run_agent_llm(
                            prose_system_prompt,
                            prose_user_message,
                            use_json_output=False,
                        )

                        if not written_content:
                            logger.error(
                                f"   ❌ Prosa falló. Usando fallback (instrucciones)."
                            )
                            written_content = (
                                instructions_raw  # (v9.2) Fallback a instrucciones
                            )

                        if (
                            i == 1 and not first_prose_written
                        ):  # (v8.0) i==1 es la intro
                            first_prose_written = written_content

                        full_article_parts.append(f"{written_content}\n\n")

            # --- 🔴 FIN: BUCLE AGENTE 4 (v9.5) 🔴 ---

            # Unir artículo
            article_body_md = "".join(full_article_parts)

            if not article_body_md.strip():
                raise Exception("AGENTE 4: Artículo vacío")

            # --- 🟢 Verificación de Calidad de Citas ---
            logger.info("🔍 Verificando calidad de citas...")
            citation_quality = check_citation_quality(
                article_body_md, external_sources_structured
            )

            quality_report = {
                "has_citations": citation_quality["has_citations"],
                "citation_count": citation_quality["citation_count"],
                "total_external_sources_found": citation_quality[
                    "total_external_sources_found"
                ],
                "missing_sources": citation_quality["missing_sources"],
                "quality_score_percent": (
                    citation_quality["citation_count"]
                    / max(1, citation_quality["total_external_sources_found"])
                )
                * 100,
            }

            with open(path_a4_quality, "w", encoding="utf-8") as f:
                json.dump(quality_report, f, indent=2, ensure_ascii=False)

            if not citation_quality["has_citations"] and external_sources_structured:
                logger.warning(
                    f"⚠️ ADVERTENCIA: Artículo SIN CITAS a fuentes externas ({citation_quality['total_external_sources_found']} fuentes encontradas pero no usadas)"
                )
            else:
                logger.info(
                    f"✅ Calidad de citas: {quality_report['quality_score_percent']:.1f}% ({citation_quality['citation_count']} citas)"
                )

            if citation_quality["missing_sources"]:
                logger.warning(
                    f"⚠️ {len(citation_quality['missing_sources'])} fuentes mencionadas sin enlazar"
                )

            # --- AGENTE 6: GEO Snippet ---
            logger.info("🌍 AGENTE 6: Generando GEO snippet")

            intro_text_for_a6 = a3_h1
            if first_prose_written and not first_prose_written.startswith("["):
                intro_text_for_a6 = (
                    f"H1: {a3_h1}\n\nIntro:\n{first_prose_written[:500]}"
                )
            else:
                logger.warning("⚠️ No hay intro de prosa. Usando solo H1.")

            a6_text = await run_agent_llm(
                AGENT_6_GEO_SNIPPET_PROMPT, intro_text_for_a6, use_json_output=True
            )
            a6_geo_data = parse_json_from_llm(a6_text) or {}

            # Refinar bullets con datos reales
            if a6_geo_data.get("citable_bullets"):
                logger.info("   🔄 Refinando bullets GEO...")
                refinement_message = (
                    f"H1: {a3_h1}\n"
                    f"Bullets preliminares: {json.dumps(a6_geo_data.get('citable_bullets'))}\n"
                    f"Datos Cliente: {a0_5_client_insight_str}\n"
                    f"Datos Externos (Scrape): {a2_5_external_insight_str}\n"
                    f"Datos Externos (Snippets): {json.dumps(a2_5_google_snippets, ensure_ascii=False)}\n\n"
                    f"TAREA: Reescribe bullets usando datos específicos de los tres contextos."
                )
                refined_bullets_text = await run_agent_llm(
                    AGENT_6_GEO_SNIPPET_PROMPT, refinement_message, use_json_output=True
                )
                refined_bullets_data = parse_json_from_llm(refined_bullets_text)
                if refined_bullets_data and refined_bullets_data.get("citable_bullets"):
                    a6_geo_data["citable_bullets"] = refined_bullets_data[
                        "citable_bullets"
                    ]
                    logger.info("   ✅ Bullets refinados")

            with open(path_a6_geo, "w", encoding="utf-8") as f:
                json.dump(a6_geo_data, f, indent=2, ensure_ascii=False)

            logger.info("✅ AGENTE 6: Snippet GEO guardado")

            # Añadir snippet GEO al artículo
            geo_snippet_md = ""
            if a6_geo_data.get("geo_snippet"):
                geo_snippet_md += (
                    f"**Resumen (Snippet):** {a6_geo_data['geo_snippet']}\n\n"
                )
            if a6_geo_data.get("citable_bullets"):
                geo_snippet_md += "**Puntos Clave (Citables):**\n"
                for bullet in a6_geo_data["citable_bullets"]:
                    geo_snippet_md += f"- {bullet}\n"
                geo_snippet_md += "\n---\n\n"

            h1_pattern = re.compile(
                r"(^\s*#\s+.*|.*\n(?:={3,}|-{3,})\s*$\n)", re.MULTILINE
            )
            h1_match_in_body = h1_pattern.search(article_body_md)

            if h1_match_in_body:
                h1_end_pos = h1_match_in_body.end()
                full_article_md = (
                    article_body_md[:h1_end_pos]
                    + f"\n{geo_snippet_md}\n"
                    + article_body_md[h1_end_pos:]
                )
            else:
                full_article_md = f"# {a3_h1}\n\n{geo_snippet_md}\n{article_body_md}"

            with open(path_a4, "w", encoding="utf-8") as f:
                f.write(full_article_md)

            logger.info("✅ AGENTE 4/6: Artículo final guardado")

            # --- AGENTE 5: Metadatos y Schema ---
            logger.info("🚀 AGENTE 5: Generando metadatos")

            prompt_titles = fill_prompt(
                AGENT_5_TITLE_PROMPT,
                {
                    "primary_keyword": primary_keyword or "",
                    "article_h1": a3_h1 or "",
                    "company_desc": a0_data.get("company_description")
                    or "Ceibo Digital",
                    "target_audience": a0_data.get("target_audience") or "",
                },
            )
            a5_titles_text = await run_agent_llm(
                prompt_titles, "", use_json_output=True
            )
            a5_titles_data = parse_json_from_llm(a5_titles_text) or {}

            prompt_metas = fill_prompt(
                AGENT_5_META_PROMPT,
                {"primary_keyword": primary_keyword or "", "article_h1": a3_h1 or ""},
            )
            a5_metas_text = await run_agent_llm(prompt_metas, "", use_json_output=True)
            a5_metas_data = parse_json_from_llm(a5_metas_text) or {}

            # Seleccionar mejores
            best_title = (
                a5_titles_data.get("titles", [{}])[0].get("title")
                if (a5_titles_data and a5_titles_data.get("titles"))
                else a3_h1
            )
            best_meta = a6_geo_data.get("geo_snippet") or (
                a5_metas_data.get("metas", [{}])[0].get("desc")
                if (a5_metas_data and a5_metas_data.get("metas"))
                else a3_h1[:150]
            )

            if best_title and len(best_title) > 60:
                best_title = best_title[:57].rsplit(" ", 1)[0] + "..."
            if best_meta and len(best_meta) > 160:
                best_meta = best_meta[:157].rsplit(" ", 1)[0] + "..."

            final_metadata = {
                "selected_title": best_title,
                "selected_meta_description": best_meta,
                "title_options": a5_titles_data.get("titles", [])
                if a5_titles_data
                else [],
                "meta_options": a5_metas_data.get("metas", []) if a5_metas_data else [],
            }

            with open(path_a5_meta, "w", encoding="utf-8") as f:
                json.dump(final_metadata, f, indent=2, ensure_ascii=False)

            logger.info("✅ AGENTE 5: Metadatos guardados")

            # Schema JSON-LD
            base_url_schema = "https://" + base_url_for_links
            slug = (
                re.sub(
                    r"[^a-z0-9]+", "-", (primary_keyword or "article").lower()
                ).strip("-")
                or "article"
            )

            prompt_schema = fill_prompt(
                AGENT_5_SCHEMA_PROMPT,
                {
                    "article_url": f"{base_url_schema}/insights/{slug}",
                    "article_h1": a3_h1,
                    "meta_description": best_meta,
                    "author_name": author_name,
                    "author_url": author_url,
                    "publisher_name": "Ceibo Digital",  # Asumido, se puede cambiar
                    "publisher_url": base_url_schema,
                    "publisher_logo_url": f"{base_url_schema}/logo.png",  # Asumido
                    "faq_list": "\n".join([f"- {q}" for q in a3_faqs]) or "",
                    "today_date": datetime.now().isoformat(),
                },
            )

            # --- 🔴 FIX (v9.1): Aumentar tokens para Schema ---
            a5_schema_text = await run_agent_llm(
                prompt_schema, "", use_json_output=True, max_tokens_override=4096
            )
            a5_schema_data = parse_json_from_llm(a5_schema_text) or {}

            if a5_schema_data and (
                a5_schema_data.get("@graph") or a5_schema_data.get("@context")
            ):
                with open(path_a5_schema, "w", encoding="utf-8") as f:
                    json.dump(a5_schema_data, f, indent=2, ensure_ascii=False)
                logger.info("✅ AGENTE 5: Schema JSON-LD guardado")
            else:
                logger.error(
                    f"❌ AGENTE 5: Fallo schema. Respuesta: {a5_schema_text[:500]}"
                )

    except Exception as e:
        logger.exception(f"💥 Error fatal en pipeline: {e}")
        print(f"\n❌ ERROR FATAL:\n{e}\n")
        return

    # --- RESUMEN FINAL ---
    print("\n" + "=" * 80)
    print("✅ FLUJO COMPLETO TERMINADO (v9.8 - API Timeout Fix)")
    print(f"📁 Resultados en: {output_dir}")
    print("=" * 80)

    print("\n📊 REPORTE DE CALIDAD:")
    print(f"   • Citas detectadas: {quality_report.get('citation_count', 0)}")
    print(
        f"   • Fuentes externas (scrape): {quality_report.get('total_external_sources_found', 0)}"
    )
    print(f"   • Fuentes externas (snippets): {len(a2_5_google_snippets)}")
    print(
        f"   • Score de calidad (vs scrape): {quality_report.get('quality_score_percent', 0):.1f}%"
    )

    if quality_report.get("missing_sources"):
        print(
            f"   ⚠️ Fuentes mencionadas sin enlazar: {len(quality_report['missing_sources'])}"
        )
        for missing in quality_report["missing_sources"][:3]:
            print(f"     - {missing.get('title', 'N/A')}")

    print("\n📄 PREVIEW ARTÍCULO:")
    try:
        preview_lines = full_article_md.split("\n")[:30]
        print("\n".join(preview_lines))
        print("...")
    except Exception:
        print("(sin preview)")

    print("\n🎯 METADATOS:")
    print(f"   • Título: {best_title}")
    print(f"   • Meta: {best_meta[:100]}...")

    print("\n🔗 ARCHIVOS GENERADOS:")
    print(f"   • Artículo final: {path_a4}")
    print(f"   • Reporte calidad: {path_a4_quality}")
    print(f"   • Fuentes estructuradas: {path_a2_5_sources}")
    print(f"   • Metadatos: {path_a5_meta}")
    print(f"   • Schema JSON-LD: {path_a5_schema}")
    print(f"   • GEO Snippets: {path_a6_geo}")

    print("\n" + "=" * 80)


# --- CLI ENTRYPOINT ---

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generador de Contenido IA v9.8 - API Timeout Fix"
    )
    parser.add_argument(
        "url",
        help="URL de la empresa (ej. 'ceibo.digital' o '[https://ceibo.digital](https://ceibo.digital)')",
    )
    parser.add_argument(
        "--author-name",
        default="Equipo Editorial",
        help="Nombre del autor para Schema y biografía",
    )
    parser.add_argument(
        "--author-url",
        default="[https://www.linkedin.com/company/ceibo-digital/](https://www.linkedin.com/company/ceibo-digital/)",
        help="URL de perfil del autor (LinkedIn o bio)",
    )

    args = parser.parse_args()

    # Normalizar URL (v8.1 fix)
    url = (
        args.url
        if args.url.startswith("http")
        else "https://" + args.url.lstrip("www.")
    )
    domain = urlparse(url).netloc.lstrip("www.")
    output_folder = os.path.join("content_production", domain.replace(".", "_"))

    print("\n" + "=" * 80)
    print("🚀 CONTENT GENERATOR v9.8 - API Timeout Fix")
    print("=" * 80)
    print(f"📍 URL objetivo: {url}")
    print(f"👤 Autor: {args.author_name}")
    print(f"📁 Output: {output_folder}")
    print("=" * 80 + "\n")

    try:
        asyncio.run(
            main_pipeline_v9(url, output_folder, args.author_name, args.author_url)
        )
    except KeyboardInterrupt:
        logger.info("\n⚠️ Proceso interrumpido por el usuario")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"💥 Error ejecutando pipeline: {e}")
        sys.exit(1)
