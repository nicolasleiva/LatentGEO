#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
agent5_optimizer.py - Flujo del Agente 5 (Optimización y Schema)

Este script implementa los Agentes 5.1 y 5.2 del manual, además
de un generador de Schema JSON-LD.

Toma el output de 'content_generator_v2.py' (los archivos A0, A1, A3)
y genera los metadatos finales listos para publicar.

Uso:
python agent5_optimizer.py "ruta/a/la_carpeta_de_produccion"

Ejemplo:
python agent5_optimizer.py "content_production/ceibo_digital"
"""

import os
import sys
import json
import argparse
import asyncio
import logging
import re
from datetime import datetime
from dotenv import load_dotenv

# --- Copiamos la misma lógica de LLM de tu content_generator_v2.py ---
# --- para mantener la compatibilidad con NVIDIA / Gemini ---

try:
    from google import genai
    from google.genai import types

    GENAI_AVAILABLE = True
except Exception as e:
    logging.info("google.genai no está instalado: %s", e)
    GENAI_AVAILABLE = False

try:
    from openai import OpenAI as NVOpenAI

    NV_OPENAI_AVAILABLE = True
except Exception as e:
    logging.warning(f"openai NV client no está instalado: {e}")
    NV_OPENAI_AVAILABLE = False

load_dotenv()
# Google / CSE
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# NVIDIA / OpenAI-style integration
NV_API_KEY = os.getenv("NV_API_KEY")
NV_BASE_URL = os.getenv("NV_BASE_URL", "https://integrate.api.nvidia.com/v1")
NV_MODEL = os.getenv("NV_MODEL", "moonshotai/kimi-k2-instruct-0905")
NV_MAX_TOKENS = int(os.getenv("NV_MAX_TOKENS", "4096"))

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("Agent5Optimizer")


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

            # Forzar JSON si se solicita (específico de OpenAI / NVIDIA)
            response_format = (
                {"type": "json_object"} if use_json_output else {"type": "text"}
            )

            completion = nv_client.chat.completions.create(
                model=NV_MODEL,
                messages=messages,
                temperature=0.1,
                top_p=0.9,
                max_tokens=NV_MAX_TOKENS,
                response_format=response_format,  # <--- Forzar JSON
            )

            content = completion.choices[0].message.content

            if content is None:
                return str(completion).strip()

            return str(content).strip()

        except Exception as e:
            logger.warning(f"NV/OpenAI-style client falló: {e}")
            # Si NV falla, intentar con Gemini (fallback)

    # --- Fallback: google.genai (Gemini) si está disponible ---
    if GEMINI_API_KEY and GENAI_AVAILABLE:
        try:
            logger.info("Usando google.genai (Gemini) como fallback...")
            client = genai.Client(api_key=GEMINI_API_KEY)

            model_name = os.getenv(
                "GEMINI_MODEL", "gemini-1.5-pro-latest"
            )  # Usar 1.5 Pro
            if not model_name.startswith("models/"):
                model_name = f"models/{model_name}"

            config = types.GenerationConfig(
                temperature=0.1,
                response_mime_type="application/json"
                if use_json_output
                else "text/plain",
            )

            response = client.models.generate_content(
                model=model_name,
                contents=prompt_text,
                generation_config=config,  # <--- Usar 'generation_config' (sintaxis moderna)
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


def parse_json_from_llm(text: str):
    """
    Función de parseo (inspirada en parse_agent_json_or_raw)
    """
    text = (text or "").strip()
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


# ---
# 🤖 SECCIÓN DE PROMPTS DEL AGENTE 5 (del Manual)
# ---
AGENT_5_TITLE_PROMPT = """
Actúa como un "Experto en Títulos" (Agente 5.1), fusionando la precisión de un Especialista SEO con la creatividad de un Copywriter.

**Contexto:**
* **Palabra Clave Principal:** "{primary_keyword}"
* **Tema del Artículo (H1):** "{article_h1}"
* **Identidad de la Empresa:** "{company_desc}"
* **Audiencia:** "{target_audience}"

**Tarea:**
Genera 5 opciones de títulos (Meta Titles).

**Restricciones:**
1.  Los títulos deben tener **menos de 60 caracteres**.
2.  DEBEN contener la palabra clave principal o una variación muy cercana.
3.  Deben ser altamente persuasivos y generar un alto CTR.
4.  Deben reflejar el tono de la empresa.
5.  Incluye "modificadores de etiqueta de título" (ej. "Guía Definitiva", "[Año]", "Mejores", "Checklist").

**Formato de Salida (JSON):**
{{
  "titles": [
    {{"title": "[Título 1 (<60 chars)]", "char_count": X}},
    {{"title": "[Título 2 (<60 chars)]", "char_count": Y}}
  ]
}}
"""

AGENT_5_META_PROMPT = """
Actúa como un Copywriter SEO experto (Agente 5.2).

**Contexto:**
* **Palabra Clave Principal:** "{primary_keyword}"
* **Título del Artículo (H1):** "{article_h1}"

**Tarea:**
Escribe 3 variaciones de una meta descripción optimizada para SEO.

