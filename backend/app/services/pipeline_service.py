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
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urlparse
from datetime import datetime
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class PipelineService:
    """
    Servicio de Orquestación Pipeline.

    Coordina Agente 1, Agente 2, búsqueda de competidores,
    y generación de reportes completos.
    """

    # --- PROMPTS DE AGENTES ---

    EXTERNAL_ANALYSIS_PROMPT = """
Eres un analista de inteligencia de mercado y experto en SEO/GEO. Recibirás un JSON de una auditoría web local ('target_audit').
Tu trabajo es (1) clasificar el sitio y (2) generar un plan de búsqueda (queries) para recopilar inteligencia externa.

Tu respuesta DEBE ser un único bloque de código JSON con la siguiente estructura:
{
  "is_ymyl": (bool),
  "business_type": (string: "SOFTWARE", "LOCAL_SERVICE", "ECOMMERCE", "OTHER"),
  "category": (string),
  "queries_to_run": [
    { "id": "competitors", "query": (string) },
    { "id": "authority", "query": (string) }
  ]
}

Pasos a seguir:
1.  **Clasificar YMYL:** Determina si es "YMYL" (Your Money Your Life).
2.  **Identificar Tipo de Negocio y Categoría:** Analiza el contenido para definir qué es.
3.  **Generar Query de Competidores (SIMPLIFICADA):**
    *   Simplemente busca la **CATEGORÍA PRINCIPAL** del negocio.
    *   Ejemplo: "AI coding assistant", "Plomero en Madrid", "Zapatillas de running".
    *   **NO** agregues palabras como "pricing", "software", "best", "top", "alternatives".
    *   **EXCEPCIÓN:** Si es un negocio local, SIEMPRE incluye la ciudad/país.
    *   El sistema se encargará de filtrar los resultados basura (blogs, directorios, etc.).
4.  **Generar Query de Autoridad:** '"[dominio]" -site:[dominio]'.

JSON de entrada:
"""

    PAGESPEED_ANALYSIS_PROMPT = """
Eres un experto en Web Performance Optimization (WPO), Core Web Vitals y experiencia de usuario.
Analiza los siguientes datos crudos de PageSpeed Insights (Mobile y Desktop) para el sitio auditado.

Tu objetivo es generar un "Análisis Ejecutivo de Rendimiento Web" en formato Markdown que sea:
- **Completo**: Cubre todas las métricas clave y su impacto en el negocio
- **Ejecutivo**: Lenguaje claro, orientado a decisiones y ROI
- **Accionable**: Recomendaciones priorizadas con impacto estimado

Estructura del reporte Markdown:

# Análisis de Rendimiento Web (PageSpeed Insights)

## 📊 Resumen Ejecutivo
* **Veredicto General**: Califica el rendimiento global (Excelente/Bueno/Necesita Mejora/Crítico)
* **Impacto en el Negocio**: Explica cómo el rendimiento actual afecta conversiones, SEO y experiencia de usuario
* **Prioridad de Acción**: Indica si requiere atención inmediata, planificada o monitoreo

## 1. Puntuaciones Generales

| Dispositivo | Puntuación | Evaluación | Impacto SEO |
|-------------|------------|------------|-------------|
| Mobile      | XX/100     | [Estado]   | [Alto/Medio/Bajo] |
| Desktop     | XX/100     | [Estado]   | [Alto/Medio/Bajo] |

**Interpretación**:
* 90-100: Excelente - Rendimiento óptimo
* 50-89: Necesita mejora - Oportunidades de optimización significativas
* 0-49: Pobre - Requiere atención inmediata

**Análisis**: [Explica la diferencia Mobile vs Desktop y su relevancia para el negocio]

## 2. Core Web Vitals - Métricas de Experiencia Real

### Largest Contentful Paint (LCP) - Velocidad de Carga Percibida
* **Mobile**: X.Xs | **Desktop**: X.Xs
* **Estado**: ✅ Aprobado / ⚠️ Necesita Mejora / ❌ Reprobado
* **Umbral**: Bueno ≤ 2.5s | Necesita Mejora ≤ 4.0s | Pobre > 4.0s
* **Impacto**: [Explica cómo afecta la percepción de velocidad y tasa de rebote]

### Interaction to Next Paint (INP) - Capacidad de Respuesta
* **Mobile**: XXXms | **Desktop**: XXXms
* **Estado**: ✅ Aprobado / ⚠️ Necesita Mejora / ❌ Reprobado
* **Umbral**: Bueno ≤ 200ms | Necesita Mejora ≤ 500ms | Pobre > 500ms
* **Impacto**: [Explica cómo afecta la interactividad y frustración del usuario]

### Cumulative Layout Shift (CLS) - Estabilidad Visual
* **Mobile**: X.XXX | **Desktop**: X.XXX
* **Estado**: ✅ Aprobado / ⚠️ Necesita Mejora / ❌ Reprobado
* **Umbral**: Bueno ≤ 0.1 | Necesita Mejora ≤ 0.25 | Pobre > 0.25
* **Impacto**: [Explica cómo afecta la usabilidad y clics accidentales]

**Evaluación Core Web Vitals**: [Indica si el sitio pasa o falla la evaluación general]

## 3. Métricas de Rendimiento Adicionales

### First Contentful Paint (FCP)
* **Mobile**: X.Xs | **Desktop**: X.Xs
* **Significado**: Tiempo hasta que aparece el primer contenido visual

### Speed Index
* **Mobile**: X.Xs | **Desktop**: X.Xs
* **Significado**: Velocidad con la que se muestra el contenido visible

### Total Blocking Time (TBT)
* **Mobile**: XXXms | **Desktop**: XXXms
* **Significado**: Tiempo total que el hilo principal está bloqueado

### Time to Interactive (TTI)
* **Mobile**: X.Xs | **Desktop**: X.Xs
* **Significado**: Tiempo hasta que la página es completamente interactiva

## 4. Oportunidades de Mejora Priorizadas

### 🔴 Prioridad Alta (Impacto Crítico)
[Lista las 3 oportunidades con mayor ahorro potencial]

**1. [Nombre de la oportunidad]**
* **Ahorro estimado**: X.Xs
* **Impacto**: [Alto/Medio/Bajo]
* **Qué es**: [Explicación breve y clara]
* **Cómo solucionarlo**: [Pasos concretos y accionables]
* **Recursos necesarios**: [Estimación de esfuerzo: Bajo/Medio/Alto]

### 🟡 Prioridad Media (Mejoras Significativas)
[Lista 2-3 oportunidades adicionales importantes]

### 🟢 Prioridad Baja (Optimizaciones Incrementales)
[Lista otras oportunidades menores]

## 5. Diagnóstico Técnico

### Recursos y Carga
* **Tamaño total de la página**: XXX KB
* **Número de solicitudes**: XXX
* **Recursos bloqueantes**: [Detalles]

### Problemas Identificados
* **DOM excesivo**: [Si aplica, detalles y recomendaciones]
* **Cadena de solicitudes crítica**: [Si aplica, análisis]
* **JavaScript no utilizado**: [Porcentaje y oportunidad de reducción]
* **CSS no utilizado**: [Porcentaje y oportunidad de reducción]
* **Imágenes sin optimizar**: [Detalles y formatos recomendados]

## 6. Comparativa Mobile vs Desktop

[Tabla comparativa de todas las métricas clave]

**Análisis de Brecha**:
* [Explica las diferencias significativas entre Mobile y Desktop]
* [Identifica si hay problemas específicos de un dispositivo]
* [Recomienda enfoque de optimización (Mobile-First, Desktop-First, o Ambos)]

## 7. Impacto en SEO y Conversiones

### Impacto en Rankings
* **Page Experience Signal**: [Evaluación de cómo afecta al ranking de Google]
* **Mobile-First Indexing**: [Análisis específico para indexación móvil]

### Impacto en Conversiones
* **Tasa de Rebote Estimada**: [Basado en velocidad de carga]
* **Pérdida de Conversiones**: [Estimación basada en estudios de la industria]
* **ROI de Optimización**: [Beneficio potencial de mejorar el rendimiento]

## 8. Plan de Acción Recomendado

### Fase 1: Quick Wins (1-2 semanas)
[Optimizaciones de bajo esfuerzo y alto impacto]

### Fase 2: Mejoras Estructurales (1-2 meses)
[Cambios técnicos más profundos]

### Fase 3: Optimización Continua (Ongoing)
[Monitoreo y ajustes incrementales]

## 9. Métricas de Éxito y Monitoreo

**KPIs a Monitorear**:
* Core Web Vitals (LCP, INP, CLS)
* Puntuación PageSpeed (Mobile y Desktop)
* Tiempo de carga promedio
* Tasa de rebote
* Conversiones

**Herramientas Recomendadas**:
* Google Search Console (Core Web Vitals Report)
* PageSpeed Insights (Monitoreo mensual)
* Chrome User Experience Report (CrUX)
* Real User Monitoring (RUM) - [Herramienta específica recomendada]

---

Datos de entrada (JSON):
"""

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
* **Usa esta plantilla como base y complétala con la info real del cliente extraída de 'target_audit':**
~~~json
{
  "@context":"https://schema.org",
  "@graph": [
    {
      "@type":"Organization",
      "name":"[Extraer del sitio]",
      "url":"[URL del cliente]",
      "logo":"[Buscar logo en el sitio]",
      "sameAs":["[Redes sociales si se encuentran]"],
      "contactPoint":[{
        "@type":"ContactPoint",
        "contactType":"sales",
        "telephone":"[Si se encuentra]",
        "areaServed":"[País/región del cliente]",
        "availableLanguage":["[Idiomas del sitio]"]
      }]
    },
    {
      "@type": "WebSite",
      "url": "[URL del cliente]",
      "name": "[Nombre del cliente]",
      "publisher": {
        "@type": "Organization",
        "name": "[Nombre del cliente]"
      },
      "potentialAction": {
        "@type": "SearchAction",
        "target": "[URL del cliente]/search?q={search_term_string}",
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

    @staticmethod
    def now_iso() -> str:
        """Retorna timestamp ISO 8601 actual."""
        return datetime.utcnow().isoformat() + "Z"

    @staticmethod
    def _aggregate_summaries(summaries: List[Dict], base_url: str) -> Dict[str, Any]:
        """Agrega múltiples auditorías en un resumen consolidado (igual a ag2_pipeline.py)."""
        from urllib.parse import urlparse
        
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
    
    @staticmethod
    def _ensure_dict(obj: Any) -> Dict[str, Any]:
        """Normaliza: si obj es tuple/list devuelve su primer elemento, si es dict lo devuelve, si None devuelve {}."""
        if obj is None:
            return {}
        if isinstance(obj, (tuple, list)) and len(obj) > 0:
            maybe = obj[0]
            return maybe if isinstance(maybe, dict) else {}
        if isinstance(obj, dict):
            return obj
        return {}

    @staticmethod
    def filter_competitor_urls(
        search_items: List[Dict], target_domain: str
    ) -> List[str]:
        """
        Filtra una lista de resultados de Google Search y devuelve URLs limpias (Home Pages).

        Args:
            search_items: Lista de items de Google Search API
            target_domain: Dominio objetivo (para excluir)

        Returns:
            Lista de URLs filtradas y únicas (Home Pages)
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
            "stackoverflow.com",
            "developers.google.com",
            # Directorios de Software y Comparadores (Bloqueo Agresivo)
            "sourceforge.net",
            "capterra.com",
            "g2.com",
            "getapp.com",
            "softwareadvice.com",
            "trustradius.com",
            "alternativeto.net",
            "openalternative.co",
            "tracxn.com",
            "crunchbase.com",
            "pitchbook.com",
            "producthunt.com",
            "appsumo.com",
            "slashdot.org",
            "techradar.com",
            "pcmag.com",
            "zapier.com",
            "dev.to",
            "hashnode.com",
            "medium.com",
            "softpedia.com",
            "uptodown.com",
            "softonic.com",
            "softonic.com",
            target_domain,
        ]
        
        bad_subdomains = [
            "blog", "blogs", "forum", "forums", "community", "help", "support", 
            "docs", "status", "dev", "developer", "developers", "learn", "academy",
            "news", "press", "investors", "careers", "jobs", "shop"
        ]
        
        bad_title_words = [
            "review", "reviews", "alternative", "alternatives", " vs ", " versus ",
            "top 10", "top 5", "top 20", "best of", "list of", "forum", "community", "blog"
        ]

        filtered_urls = []
        seen_domains = set()

        for item in search_items:
            url = item.get("link") if isinstance(item, dict) else None
            title = item.get("title", "").lower() if isinstance(item, dict) else ""
            
            if not url:
                continue

            try:
                parsed_url = urlparse(url)
                domain_parts = parsed_url.netloc.split('.')
                
                # Detectar subdominio (asumiendo estructura standard sub.dominio.com)
                subdomain = ""
                if len(domain_parts) > 2:
                    # Ignorar www
                    if domain_parts[0] == "www":
                        if len(domain_parts) > 3:
                            subdomain = domain_parts[1]
                    else:
                        subdomain = domain_parts[0]
                
                # 1. Filtrar por Subdominio prohibido
                if subdomain in bad_subdomains:
                    continue

                domain = parsed_url.netloc.lstrip("www.")
                
                # 2. Filtrar por palabras en el Título (evita artículos de blogs y listas)
                if any(word in title for word in bad_title_words):
                    continue

                # Normalizar a Home Page
                home_url = f"{parsed_url.scheme}://{parsed_url.netloc}/"

                if domain in seen_domains:
                    continue

                is_bad = False
                for pattern in bad_patterns:
                    if pattern in domain or pattern in url:
                        is_bad = True
                        break
                
                if not is_bad:
                    filtered_urls.append(home_url)
                    seen_domains.add(domain)

            except Exception:
                continue

        return filtered_urls

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

            if (first_brace != -1 and 
                (first_bracket == -1 or first_brace < first_bracket)):
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
    async def run_google_search(query: str, api_key: str, cx_id: str, num_results: int = 10) -> Dict[str, Any]:
        """
        Ejecuta una búsqueda de Google Custom Search con soporte para paginación.
        """
        if not api_key or not cx_id:
            logger.warning(
                "GOOGLE_API_KEY o CSE_ID no configurados. Omitiendo búsqueda."
            )
            return {"error": "API Key o CX_ID no configurados"}

        endpoint = "https://www.googleapis.com/customsearch/v1"
        all_items = []
        
        # Calcular cuántas páginas (max 10 por página)
        max_pages = (num_results + 9) // 10
        
        logger.info(f"Google Search: {query} (Target: {num_results} results)")
        
        try:
            async with aiohttp.ClientSession() as session:
                for page in range(max_pages):
                    start_index = page * 10 + 1
                    # Calcular cuántos pedir en esta página
                    # Google permite 'num' entre 1 y 10
                    current_num = min(10, num_results - len(all_items))
                    
                    if current_num <= 0:
                        break

                    params = {
                        "key": api_key, 
                        "cx": cx_id, 
                        "q": query,
                        "num": current_num,
                        "start": start_index
                    }
                    
                    async with session.get(endpoint, params=params, timeout=15) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            items = data.get("items", [])
                            if not items:
                                break
                            all_items.extend(items)
                        else:
                            error_text = await resp.text()
                            logger.error(
                                f"Google Search API Error {resp.status}: {error_text}"
                            )
                            # Si falla una página, devolvemos lo que tenemos
                            break
                            
            return {"items": all_items}
                            
        except Exception as e:
            logger.error(f"Error en Google Search: {e}")
            return {"error": str(e), "items": all_items}
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
            # Normalizar por si target_audit viene como (dict, meta)
            target_audit = PipelineService._ensure_dict(target_audit)

            agent1_input_data = {
                "target_audit": {
                    "url": target_audit.get("url"),
                    "structure": target_audit.get("structure", {}),
                    "content": target_audit.get("content", {})
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

        for i, comp_url in enumerate(competitor_urls[:5]):  # Max 5 competidores
            logger.info(
                f"Auditando competidor {i+1}/{min(len(competitor_urls), 5)}: {comp_url}"
            )
            try:
                res = await audit_local_function(comp_url)
                # Puede devolver (summary, meta) o summary
                if isinstance(res, (tuple, list)) and len(res) > 0:
                    summary = res[0]
                else:
                    summary = res

                if not isinstance(summary, dict):
                    logger.warning(f"Audit result for {comp_url} is not a dict: {type(summary)}")
                    continue

                status = summary.get("status")
                if status == 200:
                    competitor_audits.append(summary)
                else:
                    logger.warning(f"Auditoría de {comp_url} retornó status {status}")
            except Exception as e:
                logger.warning(f"No se pudo auditar competidor {comp_url}: {e}")

        logger.info(f"Auditados {len(competitor_audits)} competidores exitosamente.")
        return competitor_audits

    @staticmethod
    def calculate_scores(audit_data: Dict[str, Any]) -> Dict[str, float]:
        """Calcula puntajes numéricos de una auditoría."""
        scores = {}
        
        # Structure Score (0-100)
        structure = audit_data.get('structure', {})
        structure_score = 0
        structure_score += 25 if structure.get('h1_check', {}).get('status') == 'pass' else 0
        structure_score += 25 if len(structure.get('header_hierarchy', {}).get('issues', [])) == 0 else 0
        structure_score += structure.get('semantic_html', {}).get('score_percent', 0) * 0.5
        scores['structure'] = round(structure_score, 1)
        
        # Content Score (0-100)
        content = audit_data.get('content', {})
        content_score = 0
        content_score += max(0, 100 - content.get('fragment_clarity', {}).get('score', 0) * 5)
        content_score += content.get('conversational_tone', {}).get('score', 0) * 10
        content_score += 25 if content.get('question_targeting', {}).get('status') == 'pass' else 0
        content_score += 25 if content.get('inverted_pyramid_style', {}).get('status') == 'pass' else 0
        scores['content'] = round(content_score / 2, 1)
        
        # E-E-A-T Score (0-100)
        eeat = audit_data.get('eeat', {})
        eeat_score = 0
        eeat_score += 25 if eeat.get('author_presence', {}).get('status') == 'pass' else 0
        eeat_score += min(25, eeat.get('citations_and_sources', {}).get('external_links', 0) * 0.5)
        eeat_score += 25 if len(eeat.get('content_freshness', {}).get('dates_found', [])) > 0 else 0
        trans = eeat.get('transparency_signals', {})
        eeat_score += 25 * sum([trans.get('about', False), trans.get('contact', False), trans.get('privacy', False)]) / 3
        scores['eeat'] = round(eeat_score, 1)
        
        # Schema Score (0-100)
        schema = audit_data.get('schema', {})
        schema_score = 0
        schema_score += 50 if schema.get('schema_presence', {}).get('status') == 'present' else 0
        schema_score += min(50, len(schema.get('schema_types', [])) * 25)
        scores['schema'] = round(schema_score, 1)
        
        # Total Score
        scores['total'] = round((scores['structure'] + scores['content'] + scores['eeat'] + scores['schema']) / 4, 1)
        
        return scores

    @staticmethod
    async def generate_comparative_analysis(
        target_audit: Dict[str, Any],
        competitor_audits: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Genera análisis comparativo automático."""
        all_scores = []
        
        # Calcular scores del target
        target_scores = PipelineService.calculate_scores(target_audit)
        target_url = target_audit.get('url', 'Target Site')
        all_scores.append({'url': target_url, 'scores': target_scores})
        
        # Calcular scores de competidores
        for comp in competitor_audits:
            comp_scores = PipelineService.calculate_scores(comp)
            comp_url = comp.get('url', 'Unknown')
            all_scores.append({'url': comp_url, 'scores': comp_scores})
        
        # Generar ranking
        sorted_scores = sorted(all_scores, key=lambda x: x['scores']['total'], reverse=True)
        
        # Identificar fortalezas y debilidades
        analysis = []
        for item in all_scores:
            strengths = []
            weaknesses = []
            for category, score in item['scores'].items():
                if category == 'total':
                    continue
                if score >= 70:
                    strengths.append(f"{category.upper()}: {score}/100")
                elif score < 50:
                    weaknesses.append(f"{category.upper()}: {score}/100")
            
            analysis.append({
                'url': item['url'],
                'scores': item['scores'],
                'strengths': strengths,
                'weaknesses': weaknesses
            })
        
        return {
            'scores': all_scores,
            'ranking': sorted_scores,
            'analysis': analysis,
            'summary': {
                'target_position': next((i+1 for i, x in enumerate(sorted_scores) if x['url'] == target_url), None),
                'total_competitors': len(competitor_audits),
                'target_score': target_scores['total'],
                'best_competitor_score': sorted_scores[0]['scores']['total'] if sorted_scores else 0
            }
        }

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
            # Asegurar que target_audit sea dict
            target_audit = PipelineService._ensure_dict(target_audit)

            # Cargar PageSpeed si existe
            pagespeed_data = {}
            try:
                from pathlib import Path
                import json
                # Intentar cargar desde archivo si existe
                reports_dir = Path("reports") / f"audit_{id(target_audit)}"
                pagespeed_file = reports_dir / "pagespeed.json"
                if pagespeed_file.exists():
                    with open(pagespeed_file, 'r') as f:
                        pagespeed_data = json.load(f)
            except:
                pass
            
            final_context = {
                "target_audit": target_audit,
                "external_intelligence": external_intelligence,
                "search_results": search_results,
                "competitor_audits": competitor_audits,
                "pagespeed": pagespeed_data,
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
    async def generate_pagespeed_analysis(
        pagespeed_data: Dict[str, Any], llm_function: Optional[callable] = None
    ) -> str:
        """
        Genera un análisis ejecutivo de PageSpeed usando LLM.

        Args:
            pagespeed_data: Datos crudos de PageSpeed
            llm_function: Función LLM

        Returns:
            Markdown con el análisis
        """
        if not pagespeed_data or not llm_function:
            return ""

        try:
            # Preparar input minimizado para no exceder tokens
            minimized_data = {
                "mobile": {
                    "score": pagespeed_data.get("mobile", {}).get("score"),
                    "metrics": pagespeed_data.get("mobile", {}).get("metrics"),
                    "issues": pagespeed_data.get("mobile", {}).get("issues", [])[:5]
                },
                "desktop": {
                    "score": pagespeed_data.get("desktop", {}).get("score"),
                    "metrics": pagespeed_data.get("desktop", {}).get("metrics"),
                    "issues": pagespeed_data.get("desktop", {}).get("issues", [])[:5]
                }
            }
            
            input_json = json.dumps(minimized_data, ensure_ascii=False, indent=2)
            
            analysis_text = await llm_function(
                system_prompt=PipelineService.PAGESPEED_ANALYSIS_PROMPT,
                user_prompt=input_json,
            )
            
            # Limpiar markdown
            if analysis_text.startswith("```markdown"):
                analysis_text = analysis_text[11:]
            if analysis_text.endswith("```"):
                analysis_text = analysis_text[:-3]
                
            return analysis_text.strip()
            
        except Exception as e:
            logger.error(f"Error generando análisis PageSpeed: {e}")
            return ""

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

        # PASO 1: Rastrear y auditar múltiples páginas (como ag2_pipeline.py)
        if not target_audit:
            if audit_local_service is None:
                logger.error("No hay auditoría preexistente ni función audit_local")
                return {"error": "No audit data available"}

            try:
                # Rastrear sitio si hay crawler_service
                all_urls = [url]
                if crawler_service:
                    try:
                        all_urls = await crawler_service(url, max_pages=50)
                        logger.info(f"Crawler encontró {len(all_urls)} URLs")
                    except Exception as e:
                        logger.warning(f"Crawler falló: {e}. Auditando solo URL principal.")
                        all_urls = [url]
                
                # Seleccionar URLs importantes (máximo 5)
                urls_to_audit = all_urls[:5] if len(all_urls) > 5 else all_urls
                logger.info(f"Auditando {len(urls_to_audit)} páginas")
                
                # Auditar cada página
                all_summaries = []
                individual_page_audits = []  # NUEVO: Guardar auditorías individuales
                
                for i, page_url in enumerate(urls_to_audit):
                    try:
                        audit_result = await audit_local_service(page_url)
                        if isinstance(audit_result, tuple):
                            summary = audit_result[0]
                        else:
                            summary = audit_result
                        
                        if isinstance(summary, dict) and summary.get("status") == 200:
                            all_summaries.append(summary)
                            # NUEVO: Guardar datos individuales con índice
                            individual_page_audits.append({
                                "index": i,
                                "url": page_url,
                                "data": summary
                            })
                    except Exception as e:
                        logger.warning(f"Error auditando {page_url}: {e}")
                
                if not all_summaries:
                    logger.error("Todas las auditorías fallaron")
                    return {"error": "All audits failed"}
                
                # Agregar resumen (como ag2_pipeline.py)
                if len(all_summaries) == 1:
                    target_audit = all_summaries[0]
                    # Añadir audited_page_paths para una sola página
                    parsed = urlparse(target_audit.get("url", ""))
                    target_audit["audited_page_paths"] = [parsed.path or "/"]
                    target_audit["audited_pages_count"] = 1
                else:
                    # Agregar múltiples páginas
                    target_audit = PipelineService._aggregate_summaries(all_summaries, url)
                
                # NUEVO: Guardar datos individuales de páginas
                # Usamos deepcopy para evitar referencias circulares si target_audit es uno de los elementos
                import copy
                target_audit["_individual_page_audits"] = copy.deepcopy(individual_page_audits)
                
                logger.info("Auditoría local completada")
            except Exception as e:
                logger.exception(f"Error en auditoría local: {e}")
                return {"error": f"Local audit failed: {e}"}

        # Normalizar target_audit por si viene como tuple/list desde otro punto
        target_audit = PipelineService._ensure_dict(target_audit)

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
                        query, google_api_key, google_cx_id, num_results=30
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
        
        # Agregar competidores del usuario
        user_competitors = []
        try:
            from app.core.database import SessionLocal
            from app.models import Audit
            db = SessionLocal()
            
            # Buscar por URL exacta primero
            audit = db.query(Audit).filter(Audit.url == url).order_by(Audit.id.desc()).first()
            
            # Si no encuentra, buscar por dominio
            if not audit:
                domain = urlparse(url).netloc.replace('www.', '')
                audit = db.query(Audit).filter(Audit.url.contains(domain)).order_by(Audit.id.desc()).first()
            
            logger.info(f"Audit ID: {audit.id if audit else 'No encontrado'}, URL: {audit.url if audit else 'N/A'}, Competitors: {audit.competitors if audit else 'N/A'}")
            
            if audit and audit.competitors:
                if isinstance(audit.competitors, list):
                    user_competitors = audit.competitors
                elif isinstance(audit.competitors, str):
                    import json
                    try:
                        user_competitors = json.loads(audit.competitors)
                    except:
                        user_competitors = [audit.competitors]
            
            db.close()
        except Exception as e:
            logger.error(f"Error cargando competidores: {e}", exc_info=True)
        
        # PRIORIZAR competidores del usuario: primero los del usuario, luego los de Google
        # Limitar a 5 total, pero si el usuario dio 5+, usar solo los del usuario
        if len(user_competitors) >= 5:
            all_competitor_urls = user_competitors[:5]
        else:
            # Combinar: primero los del usuario, luego completar con Google hasta 5
            all_competitor_urls = user_competitors + competitor_urls_filtradas
            all_competitor_urls = list(dict.fromkeys(all_competitor_urls))[:5]
        
        logger.info(
            f"Competidores: {len(competitor_urls_raw)} de Google, "
            f"{len(user_competitors)} del usuario, "
            f"{len(all_competitor_urls)} total a auditar"
        )

        competitor_audits = await PipelineService.generate_competitor_audits(
            all_competitor_urls, audit_local_service
        )

        # PASO 5: Generar Reporte (Agente 2)
        markdown_report, fix_plan = await PipelineService.generate_report(
            target_audit,
            external_intelligence,
            search_results,
            competitor_audits,
            llm_function,
        )

        # PASO 6: Análisis Comparativo Automático
        comparative_analysis = None
        try:
            comparative_analysis = await PipelineService.generate_comparative_analysis(
                target_audit, competitor_audits
            )
            logger.info("Análisis comparativo generado exitosamente")
            
            # Guardar reporte HTML si hay análisis
            if comparative_analysis:
                try:
                    from .comparative_report_generator import generate_html_report
                    
                    # Determinar ruta de salida
                    reports_dir = Path("reports")
                    reports_dir.mkdir(exist_ok=True)
                    
                    html_path = reports_dir / "comparative_report.html"
                    json_path = reports_dir / "comparative_scores.json"
                    
                    # Generar HTML
                    generate_html_report(
                        comparative_analysis['scores'],
                        comparative_analysis['analysis'],
                        html_path
                    )
                    
                    # Guardar JSON
                    import json as json_lib
                    with open(json_path, 'w', encoding='utf-8') as f:
                        json_lib.dump(comparative_analysis, f, indent=2, ensure_ascii=False)
                    
                    logger.info(f"Reportes guardados: {html_path}, {json_path}")
                except Exception as e:
                    logger.warning(f"Error guardando reportes: {e}")
        except Exception as e:
            logger.warning(f"Error generando análisis comparativo: {e}")

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
            "comparative_analysis": comparative_analysis,
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