**Restricciones:**
1.  La longitud debe estar **entre 120 y 160 caracteres**.
2.  DEBE contener la palabra clave principal.
3.  Debe centrarse en los beneficios para el lector y ser altamente persuasiva.
4.  Debe incluir un llamado a la acción (CTA) claro (ej. "Descubre cómo", "Aprende más").

**Formato de Salida (JSON):**
{{
  "metas": [
    {{"desc": "[Meta descripción 1 (120-160 chars)]", "char_count": X}},
    {{"desc": "[Meta descripción 2 (120-160 chars)]", "char_count": Y}}
  ]
}}
"""

AGENT_5_SCHEMA_PROMPT = """
Actúa como un Especialista Técnico SEO experto en Schema.org.
Tu tarea es generar un script JSON-LD completo que combine
los schemas 'Article' y 'FAQPage'.

**Contexto:**
* **URL del Artículo:** "{article_url}"
* **Headline (H1):** "{article_h1}"
* **Meta Description:** "{meta_description}"
* **Nombre del Autor:** "{author_name}"
* **URL del Autor (LinkedIn/Bio):** "{author_url}"
* **Nombre del Publisher (Empresa):** "{publisher_name}"
* **URL del Publisher:** "{publisher_url}"
* **Lista de FAQs (Solo Preguntas):**
{faq_list}

**Instrucciones:**
1.  Crea un objeto `@graph` que contenga dos schemas: `Article` y `FAQPage`.
2.  **Para `Article`:**
    * Usa el H1 como `headline`.
    * Usa la Meta Description como `description`.
    * Usa la fecha de hoy ({today_date}) como `datePublished` y `dateModified`.
    * Crea el `author` y `publisher` como objetos `Person` y `Organization`.
3.  **Para `FAQPage`:**
    * Para cada pregunta en la lista de FAQs, crea una `Question`.
    * **Importante:** Para la `acceptedAnswer`, genera una respuesta corta y experta (1-2 frases) basada en el contexto del H1. No digas "ver arriba".

**Formato de Salida (JSON-LD):**
(Devuelve SOLAMENTE el bloque JSON, nada más)
"""

# ---
# 🚀 FUNCIÓN PRINCIPAL (main_a5)
# ---


def extract_from_outline(outline_md: str) -> dict:
    """Extrae el H1 y las FAQs del esqueleto de Markdown."""
    h1 = "Artículo sin Título"
    faqs = []

    # Extraer H1
    h1_match = re.search(r"^\s*#\s+(.*)", outline_md, re.MULTILINE)
    if h1_match:
        h1 = h1_match.group(1).strip()

    # Extraer FAQs (H3 bajo un H2 de "Preguntas Frecuentes")
    faq_section_match = re.search(
        r"##\s+(Preguntas Frecuentes|FAQ|FAQs)\b.*",
        outline_md,
        re.IGNORECASE | re.DOTALL,
    )
    if faq_section_match:
        faq_text = faq_section_match.group(0)
        # Buscar todos los H3 (###) dentro de esa sección
        faq_matches = re.findall(r"^\s*###\s+(.*)", faq_text, re.MULTILINE)
        faqs = [q.strip().replace("[", "").replace("]", "") for q in faq_matches]

    return {"h1": h1, "faqs": faqs}


async def main_pipeline_a5(report_dir: str, author_name: str, author_url: str):
    """
    Orquesta el flujo del Agente 5.
    """
    logger.info(f"--- 🚀 Iniciando Agente 5 (Optimizador) en: {report_dir} ---")

    # --- 1. Cargar archivos de contexto (A0, A1, A3) ---
    try:
        with open(
            os.path.join(report_dir, "A0_discovery.json"), "r", encoding="utf-8"
        ) as f:
            a0_data = json.load(f)
        with open(
            os.path.join(report_dir, "A1_keyword_clusters.json"), "r", encoding="utf-8"
        ) as f:
            a1_data = json.load(f)
        with open(
            os.path.join(report_dir, "A3_final_outline.md"), "r", encoding="utf-8"
        ) as f:
            a3_outline_md = f.read()
    except FileNotFoundError as e:
        logger.error(f"Error: No se pudo encontrar un archivo necesario: {e.filename}")
        logger.error("Asegúrate de ejecutar 'content_generator_v2.py' primero.")
        return
    except Exception as e:
        logger.error(f"Error al leer archivos de contexto: {e}")
        return

    # --- 2. Extraer contexto clave ---
    primary_keyword = a1_data.get("palabra_clave_principal", "tema principal")
    company_desc = a0_data.get("company_description", "empresa experta")
    target_audience = a0_data.get("target_audience", "público objetivo")
    publisher_name = a0_data.get("publisher_name", "Ceibo Digital")  # Fallback
    publisher_url = a0_data.get(
        "publisher_url", "[https://ceibo.digital/](https://ceibo.digital/)"
    )  # Fallback

    outline_info = extract_from_outline(a3_outline_md)
    article_h1 = outline_info["h1"]
    faq_list = outline_info["faqs"]

    logger.info(f"Contexto cargado: H1='{article_h1}', Keyword='{primary_keyword}'")

    # --- 3. Ejecutar Agente 5.1 (Meta Títulos) ---
    logger.info("--- 🏷️  Agente 5.1: Generando Meta Títulos ---")
    prompt_titles = AGENT_5_TITLE_PROMPT.format(
        primary_keyword=primary_keyword,
        article_h1=article_h1,
        company_desc=company_desc,
        target_audience=target_audience,
    )

    a5_titles_text = await run_agent_llm(prompt_titles, "", use_json_output=True)
    a5_titles_data = parse_json_from_llm(a5_titles_text)
    if not a5_titles_data:
        logger.error("Agente 5.1 (Títulos) falló. Saliendo.")
        return

    output_path_titles = os.path.join(report_dir, "A5_meta_titles.json")
    with open(output_path_titles, "w", encoding="utf-8") as f:
        json.dump(a5_titles_data, f, indent=2, ensure_ascii=False)
    logger.info(f"Títulos guardados en: {output_path_titles}")

    # --- 4. Ejecutar Agente 5.2 (Meta Descripciones) ---
    logger.info("--- ✍️  Agente 5.2: Generando Meta Descripciones ---")
    prompt_metas = AGENT_5_META_PROMPT.format(
        primary_keyword=primary_keyword, article_h1=article_h1
    )

    a5_metas_text = await run_agent_llm(prompt_metas, "", use_json_output=True)
    a5_metas_data = parse_json_from_llm(a5_metas_text)
    if not a5_metas_data:
        logger.error("Agente 5.2 (Metas) falló. Saliendo.")
        return

    output_path_metas = os.path.join(report_dir, "A5_meta_descriptions.json")
    with open(output_path_metas, "w", encoding="utf-8") as f:
        json.dump(a5_metas_data, f, indent=2, ensure_ascii=False)
    logger.info(f"Metas guardadas en: {output_path_metas}")

    # --- 5. Ejecutar Agente 5.X (Schema Generator) ---
    logger.info("--- 🧾 Agente 5.X: Generando Schema JSON-LD (Article + FAQ) ---")

    # Usar la primera meta descripción generada como input
    best_meta_desc = a5_metas_data.get("metas", [{}])[0].get(
        "desc", "Lea nuestro artículo completo."
    )
    # Crear una URL de artículo ficticia
    article_url_slug = re.sub(r"[^a-z0-9]+", "-", primary_keyword.lower()).strip("-")
    article_url = f"{publisher_url}/insights/{article_url_slug}"

    prompt_schema = AGENT_5_SCHEMA_PROMPT.format(
        article_url=article_url,
        article_h1=article_h1,
        meta_description=best_meta_desc,
        author_name=author_name,
        author_url=author_url,
        publisher_name=publisher_name,
        publisher_url=publisher_url,
        faq_list="\n".join([f"- {q}" for q in faq_list]),
        today_date=datetime.now().isoformat(),
    )

    a5_schema_text = await run_agent_llm(prompt_schema, "", use_json_output=True)
    a5_schema_data = parse_json_from_llm(a5_schema_text)
    if not a5_schema_data:
        logger.error("Agente 5.X (Schema) falló. Saliendo.")
        logger.error(f"Raw output: {a5_schema_text}")
        return

    output_path_schema = os.path.join(report_dir, "A5_schema.jsonld")
    with open(output_path_schema, "w", encoding="utf-8") as f:
        json.dump(a5_schema_data, f, indent=2, ensure_ascii=False)
    logger.info(f"Schema guardado en: {output_path_schema}")

    logger.info("--- ✅ ¡Flujo del Agente 5 Completado! ---")
    print("\n" + "=" * 50)
    print("RESUMEN DE OPTIMIZACIÓN:")
    print(f"Mejor Título: {a5_titles_data.get('titles', [{}])[0].get('title')}")
    print(f"Mejor Meta: {a5_metas_data.get('metas', [{}])[0].get('desc')}")
    print(f"Schema Generado: Ver {output_path_schema}")
    print("=" * 50)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Optimizador de Contenido (Agente 5)")
    parser.add_argument(
        "report_directory",
        help="Ruta a la carpeta de producción (ej. 'content_production/ceibo_digital')",
    )
    parser.add_argument(
        "--author-name",
        default="Equipo de Ceibo Digital",
        help="Nombre del autor para el Schema.",
    )
    parser.add_argument(
        "--author-url",
        default="[https://www.linkedin.com/company/ceibo-digital/](https://www.linkedin.com/company/ceibo-digital/)",
        help="URL de perfil del autor (ej. LinkedIn).",
    )

    args = parser.parse_args()

    if not os.path.isdir(args.report_directory):
        logger.error(f"Error: El directorio no existe: {args.report_directory}")
        sys.exit(1)

    try:
        asyncio.run(
            main_pipeline_a5(args.report_directory, args.author_name, args.author_url)
        )
    except Exception as e:
        logger.exception(f"Error fatal en el pipeline del Agente 5: {e}")
