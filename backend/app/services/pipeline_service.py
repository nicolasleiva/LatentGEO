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

## 2. Métricas de Rendimiento (Lighthouse / Lab Data)

### Largest Contentful Paint (LCP) - Velocidad de Carga Percibida
* **Mobile**: X.Xs | **Desktop**: X.Xs
* **Evaluación**: ✅ Óptimo / ⚠️ Necesita Mejora / ❌ Pobre
* **Impacto**: [Explica cómo afecta la percepción de velocidad y tasa de rebote]

### Interaction to Next Paint (INP) / FID - Capacidad de Respuesta
* **Mobile**: XXXms | **Desktop**: XXXms
* **Evaluación**: ✅ Óptimo / ⚠️ Necesita Mejora / ❌ Pobre
* **Impacto**: [Explica cómo afecta la interactividad y frustración del usuario]

### Cumulative Layout Shift (CLS) - Estabilidad Visual
* **Mobile**: X.XXX | **Desktop**: X.XXX
* **Evaluación**: ✅ Óptimo / ⚠️ Necesita Mejora / ❌ Pobre
* **Impacto**: [Explica cómo afecta la usabilidad y clics accidentales]

**Veredicto Lab Data**: [Análisis de si el sitio es técnicamente rápido]

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
* ANALIZA EXHAUSTIVAMENTE cada sección del 'target_audit' para identificar TODOS los issues:
  - **Estructura:** Analiza 'structure.h1_check', 'structure.header_hierarchy.issues', 'structure.semantic_html', 'structure.list_usage', 'structure.table_usage'
  - **Contenido:** Analiza 'content.fragment_clarity', 'content.conversational_tone', 'content.question_targeting'
  - **E-E-A-T:** Analiza 'eeat.author_presence', 'eeat.citations_and_sources', 'eeat.content_freshness'
  - **Schema:** Analiza 'schema.schema_presence', 'schema.schema_types'
  - **Páginas específicas:** Para cada página en 'audited_page_paths', revisa si tiene issues específicos
* Cada objeto del array debe tener estos campos:
  - "page_path": (string) Ruta de la página afectada (ej. "/", "/es", "/es/consulting-team"). Usa "ALL_PAGES" para issues globales.
  - "issue_code": (string) Código del problema (ej. "SCHEMA_MISSING", "H1_HIERARCHY_SKIP", "AUTHOR_MISSING", "FAQ_MISSING")
  - "priority": (string) "CRITICAL", "HIGH", "MEDIUM", "LOW" - Basado en impacto SEO/GEO
  - "description": (string) Descripción clara del problema con datos específicos del audit
  - "snippet": (string, opcional) Fragmento de código HTML relevante si aplica
  - "suggestion": (string) Sugerencia concreta de cómo solucionarlo

**INSTRUCCIONES DE ANÁLISIS DETALLADO:**

1. **Issues de Estructura (H1/Hierarquía):**
   - Si 'structure.h1_check.status' != "pass", crear issues para páginas faltantes
   - Para cada issue en 'structure.header_hierarchy.issues', crear item específico

2. **Issues de Contenido:**
   - Páginas con párrafos largos: 'content.fragment_clarity.pages_with_issues'
   - Si 'content.question_targeting.status' != "pass", crear FAQ_MISSING

3. **Issues E-E-A-T:**
   - Si 'eeat.author_presence.status' != "pass", crear AUTHOR_MISSING
   - Páginas sin fechas: 'eeat.content_freshness.pages_missing_dates'

4. **Issues de Schema:**
   - Si 'schema.schema_presence.status' != "present", crear SCHEMA_MISSING

5. **Issues Específicos por Página:**
   - Analizar cada página en 'audited_page_paths' individualmente
   - Identificar patrones específicos (ej. páginas de producto, categorías)

**EJEMPLO DE fix_plan COMPLETO (SIGUE ESTE FORMATO EXACTO):**
[
  {
    "page_path": "ALL_PAGES",
    "issue_code": "SCHEMA_MISSING",
    "priority": "CRITICAL",
    "description": "No se detectó JSON-LD Schema en ninguna página (0/X páginas)",
    "snippet": "",
    "suggestion": "Implementar Schema Organization + WebSite en el <head> de todas las páginas."
  },
  {
    "page_path": "/",
    "issue_code": "H1_MISSING",
    "priority": "CRITICAL",
    "description": "Página home sin H1 único detectado",
    "snippet": "",
    "suggestion": "Añadir <h1> con título principal de la página"
  },
  {
    "page_path": "/contacto",
    "issue_code": "H1_HIERARCHY_SKIP",
    "priority": "HIGH",
    "description": "Salto de jerarquía H1->H3 detectado",
    "snippet": "<h3>Contáctanos</h3>",
    "suggestion": "Insertar H2 antes del H3 o cambiar H3 por H2"
  }
]

**GENERA EL fix_plan COMPLETO BASÁNDOTE EN TODOS LOS DATOS REALES DE 'target_audit'.**
"""

    REPORT_PROMPT_V11_COMPLETE = """
Eres un Director de Consultoría SEO/GEO de élite. Tu objetivo es generar el informe más detallado, profesional y exhaustivo posible.
Recibirás un JSON gigante con 10 claves de contexto clave: target_audit, external_intelligence, search_results, competitor_audits, pagespeed, keywords, backlinks, rank_tracking, llm_visibility, ai_content_suggestions.

Tu trabajo es generar un INFORME DE AUDITORÍA COMPLETO (en Markdown) y un PLAN DE ACCIÓN (en JSON).

**REQUISITOS CRÍTICOS DE CALIDAD:**
1.  **EXTENSIÓN Y DETALLE:** Cada sección debe ser profunda. No te limites a resúmenes breves. Analiza los datos, explica el "por qué" y el impacto en el negocio.
2.  **SUB-SECCIONES:** Usa obligatoriamente los encabezados ## 4.1, ## 4.2, etc. indicados en la plantilla. Esto es vital para el índice del PDF.
3.  **DATOS REALES:** Usa cada fragmento de información de 'keywords', 'pagespeed', 'backlinks', etc. Si un dato está presente, DEBE aparecer en el informe en formato de tabla o análisis.
4.  **TONO:** Ejecutivo, experto, autoritario y accionable.

IMPORTANTE: Manejo de Datos Faltantes
- Si una sección clave (ej. 'pagespeed', 'keywords', 'backlinks') tiene datos (en 'items' o tablas), DEBES presentarlos.
- Si alguna clave está realmente vacía o es null, indica: "Datos no disponibles para esta sección" y ofrece recomendaciones generales basadas en el nicho.
- NO inventes datos que no están en el JSON.
- Usa 'pagespeed_metrics' (tabla) y 'pagespeed_analysis' (resumen) como base fundamental para la sección 3.

Tu respuesta DEBE tener DOS PARTES separadas por el delimitador exacto:
1. "report_markdown": El informe completo.
2. ---START_FIX_PLAN---
3. "fix_plan": El JSON Array de tareas.

--- REQUISITOS DEL "report_markdown" (Plantilla Estricta) ---

# 1. Resumen Ejecutivo (Enfoque de Negocio)
* Análisis profundo del estado actual.
* **Hipótesis de Impacto:** Estimación detallada de mejora.
* **Tabla de Hallazgos (Cuantificada):** (Estructura, Contenido, Rendimiento, Autoridad).

# 2. Metodología
* Detalla las herramientas y procesos usados.

# 3. Rendimiento y Velocidad (WPO)
[IMPORTANTE: Esta sección SOLO debe incluirse si 'pagespeed_metrics' contiene datos reales de Lighthouse. Si 'pagespeed_metrics' indica "Datos no disponibles", salta COMPLETAMENTE esta sección (incluyendo el encabezado # 3) y continúa con la sección # 4.]
## 3.1 Métricas de Auditoría de Rendimiento (Lab Data)
* Presenta una tabla con LCP, FID/INP, CLS, FCP y TTFB para Mobile y Desktop.
* Comenta los resultados basándote en los umbrales estándar de la industria.
## 3.2 Oportunidades Técnicas Priorizadas
* Tabla con el Top 5 de mejoras de rendimiento extraídas de 'pagespeed'.

# 4. Diagnóstico Técnico & Semántico
## 4.1 Estructura Técnica (H1, Jerarquía)
## 4.2 Estructura para IA (GEO) - Claridad y Fragmentación
## 4.3 Schema.org y Datos Estructurados
## 4.4 E-E-A-T (Experiencia, Autoridad, Confianza)

# 5. Análisis de Visibilidad y Competencia
## 5.1 Palabras Clave y Oportunidades
* Tabla Top 20 Keywords. Análisis de intención y dificultad.
## 5.2 Rank Tracking y Posicionamiento
* Resume el estado actual de los rankings según los datos proporcionados en 'rank_tracking.items'.
* Menciona cuántas palabras clave están en el Top 3, Top 10 y Top 20.
* NO indiques que no hay conexión si se han proporcionado datos de rastreo.

# 6. Perfil de Enlaces y Autoridad
## 6.1 Análisis de Backlinks
* Presenta una tabla con los Top Backlinks de 'backlinks.items' (source_url, anchor_text, authority).
* Resumen de autoridad y salud del perfil (Dofollow vs Nofollow).
## 6.2 Estrategia de Citabilidad

# 7. Visibilidad en IA y LLMs (GEO Insights)
## 7.1 Menciones y Visibilidad en LLMs
* Usa los datos de 'llm_visibility.items' para informar si la marca es mencionada en ChatGPT, Gemini y Perplexity para las queries analizadas.
* Presenta una tabla o lista con ejemplos de citaciones y el estado de visibilidad.
## 7.2 Análisis de Fragmentos (GEO Metrics)

# 8. Hoja de Ruta GEO (Estrategia de Contenido)
## 8.1 Sugerencias de Contenido AI
## 8.2 Calendario Editorial 90 días (Plan de Acción de Contenidos)

# 9. Estrategia Competitiva Integrada
## 9.1 Ventajas y Debilidades
## 9.2 Matriz Impacto vs Esfuerzo

# 10. Plan de Implementación (RACI)
* Tabla de tareas con responsables y KPIs.

# Anexos
## Anexo A: Snippet JSON-LD Crítico
## Anexo B: Verificación Manual (Prompts usados)

---START_FIX_PLAN---
[
  { "page_path": "URL", "issue_code": "CODE", "priority": "CRITICAL/HIGH/MEDIUM/LOW", "description": "DESC", "snippet": "HTML", "suggestion": "FIX" }
]
"""

    @staticmethod
    def now_iso() -> str:
        """Retorna timestamp ISO 8601 actual (timezone-aware)."""
        return datetime.now(timezone.utc).isoformat() + "Z"

    @staticmethod
    async def generate_pagespeed_analysis(pagespeed_data: Dict[str, Any], llm_function: callable) -> str:
        """
        Generates a markdown analysis of PageSpeed data using LLM.
        
        Args:
            pagespeed_data: Full PageSpeed data (mobile + desktop)
            llm_function: LLM call function
            
        Returns:
            Markdown string with the analysis
        """
        if not pagespeed_data:
            logger.warning("No PageSpeed data provided for analysis")
            return ""
        
        try:
            def to_sec(ms):
                try: return f"{float(ms)/1000:.2f}s"
                except: return "0.00s"

            # Prepare simplified data for LLM to save tokens
            lite_data = {
                "mobile": {
                    "score": pagespeed_data.get("mobile", {}).get("performance_score", 0),
                    "metrics": {
                        "LCP": to_sec(pagespeed_data.get("mobile", {}).get("core_web_vitals", {}).get("lcp", 0)),
                        "FID": f"{pagespeed_data.get('mobile', {}).get('core_web_vitals', {}).get('fid', 0):.0f}ms",
                        "CLS": f"{pagespeed_data.get('mobile', {}).get('core_web_vitals', {}).get('cls', 0):.3f}",
                        "FCP": to_sec(pagespeed_data.get("mobile", {}).get("core_web_vitals", {}).get("fcp", 0)),
                        "TTFB": f"{pagespeed_data.get('mobile', {}).get('core_web_vitals', {}).get('ttfb', 0):.0f}ms"
                    },
                    "top_opportunities": PipelineService._extract_top_opportunities(
                        pagespeed_data.get("mobile", {}).get("opportunities", {}), limit=3
                    )
                },
                "desktop": {
                    "score": pagespeed_data.get("desktop", {}).get("performance_score", 0),
                    "metrics": {
                        "LCP": to_sec(pagespeed_data.get("desktop", {}).get("core_web_vitals", {}).get("lcp", 0)),
                        "FID": f"{pagespeed_data.get('desktop', {}).get('core_web_vitals', {}).get('fid', 0):.0f}ms",
                        "CLS": f"{pagespeed_data.get('desktop', {}).get('core_web_vitals', {}).get('cls', 0):.3f}",
                        "FCP": to_sec(pagespeed_data.get("desktop", {}).get("core_web_vitals", {}).get("fcp", 0)),
                        "TTFB": f"{pagespeed_data.get('desktop', {}).get('core_web_vitals', {}).get('ttfb', 0):.0f}ms"
                    },
                    "top_opportunities": PipelineService._extract_top_opportunities(
                        pagespeed_data.get("desktop", {}).get("opportunities", {}), limit=3
                    )
                }
            }
            
            prompt = PipelineService.PAGESPEED_ANALYSIS_PROMPT
            user_input = json.dumps(lite_data, ensure_ascii=False)
            
            logger.info("Calling LLM for PageSpeed analysis...")
            analysis = await llm_function(system_prompt=prompt, user_prompt=user_input)
            
            return analysis
        except Exception as e:
            logger.error(f"Error generating PageSpeed analysis: {e}", exc_info=True)
            return ""

    @staticmethod
    def _extract_top_opportunities(opportunities_dict: dict, limit: int = 3) -> list:
        """
        Extract top opportunities from PageSpeed opportunities dictionary.
        
        Safely converts the opportunities dictionary to a sorted list of the most
        impactful optimizations based on potential time savings.
        
        Args:
            opportunities_dict: Dictionary of opportunity audits from PageSpeed API
            limit: Maximum number of opportunities to return (default: 3)
            
        Returns:
            List of top opportunities sorted by potential savings (descending)
            Returns empty list if input is invalid or no opportunities have savings
            
        Example:
            >>> opps = {
            ...     "uses_optimized_images": {"title": "Optimize images", "numericValue": 1250},
            ...     "render_blocking": {"title": "Remove blocking", "numericValue": 890}
            ... }
            >>> result = _extract_top_opportunities(opps, limit=2)
            >>> len(result)
            2
            >>> result[0]["savings_ms"]
            1250
        """
        if not opportunities_dict or not isinstance(opportunities_dict, dict):
            logger.warning(f"PageSpeed opportunities is not a valid dict: {type(opportunities_dict)}")
            return []
        
        try:
            # Convert dict to list of opportunities with savings
            opportunities_list = []
            for key, opp_data in opportunities_dict.items():
                if not isinstance(opp_data, dict):
                    logger.debug(f"Skipping non-dict opportunity: {key}")
                    continue
                    
                # Extract numeric value (savings in ms)
                numeric_value = opp_data.get("numericValue", 0)
                # Handle None values explicitly
                if numeric_value is None:
                    logger.debug(f"Found None numericValue for opportunity {key}, converting to 0")
                    numeric_value = 0
                
                # Additional type checking for safety
                if not isinstance(numeric_value, (int, float)):
                    logger.warning(f"Invalid numericValue type for {key}: {type(numeric_value)} = {numeric_value}, converting to 0")
                    numeric_value = 0
                    
                if numeric_value > 0:  # Only include opportunities with measurable savings
                    opportunities_list.append({
                        "id": key,
                        "title": opp_data.get("title", key.replace("_", " ").title()),
                        "description": opp_data.get("description", ""),
                        "savings_ms": numeric_value,
                        "score": opp_data.get("score", 0),
                        "display_value": opp_data.get("displayValue", "")
                    })
            
            # Sort by savings (descending) and return top N
            opportunities_list.sort(key=lambda x: x["savings_ms"], reverse=True)
            result = opportunities_list[:limit]
            
            logger.info(f"Extracted {len(result)} PageSpeed opportunities from {len(opportunities_dict)} total (top {limit})")
            return result
            
        except Exception as e:
            logger.error(f"Error extracting PageSpeed opportunities: {e}", exc_info=True)
            return []

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
        Filtra una lista de resultados de Google Search y devuelve URLs limpias (Home Pages) de competidores reales.
        
        Reglas:
        1. Excluye el dominio objetivo.
        2. Excluye directorios, redes sociales y sitios de "listas".
        3. Excluye subdominios irrelevantes (blog, help, forums).
        4. Normaliza a la URL raíz (Home Page).
        5. Devuelve solo un dominio único por competidor.

        Args:
            search_items: Lista de items de Google Search API
            target_domain: Dominio objetivo (para excluir)

        Returns:
            Lista de URLs filtradas y únicas (Home Pages)
        """
        if not search_items:
            return []

        bad_patterns = [
            "linkedin.com", "facebook.com", "twitter.com", "x.com", "youtube.com", 
            "instagram.com", "pinterest.com", "tiktok.com", ".gov", ".edu", ".org", 
            "wikipedia.org", "medium.com", "reddit.com", "quora.com", "g.page", 
            "goo.gl", "maps.google.com", "github.com", "zoom.info", "crunchbase.com", 
            "amazon.com", "ebay.com", "mercadolibre.com", "clarin.com", "lanacion.com", 
            "stackoverflow.com", "developers.google.com", "imdb.com", "warnerbros.com",
            "merriam-webster.com", "britannica.com", "dictionary.com", "thefreedictionary.com",
            "medicalnewstoday.com", "mayoclinic.org", "webmd.com", "healthline.com",
            # Software Directories and Comparators
            "sourceforge.net", "capterra.com", "g2.com", "getapp.com", "softwareadvice.com", 
            "trustradius.com", "alternativeto.net", "openalternative.co", "tracxn.com", 
            "pitchbook.com", "producthunt.com", "appsumo.com", "slashdot.org", 
            "techradar.com", "pcmag.com", "zapier.com", "dev.to", "hashnode.com", 
            "softpedia.com", "uptodown.com", "softonic.com", 
            target_domain  # Excluir self
        ]
        
        bad_subdomains = {
            "blog", "blogs", "forum", "forums", "community", "help", "support", 
            "docs", "status", "dev", "developer", "developers", "learn", "academy",
            "news", "press", "investors", "careers", "jobs", "shop", "store"
        }
        
        bad_title_words = [
            "review", "reviews", "alternative", "alternatives", " vs ", " versus ",
            "top 10", "top 5", "top 20", "best of", "list of", "forum"
        ]

        unique_domains = set()
        filtered_urls = []

        logger.info(f"PIPELINE: Filtrando {len(search_items)} resultados de búsqueda para encontrar competidores.")

        for item in search_items:
            # Check limit upfront
            if len(filtered_urls) >= 10:  # Aumentamos a 10 como se mencionó en el summary
                break
                
            url = item.get("link") if isinstance(item, dict) else None
            title = item.get("title", "").lower() if isinstance(item, dict) else ""
            
            if not url:
                continue

            try:
                parsed_url = urlparse(url)
                netloc = parsed_url.netloc.lower()
                
                # Normalizar domain para checkeo (sin www)
                domain_clean = netloc[4:] if netloc.startswith("www.") else netloc
                
                # 0. Check si ya tenemos este dominio
                if domain_clean in unique_domains:
                    continue
                
                # 1. Check Subdominios
                domain_parts = netloc.split('.')
                subdomain = ""
                # Lógica simple de subdominio: si tiene 3 partes y la primera no es www
                if len(domain_parts) >= 3 and domain_parts[0] != "www":
                    subdomain = domain_parts[0]
                
                if subdomain in bad_subdomains:
                    logger.info(f"PIPELINE: Excluyendo {url} (subdominio irrelevante: {subdomain})")
                    continue
                
                # 2. Check Patrones prohibidos en dominio
                is_bad = False
                for pattern in bad_patterns:
                    if pattern in domain_clean:
                        logger.info(f"PIPELINE: Excluyendo {url} (patrón prohibido: {pattern})")
                        is_bad = True
                        break
                if is_bad:
                    continue
                
                # 3. Check Palabras en Título (para filtrar listicles/reviews)
                bad_word = next((word for word in bad_title_words if word in title), None)
                if bad_word:
                    logger.info(f"PIPELINE: Excluyendo {url} (palabra prohibida en título: {bad_word})")
                    continue

                # 4. Validar que es una URL "home" o raiz
                # Si el path es largo o tiene muchos segmentos, es probable que sea una página interna específica
                # Preferimos encontrar la home del competidor.
                # ESTRATEGIA: Tomamos la raiz.
                home_url = f"{parsed_url.scheme}://{netloc}/"
                
                logger.info(f"PIPELINE: Competidor detectado: {home_url}")
                unique_domains.add(domain_clean)
                filtered_urls.append(home_url)

            except Exception as e:
                logger.error(f"PIPELINE: Error procesando URL {url}: {e}")
                continue

        logger.info(f"PIPELINE: Total {len(filtered_urls)} competidores únicos encontrados.")
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
            
            # Limpiar comentarios estilo JS (// o /* */) que a veces meten los LLMs
            candidate_cleaned = re.sub(r"//.*?\n", "\n", candidate_cleaned)
            candidate_cleaned = re.sub(r"/\*.*?\*/", "", candidate_cleaned, flags=re.DOTALL)

            try:
                parsed = json.loads(candidate_cleaned)
                return parsed
            except json.JSONDecodeError:
                # Intento final: si falló por algún caracter raro, intentar con el original sin limpiar comentarios
                # (A veces el regex de limpieza puede romper algo)
                return json.loads(candidate)

        except Exception as e:
            logger.warning(f"Fallo parsear JSON: {e}. Raw: {text[:200]}...")
            return {default_key: text}

    @staticmethod
    async def run_google_search(query: str, api_key: str, cx_id: str, num_results: int = 10) -> Dict[str, Any]:
        """
        Ejecuta una búsqueda de Google Custom Search con soporte para paginación.
        """
        if not api_key or not cx_id:
            logger.error(
                f"Step 2: GOOGLE_API_KEY or CSE_ID missing. SEARCH ABORTED for: {query}"
            )
            return {"error": "API Key o CX_ID no configurados"}

        endpoint = "https://www.googleapis.com/customsearch/v1"
        all_items = []
        
        # Calcular cuántas páginas (max 10 por página)
        max_pages = (num_results + 9) // 10
        
        logger.info(f"PIPELINE: Google Search Iniciado. Query: '{query}' (Objetivo: {num_results} resultados en {max_pages} páginas)")
        
        try:
            async with aiohttp.ClientSession() as session:
                for page in range(max_pages):
                    start_index = page * 10 + 1
                    # Calcular cuántos pedir en esta página
                    # Google permite 'num' entre 1 y 10
                    current_num = min(10, num_results - len(all_items))
                    
                    if current_num <= 0:
                        break

                    logger.info(f"PIPELINE: Google Search página {page+1}/{max_pages} (start={start_index}, num={current_num})")
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
                                logger.warning(f"PIPELINE: Google Search no devolvió más items en la página {page+1}")
                                break
                            all_items.extend(items)
                            logger.info(f"PIPELINE: Google Search página {page+1} obtuvo {len(items)} items. Total acumulado: {len(all_items)}")
                        else:
                            error_text = await resp.text()
                            logger.error(
                                f"PIPELINE: Google Search API Error {resp.status} en página {page+1}: {error_text}"
                            )
                            # Si falla una página, devolvemos lo que tenemos
                            break
                            
            results_count = len(all_items)
            logger.info(f"PIPELINE: Google Search completado. Total: {results_count} items para la query: '{query}'")
            return {"items": all_items}
                            
        except Exception as e:
            logger.error(f"PIPELINE: Error fatal en Google Search: {e}")
            return {"error": str(e), "items": all_items}

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
                logger.error("LLM function is None in analyze_external_intelligence")
                raise ValueError("LLM function required for production. Cannot generate external intelligence without LLM.")
            
            logger.info(f"Enviando datos al Agente 1 (KIMI). Tamaño del input: {len(agent1_input)} caracteres.")
            
            try:
                # Llamar LLM (Gemini, OpenAI, etc.)
                agent1_response_text = await llm_function(
                    system_prompt=PipelineService.EXTERNAL_ANALYSIS_PROMPT,
                    user_prompt=agent1_input,
                )
                logger.info(f"Respuesta recibida del Agente 1. Tamaño: {len(agent1_response_text)} caracteres.")
                logger.debug(f"Respuesta raw del Agente 1: {agent1_response_text[:500]}...")
            except Exception as llm_err:
                logger.error(f"Error llamando al LLM en Agente 1: {llm_err}")
                raise

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
        total_competitors = len(competitor_urls[:5])
        logger.info(f"PIPELINE: Iniciando auditoría de {total_competitors} competidores.")
        
        for i, comp_url in enumerate(competitor_urls[:5]):  # Max 5 competidores
            logger.info(
                f"PIPELINE: Auditando competidor {i+1}/{total_competitors}: {comp_url}"
            )
            try:
                res = await audit_local_function(comp_url)
                # Puede devolver (summary, meta) o summary
                if isinstance(res, (tuple, list)) and len(res) > 0:
                    summary = res[0]
                else:
                    summary = res

                if not isinstance(summary, dict):
                    logger.warning(f"PIPELINE: Resultado de auditoría para {comp_url} no es un diccionario: {type(summary)}")
                    continue

                status = summary.get("status") if isinstance(summary, dict) else 500
                if status == 200:
                    competitor_audits.append(summary)
                    logger.info(f"PIPELINE: Auditoría de competidor {comp_url} exitosa.")
                else:
                    logger.warning(f"PIPELINE: Auditoría de {comp_url} retornó status {status}. Se omitirá este competidor.")
                    # Opcional: Agregar un registro mínimo para que el LLM sepa que existe pero falló
                    competitor_audits.append({
                        "url": comp_url,
                        "status": status,
                        "error": f"No se pudo acceder al sitio (HTTP {status})"
                    })
            except Exception as e:
                logger.error(f"PIPELINE: Falló auditoría de competidor {comp_url}: {e}")
                competitor_audits.append({
                    "url": comp_url,
                    "status": 500,
                    "error": str(e)
                })

        logger.info(f"PIPELINE: Auditados {len(competitor_audits)} competidores (incluyendo fallidos).")
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
    def _enrich_fix_plan_with_audit_issues(fix_plan: List[Dict], target_audit: Dict[str, Any]) -> List[Dict]:
        """
        Enrich the fix_plan with specific issues extracted from target_audit data.
        This ensures the fix plan covers all the detailed issues found in the audit.
        """
        if not isinstance(fix_plan, list):
            fix_plan = []

        # Avoid duplicates by tracking added items (page_path + issue_code)
        existing_items = {(item.get("page_path", ""), item.get("issue_code", "")) for item in fix_plan}

        # Extract issues from target_audit
        new_items = []

        # 1. H1 Issues
        if target_audit.get("structure", {}).get("h1_check", {}).get("status") != "pass":
            pages_with_h1_issues = []
            audited_pages_count = target_audit.get("audited_pages_count", 1)
            if audited_pages_count > 1:
                # Multi-page audit
                audited_page_paths = target_audit.get("audited_page_paths", [])
                for path in audited_page_paths:
                    key = (path, "H1_MISSING")
                    if key not in existing_items:
                        new_items.append({
                            "page_path": path,
                            "issue_code": "H1_MISSING",
                            "priority": "CRITICAL",
                            "description": f"H1 missing or multiple on page {path}",
                            "snippet": "",
                            "suggestion": f"Add a unique, descriptive H1 tag to {path}"
                        })
                        existing_items.add(key)
            else:
                # Single page
                key = ("/", "H1_MISSING")
                if key not in existing_items:
                    new_items.append({
                        "page_path": "/",
                        "issue_code": "H1_MISSING",
                        "priority": "CRITICAL",
                        "description": "Home page missing H1 tag",
                        "snippet": "",
                        "suggestion": "Add <h1> tag with main page title"
                    })
                    existing_items.add(key)

        # 2. Schema Issues
        if target_audit.get("schema", {}).get("schema_presence", {}).get("status") != "present":
            key = ("ALL_PAGES", "SCHEMA_MISSING")
            if key not in existing_items:
                new_items.append({
                    "page_path": "ALL_PAGES",
                    "issue_code": "SCHEMA_MISSING",
                    "priority": "CRITICAL",
                    "description": "No JSON-LD Schema.org markup found on any page",
                    "snippet": "",
                    "suggestion": "Implement Organization + WebSite Schema in <head> of all pages"
                })
                existing_items.add(key)

        # 3. Author Issues
        if target_audit.get("eeat", {}).get("author_presence", {}).get("status") != "pass":
            key = ("ALL_PAGES", "AUTHOR_MISSING")
            if key not in existing_items:
                new_items.append({
                    "page_path": "ALL_PAGES",
                    "issue_code": "AUTHOR_MISSING",
                    "priority": "HIGH",
                    "description": "Author information missing on all pages",
                    "snippet": "",
                    "suggestion": "Add author bio and Person Schema to content pages"
                })
                existing_items.add(key)

        # 4. Header Hierarchy Issues
        header_issues = target_audit.get("structure", {}).get("header_hierarchy", {}).get("issues", [])
        for issue in header_issues[:5]:  # Limit to 5
            page_path = issue.get("page_path", "/")
            key = (page_path, "H1_HIERARCHY_SKIP")
            if key not in existing_items:
                prev_tag = issue.get('prev_tag_html', '<h1>').strip('<>')
                current_tag = issue.get('current_tag_html', '<h3>').strip('<>')
                try:
                    prev_level = int(prev_tag[1:]) if prev_tag.startswith('h') else 1
                    next_level = prev_level + 1
                    suggestion = f"Fix header hierarchy by adding missing H{next_level} or changing to correct level"
                except ValueError:
                    suggestion = "Fix header hierarchy by adding missing header levels"

                new_items.append({
                    "page_path": page_path,
                    "issue_code": "H1_HIERARCHY_SKIP",
                    "priority": "HIGH",
                    "description": f"Header hierarchy skip: {prev_tag} -> {current_tag}",
                    "snippet": f"<{current_tag}>",
                    "suggestion": suggestion
                })
                existing_items.add(key)

        # 5. Long Paragraph Issues
        long_paragraph_pages = target_audit.get("content", {}).get("fragment_clarity", {}).get("pages_with_issues", [])
        for page_path in long_paragraph_pages[:3]:  # Limit to 3
            key = (page_path, "LONG_PARAGRAPH")
            if key not in existing_items:
                new_items.append({
                    "page_path": page_path,
                    "issue_code": "LONG_PARAGRAPH",
                    "priority": "MEDIUM",
                    "description": f"Long paragraphs found on {page_path}",
                    "snippet": "",
                    "suggestion": "Break long paragraphs into shorter ones with subheadings and bullet points"
                })
                existing_items.add(key)

        # 6. FAQ Missing
        if target_audit.get("content", {}).get("question_targeting", {}).get("status") != "pass":
            key = ("ALL_PAGES", "FAQ_MISSING")
            if key not in existing_items:
                new_items.append({
                    "page_path": "ALL_PAGES",
                    "issue_code": "FAQ_MISSING",
                    "priority": "MEDIUM",
                    "description": "No FAQ sections found on any page",
                    "snippet": "",
                    "suggestion": "Add FAQ sections with Schema.org FAQPage markup"
                })
                existing_items.add(key)

        # 7. Content Freshness Issues
        if len(target_audit.get("eeat", {}).get("content_freshness", {}).get("pages_missing_dates", [])) > 0:
            key = ("ALL_PAGES", "CONTENT_FRESHNESS_MISSING")
            if key not in existing_items:
                new_items.append({
                    "page_path": "ALL_PAGES",
                    "issue_code": "CONTENT_FRESHNESS_MISSING",
                    "priority": "MEDIUM",
                    "description": "Content freshness dates missing on multiple pages",
                    "snippet": "",
                    "suggestion": "Add publication and last modified dates to content"
                })
                existing_items.add(key)

        # 8. E-commerce Specific Issues (for retail sites like Farmalife)
        url = target_audit.get("url", "").lower()
        if any(keyword in url for keyword in ["farmacia", "pharmacy", "retail", "tienda", "store", "ecommerce", "shop"]):
            # Product Page Optimizations
            product_pages = [path for path in target_audit.get("audited_page_paths", []) if "/p" in path or "product" in path]
            for page_path in product_pages[:5]:  # Top 5 product pages
                # Product Schema
                key = (page_path, "PRODUCT_SCHEMA_MISSING")
                if key not in existing_items:
                    new_items.append({
                        "page_path": page_path,
                        "issue_code": "PRODUCT_SCHEMA_MISSING",
                        "priority": "CRITICAL",
                        "description": "Product page missing Product Schema markup - competitors have it",
                        "snippet": "",
                        "suggestion": "Add Product Schema: {\"@type\":\"Product\",\"name\":\"[Product Name]\",\"offers\":{\"@type\":\"Offer\",\"price\":\"[Price]\",\"priceCurrency\":\"ARS\",\"availability\":\"InStock\"}}"
                    })
                    existing_items.add(key)

                # Product Image Optimization
                key = (page_path, "PRODUCT_IMAGE_MISSING_ALT")
                if key not in existing_items:
                    new_items.append({
                        "page_path": page_path,
                        "issue_code": "PRODUCT_IMAGE_MISSING_ALT",
                        "priority": "HIGH",
                        "description": "Product images missing alt text for SEO",
                        "snippet": "<img src=\"product.jpg\" alt=\"\">",
                        "suggestion": "Add descriptive alt text: <img src=\"product.jpg\" alt=\"[Brand] [Product Name] [Size/Quantity] - [Key Benefit]\">"
                    })
                    existing_items.add(key)

            # Category Pages
            category_pages = [path for path in target_audit.get("audited_page_paths", []) if any(x in path for x in ["/categoria", "/category", "/cuidado", "/dermo"])]
            for page_path in category_pages[:3]:
                key = (page_path, "COLLECTION_SCHEMA_MISSING")
                if key not in existing_items:
                    new_items.append({
                        "page_path": page_path,
                        "issue_code": "COLLECTION_SCHEMA_MISSING",
                        "priority": "HIGH",
                        "description": "Category page missing CollectionPage Schema",
                        "snippet": "",
                        "suggestion": "Add CollectionPage + ItemList Schema for product listings to improve rich snippets"
                    })
                    existing_items.add(key)

            # Breadcrumb Navigation
            key = ("ALL_PAGES", "BREADCRUMB_SCHEMA_MISSING")
            if key not in existing_items:
                new_items.append({
                    "page_path": "ALL_PAGES",
                    "issue_code": "BREADCRUMB_SCHEMA_MISSING",
                    "priority": "HIGH",
                    "description": "Breadcrumb navigation missing Schema markup - competitors show rich snippets",
                    "snippet": "",
                    "suggestion": "Implement BreadcrumbList Schema: [{\"@type\":\"ListItem\",\"position\":1,\"name\":\"Home\",\"item\":\"https://...\"},...]"
                })
                existing_items.add(key)

            # Review/Rating System
            if not target_audit.get("schema", {}).get("schema_types") or "AggregateRating" not in str(target_audit.get("schema", {}).get("schema_types")):
                key = ("PRODUCT_PAGES", "REVIEW_SCHEMA_MISSING")
                if key not in existing_items:
                    new_items.append({
                        "page_path": "PRODUCT_PAGES",
                        "issue_code": "REVIEW_SCHEMA_MISSING",
                        "priority": "HIGH",
                        "description": "Product reviews missing structured data - competitors have ratings in SERP",
                        "snippet": "",
                        "suggestion": "Add AggregateRating Schema: {\"@type\":\"AggregateRating\",\"ratingValue\":\"4.5\",\"reviewCount\":\"128\"}"
                    })
                    existing_items.add(key)

            # Price Comparison Features
            key = ("ALL_PAGES", "PRICE_COMPARISON_MISSING")
            if key not in existing_items:
                new_items.append({
                    "page_path": "ALL_PAGES",
                    "issue_code": "PRICE_COMPARISON_MISSING",
                    "priority": "MEDIUM",
                    "description": "No price comparison or 'best price' messaging - competitors highlight price advantages",
                    "snippet": "",
                    "suggestion": "Add price comparison badges and 'Mejor Precio Garantizado' messaging with Offer Schema"
                })
                existing_items.add(key)

            # Mobile Cart Optimization
            key = ("CART_PAGE", "MOBILE_CART_OPTIMIZATION")
            if key not in existing_items:
                new_items.append({
                    "page_path": "CART_PAGE",
                    "issue_code": "MOBILE_CART_OPTIMIZATION",
                    "priority": "HIGH",
                    "description": "Cart page not optimized for mobile conversion - competitors have sticky add-to-cart",
                    "snippet": "",
                    "suggestion": "Implement sticky cart button, simplified checkout flow, and Cart Schema markup"
                })
                existing_items.add(key)

            # Internal Linking Strategy
            key = ("ALL_PAGES", "INTERNAL_LINKING_POOR")
            if key not in existing_items:
                new_items.append({
                    "page_path": "ALL_PAGES",
                    "issue_code": "INTERNAL_LINKING_POOR",
                    "priority": "MEDIUM",
                    "description": "Poor internal linking structure - products not well connected",
                    "snippet": "",
                    "suggestion": "Add related products sections, category links, and 'Frequently Bought Together' with Product Schema relationships"
                })
                existing_items.add(key)

        # Combine LLM-generated and extracted items
        enriched_fix_plan = fix_plan + new_items

        # Sort by priority (CRITICAL > HIGH > MEDIUM > LOW)
        priority_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        enriched_fix_plan.sort(key=lambda x: priority_order.get(x.get("priority", "MEDIUM"), 2))

        logger.info(f"Enriched fix_plan: {len(fix_plan)} LLM items + {len(new_items)} extracted = {len(enriched_fix_plan)} total")
        return enriched_fix_plan

    @staticmethod
    def _minimize_context(context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Minimiza el contexto para evitar exceder el límite de tokens (Kimi K2 262K).
        - Trunca snippets de resultados de búsqueda.
        - Remueve raw JSON-LD de las auditorías.
        - Limita cantidad de ítems en listas de keywords, backlinks, etc.
        """
        import copy
        minimized = copy.deepcopy(context)
        
        # 1. Minimizar search_results (Suele ser lo más pesado)
        if "search_results" in minimized and isinstance(minimized["search_results"], dict):
            for q_id, results in minimized["search_results"].items():
                if isinstance(results, dict) and "items" in results:
                    # Top 10 resultados, solo campos esenciales
                    minimized_items = []
                    for item in results["items"][:10]:
                        minimized_items.append({
                            "title": item.get("title"),
                            "link": item.get("link"),
                            "snippet": item.get("snippet", "")[:150] # Truncar snippet
                        })
                    minimized["search_results"][q_id] = {"items": minimized_items}
        
        # 2. Minimizar auditorías (remover raw_jsonld)
        def minimize_audit(audit):
            if not isinstance(audit, dict): return audit
            
            # Copia para no modificar original si no es deepcopy
            a = audit.copy()
            
            # Remover raw JSON-LD que puede ser masivo
            if "schema" in a and isinstance(a["schema"], dict):
                a["schema"] = a["schema"].copy()
                if "raw_jsonld" in a["schema"]:
                    a["schema"]["raw_jsonld"] = []
                if "raw_jsonld_found" in a["schema"]:
                    a["schema"]["raw_jsonld_found"] = []
            
            # Truncar h1_details si son muchos
            if "structure" in a and isinstance(a["structure"], dict):
                if "h1_details" in a["structure"] and isinstance(a["structure"]["h1_details"], list):
                    a["structure"]["h1_details"] = a["structure"]["h1_details"][:5]
            
            return a

        if "target_audit" in minimized:
            minimized["target_audit"] = minimize_audit(minimized["target_audit"])
            
        if "competitor_audits" in minimized and isinstance(minimized["competitor_audits"], list):
            minimized["competitor_audits"] = [minimize_audit(a) for a in minimized["competitor_audits"]]
        
        # 3. Limitar listas de inteligencia adicional
        list_keys = ["keywords", "backlinks", "rank_tracking", "llm_visibility", "ai_content_suggestions"]
        for key in list_keys:
            if key in minimized and isinstance(minimized[key], dict) and "items" in minimized[key]:
                minimized[key]["items"] = minimized[key]["items"][:20] # Max 20 ítems
            elif key in minimized and isinstance(minimized[key], list):
                minimized[key] = minimized[key][:20]

        # 4. Minimizar PageSpeed (ya suele estar minimizado pero por las dudas)
        if "pagespeed" in minimized and isinstance(minimized["pagespeed"], dict):
            for device in ["mobile", "desktop"]:
                if device in minimized["pagespeed"] and isinstance(minimized["pagespeed"][device], dict):
                    # Handle both 'opportunities' and 'diagnostics' as they both contain technical issues
                    for key in ["opportunities", "diagnostics"]:
                        if key in minimized["pagespeed"][device] and isinstance(minimized["pagespeed"][device][key], dict):
                            # Sort items by numericValue (savings/impact) if available
                            opps = minimized["pagespeed"][device][key]
                            # Safe sorting: extract items, sort by numericValue descending, take top 5
                            try:
                                sorted_items = sorted(
                                    [(k, v) for k, v in opps.items() if isinstance(v, dict)],
                                    key=lambda x: x[1].get("numericValue", 0) if x[1].get("numericValue") is not None else 0,
                                    reverse=True
                                )
                                minimized["pagespeed"][device][key] = dict(sorted_items[:5])
                            except Exception as e:
                                logger.warning(f"Error sorting {key} for {device}: {e}")
                                # Simple truncation as fallback
                                items = list(opps.items())[:5]
                                minimized["pagespeed"][device][key] = dict(items)

        return minimized

    @staticmethod
    def select_important_urls(all_urls: List[str], base_url: str, max_sample: int = 5) -> List[str]:
        """
        Selecciona una muestra representativa de URLs para auditar.
        Lógica extraída de ag2_pipeline.py
        """
        logger.info(f"PIPELINE: Seleccionando hasta {max_sample} URLs importantes de un total de {len(all_urls)} encontradas.")
        
        if not all_urls:
            logger.info("PIPELINE: No se encontraron URLs, usando la base URL.")
            return [base_url]
            
        import random
        from urllib.parse import urlparse
        
        parsed_base = urlparse(base_url)
        # Normalizar base URL
        norm_base_url = f"{parsed_base.scheme}://{parsed_base.hostname.lstrip('www.') if parsed_base.hostname else ''}{parsed_base.path or ''}"
        if norm_base_url.endswith("/") and len(norm_base_url) > 1:
            norm_base_url = norm_base_url[:-1]
            
        # Asegurar que la home esté incluida
        if norm_base_url not in all_urls:
            all_urls.insert(0, norm_base_url)
            
        sample = [all_urls[0]]
        
        # Preferir URLs cortas (arquitectura plana)
        short_urls = sorted(
            [u for u in all_urls if u != sample[0]], 
            key=lambda u: (u.count("/"), len(u))
        )
        
        for url in short_urls:
            if len(sample) >= max_sample:
                break
            if url not in sample:
                sample.append(url)
                
        logger.info(f"PIPELINE: URLs seleccionadas: {sample}")
        # Si falta para el máximo, tomar aleatorias
        remaining_urls = [u for u in all_urls if u not in sample]
        while len(sample) < max_sample and remaining_urls:
            idx = random.randint(0, len(remaining_urls) - 1)
            sample.append(remaining_urls.pop(idx))
            
        logger.info(f"Seleccionadas {len(sample)} URLs para auditar del sitio objetivo: {sample}")
        return sample

    @staticmethod
    def aggregate_summaries(summaries: List[Dict], base_url: str) -> Dict:
        """
        Agrega múltiples resúmenes de auditoría en uno solo representativo del sitio.
        Lógica extraída de ag2_pipeline.py
        """
        if not summaries:
            return {"error": "No summaries provided"}

        from urllib.parse import urlparse
        import re

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
            s["audited_pages_count"] = 1
            return s

        logger.info(f"Agregando {len(summaries)} resúmenes de auditoría del sitio objetivo...")

        pages_with_h1_pass = [
            get_path_from_url(s["url"], base_url)
            for s in summaries
            if s.get("structure", {}).get("h1_check", {}).get("status") == "pass"
        ]
        pages_with_author = [
            get_path_from_url(s["url"], base_url)
            for s in summaries
            if s.get("eeat", {}).get("author_presence", {}).get("status") == "pass"
        ]
        pages_with_schema = [
            get_path_from_url(s["url"], base_url)
            for s in summaries
            if s.get("schema", {}).get("schema_presence", {}).get("status") == "present"
        ]
        pages_with_faqs = [
            get_path_from_url(s["url"], base_url)
            for s in summaries
            if s.get("content", {}).get("question_targeting", {}).get("status") == "pass"
        ]

        header_hierarchy_issues = []
        long_paragraph_issues = []
        for s in summaries:
            path = get_path_from_url(s["url"], base_url)
            clarity_details = s.get("content", {}).get("fragment_clarity", {}).get("details", "")
            if "long_paragraphs=" in clarity_details:
                try:
                    count = int(clarity_details.split("=")[-1])
                    if count > 0:
                        long_paragraph_issues.append(path)
                except:
                    pass

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
            all_schema_types.update(s.get("schema", {}).get("schema_types", []))
            if s.get("schema", {}).get("raw_jsonld"):
                all_raw_jsonld.append({
                    "page_path": path,
                    "raw_json": s["schema"]["raw_jsonld"][0]
                })

            h1_details = s.get("structure", {}).get("h1_check", {}).get("details", {})
            if h1_details:
                all_h1s.append(
                    f"[{path}] -> H1: {h1_details.get('example', 'N/A')} (Count: {h1_details.get('count', 0)})"
                )
            if s.get("meta_robots"):
                all_meta_robots.add(s["meta_robots"])

            eeat_stats = s.get("eeat", {}).get("citations_and_sources", {})
            total_external += eeat_stats.get("external_links", 0)
            total_authoritative += eeat_stats.get("authoritative_links", 0)
            
            struct = s.get("structure", {})
            total_lists += struct.get("list_usage", {}).get("count", 0)
            total_tables += struct.get("table_usage", {}).get("count", 0)

            if struct.get("header_hierarchy", {}).get("issues"):
                header_hierarchy_issues.append({
                    "page_path": path,
                    "issue": struct["header_hierarchy"]["issues"][0]
                })

        avg_semantic_score = round(
            sum(s.get("structure", {}).get("semantic_html", {}).get("score_percent", 0) for s in summaries) / len(summaries),
            1,
        )
        avg_conversational = round(
            sum(s.get("content", {}).get("conversational_tone", {}).get("score", 0) for s in summaries) / len(summaries),
            1,
        )

        # Usar la home como base para el resumen si es posible
        home_summary = summaries[0]

        aggregated = {
            "url": base_url,
            "status": 200,
            "is_aggregate": True,
            "generated_at": home_summary.get("generated_at"),
            "audited_pages_count": len(summaries),
            "audited_page_paths": [get_path_from_url(s["url"], base_url) for s in summaries],
            "_individual_page_audits": [
                {"url": s["url"], "index": i, "data": s} for i, s in enumerate(summaries)
            ],
            "structure": {
                "h1_check": {
                    "status": "warn" if len(pages_with_h1_pass) < len(summaries) else "pass",
                    "details": {"example": f"{len(pages_with_h1_pass)}/{len(summaries)} páginas tienen H1 válido"},
                    "examples": all_h1s,
                },
                "header_hierarchy": {
                    "issues": header_hierarchy_issues,
                },
                "semantic_html": {"score_percent": avg_semantic_score},
                "list_usage": {"count": total_lists},
                "table_usage": {"count": total_tables},
            },
            "content": {
                "fragment_clarity": {
                    "score": max(1, 10 - len(long_paragraph_issues)),
                    "pages_with_issues": long_paragraph_issues,
                },
                "conversational_tone": {"score": avg_conversational},
                "question_targeting": {
                    "status": "pass" if pages_with_faqs else "warn",
                    "pages_with_faqs": pages_with_faqs,
                },
            },
            "eeat": {
                "author_presence": {
                    "status": "warn" if len(pages_with_author) < len(summaries) else "pass",
                    "pages_with_author": pages_with_author,
                },
                "citations_and_sources": {
                    "external_links": total_external,
                    "authoritative_links": total_authoritative,
                },
            },
            "schema": {
                "schema_presence": {
                    "status": "warn" if len(pages_with_schema) < len(summaries) else "pass",
                    "pages_with_schema": pages_with_schema,
                },
                "schema_types": list(all_schema_types),
                "raw_jsonld": [item["raw_json"] for item in all_raw_jsonld],
            },
            "meta_robots": list(all_meta_robots)[0] if all_meta_robots else "",
        }
        return aggregated

    async def run_complete_audit(
        self,
        url: str,
        target_audit: Optional[Dict[str, Any]] = None,
        audit_id: Optional[int] = None,
        pagespeed_data: Optional[Dict[str, Any]] = None,
        additional_context: Optional[Dict[str, Any]] = None,
        crawler_service: Optional[callable] = None,
        audit_local_service: Optional[callable] = None,
        llm_function: Optional[callable] = None,
        google_api_key: Optional[str] = None,
        google_cx_id: Optional[str] = None,
        minimal_audit: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute complete audit pipeline.

        This is the main pipeline method that orchestrates the entire audit process.
        """
        try:
            # Step 1.5: Crawl and audit additional target pages if crawler_service is provided
            if crawler_service and audit_local_service:
                logger.info(f"Iniciando rastreo del sitio objetivo para auditoría multi-página: {url}")
                try:
                    all_target_urls = await crawler_service(url, max_pages=100)
                    important_target_urls = self.select_important_urls(all_target_urls, url, max_sample=50)
                    
                    target_summaries = []
                    total_to_audit = len(important_target_urls)
                    logger.info(f"PIPELINE: Iniciando auditoría de {total_to_audit} páginas seleccionadas del objetivo.")
                    
                    for idx, t_url in enumerate(important_target_urls):
                        logger.info(f"PIPELINE: Auditing target page {idx+1}/{total_to_audit}: {t_url}")
                        summary = await audit_local_service(t_url)
                        if isinstance(summary, (tuple, list)):
                            summary = summary[0]
                        if summary and summary.get("status") == 200:
                            target_summaries.append(summary)
                        else:
                            logger.warning(f"PIPELINE: Page audit failed or returned non-200 for {t_url}")
                    
                    if target_summaries:
                        target_audit = self.aggregate_summaries(target_summaries, url)
                        logger.info(f"Auditoría agregada del objetivo completada con {len(target_summaries)} páginas.")
                except Exception as crawl_err:
                    logger.error(f"Error durante el rastreo/auditoría multi-página del objetivo: {crawl_err}")
                    # Continuamos con lo que tengamos (probablemente solo la home)

            # Step 1: Analyze external intelligence (Agent 1)
            logger.info("PIPELINE: Iniciando Agente 1 (Inteligencia Externa)...")
            external_intelligence, search_queries = await self.analyze_external_intelligence(
                target_audit, llm_function
            )
            logger.info(f"PIPELINE: Agente 1 completado. Consultas generadas: {len(search_queries)}")

            # Step 2: Run Google searches for competitors and authority
            search_results = {}
            if google_api_key and google_cx_id:
                logger.info(f"PIPELINE: Google API Key detectada. Ejecutando {len(search_queries)} búsquedas...")
                # Robustness check: Ensure we have a competitors query even if Agent 1 failed
                has_competitor_query = any(q.get("id") == "competitors" for q in search_queries)
                if not has_competitor_query:
                    category = external_intelligence.get("category", "main services")
                    logger.warning(f"Agent 1 missed 'competitors' query. Adding fallback for category: {category}")
                    search_queries.append({"id": "competitors", "query": category})

                for query_data in search_queries:
                    query_id = query_data.get("id")
                    query_text = query_data.get("query")
                    if not query_id or not query_text:
                        continue
                        
                    logger.info(f"Step 2: Google search [{query_id}]: {query_text}")
                    search_results[query_id] = await self.run_google_search(
                        query_text, google_api_key, google_cx_id, num_results=20
                    )
            else:
                logger.warning("PIPELINE: Google API Key o CSE ID faltante. Se omitirá la búsqueda de competidores externos.")

            # Step 3: Find and audit competitors
            raw_competitor_items = search_results.get("competitors", {}).get("items", [])
            logger.info(f"Step 3: Found {len(raw_competitor_items)} raw search results for competitors.")
            
            competitor_urls = self.filter_competitor_urls(raw_competitor_items, url)
            logger.info(f"Step 3: Filtered to {len(competitor_urls)} real competitor domains: {competitor_urls}")
            
            if competitor_urls and audit_local_service:
                logger.info(f"Step 3: Commencing crawl of {len(competitor_urls)} competitors...")
                competitor_audits = await self.generate_competitor_audits(
                    competitor_urls, audit_local_service
                )
            else:
                logger.warning("Step 3: Skipping competitor audits (no URLs found or service missing)")
                competitor_audits = []

            # Step 4: Generate report (Agent 2)
            # If minimal_audit is True, we only generate the fix plan JSON.
            report_markdown, fix_plan = await self.generate_report(
                target_audit=target_audit,
                external_intelligence=external_intelligence,
                search_results=search_results,
                competitor_audits=competitor_audits,
                pagespeed_data=pagespeed_data,
                llm_function=llm_function,
                minimal_audit=minimal_audit
            )

            # Step 5: Prepare final result
            result = {
                "url": url,
                "target_audit": target_audit,
                "external_intelligence": external_intelligence,
                "search_results": search_results,
                "competitor_audits": competitor_audits,
                "pagespeed": pagespeed_data,
                "report_markdown": report_markdown,
                "fix_plan": fix_plan,
                "status": "completed"
            }

            logger.info(f"Complete audit pipeline finished successfully for {url}")
            return result

        except Exception as e:
            logger.error(f"Error in complete audit pipeline for {url}: {e}", exc_info=True)
            return {
                "url": url,
                "error": str(e),
                "status": "failed"
            }

    @staticmethod
    async def generate_report(
        target_audit: Dict[str, Any],
        external_intelligence: Dict[str, Any],
        search_results: Dict[str, Any],
        competitor_audits: List[Dict[str, Any]],
        pagespeed_data: Optional[Dict[str, Any]] = None,
        keywords_data: Optional[Dict[str, Any]] = None,
        backlinks_data: Optional[Dict[str, Any]] = None,
        rank_tracking_data: Optional[Dict[str, Any]] = None,
        llm_visibility_data: Optional[Dict[str, Any]] = None,
        ai_content_suggestions: Optional[Dict[str, Any]] = None,
        llm_function: Optional[callable] = None,
        minimal_audit: bool = False,
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

            # --- BRANCH: MINIMAL AUDIT (FAST FLOW) ---
            if minimal_audit:
                logger.info("Executing MINIMAL report flow (Fix Plan only)")
                if llm_function is None:
                    raise ValueError("LLM function required for minimal audit.")

                system_prompt = """Eres un experto en SEO/GEO. Tu tarea es analizar los datos de la auditoría ('target_audit') y generar un PLAN DE ACCIÓN (fix_plan) en formato JSON.
                No generes el informe en Markdown. Devuelve SOLO el JSON array de tareas.
                
                Cada objeto debe tener:
                - page_path: ruta de la página o "ALL_PAGES"
                - issue_code: código corto del error
                - priority: CRITICAL, HIGH, MEDIUM, LOW
                - description: descripción del problema
                - snippet: fragmento de HTML si aplica
                - suggestion: cómo arreglarlo
                """
                report_text = await llm_function(
                    system_prompt=system_prompt,
                    user_prompt=json.dumps({"target_audit": target_audit}, ensure_ascii=False)
                )
                
                # Markdown placeholder for dashboard
                markdown_report = "# Reporte GEO (Pendiente)\n\nEl reporte completo se generará automáticamente con el PDF."
                
                # Skip all complex context building and PageSpeed processing
                # The parsing logic below will handle report_text
            else:
                # --- BRANCH: FULL AUDIT (PDF FLOW) ---
                # Normalizar PageSpeed (asegurar que sea dict)
                if not pagespeed_data:
                    pagespeed_data = {}
                
                # Helper para normalizar inteligencia GEO/IA
                def normalize_items(data, list_key=None):
                    if not data: return {"items": [], "total": 0}
                    if isinstance(data, list): return {"items": data, "total": len(data)}
                    if isinstance(data, dict):
                        if "items" in data: return data
                        # Si tiene una lista bajo una clave específica (ej: 'keywords', 'rankings', 'top_backlinks')
                        for k in [list_key, "keywords", "rankings", "top_backlinks", "items"]:
                            if k and k in data and isinstance(data[k], list):
                                return {"items": data[k], "total": data.get("total") or data.get("total_keywords") or len(data[k])}
                        return {"items": [], "total": 0}
                    return {"items": [], "total": 0}

                # Normalizar todos los inputs GEO e IA
                keywords_data = normalize_items(keywords_data, "keywords")
                backlinks_data = normalize_items(backlinks_data, "top_backlinks")
                rank_tracking_data = normalize_items(rank_tracking_data, "rankings")
                llm_visibility_data = normalize_items(llm_visibility_data)
                ai_content_suggestions = normalize_items(ai_content_suggestions)

                # Pre-generar un resumen de PageSpeed para el LLM ya que el crudo puede ser masivo
                pagespeed_analysis = ""
                pagespeed_metrics_table = "Datos no disponibles para PageSpeed."
                
                if pagespeed_data and isinstance(pagespeed_data, dict):
                    try:
                        m = "mobile"
                        d = "desktop"
                        mobile = pagespeed_data.get(m, {})
                        desktop = pagespeed_data.get(d, {})
                        
                        has_mobile_data = mobile.get("performance_score") is not None or mobile.get("core_web_vitals")
                        has_desktop_data = desktop.get("performance_score") is not None or desktop.get("core_web_vitals")
                        has_any_data = has_mobile_data or has_desktop_data
                        
                        if has_any_data:
                            def get_val(dev, key):
                                val = pagespeed_data.get(dev, {}).get("core_web_vitals", {}).get(key, 0)
                                return val if val is not None else 0
                            
                            def fmt_s(ms): 
                                try:
                                    if ms and ms > 0:
                                        return f"{float(ms)/1000:.2f}s"
                                    return "N/A"
                                except: 
                                    return "N/A"

                            mobile_score = mobile.get('performance_score', 'N/A')
                            desktop_score = desktop.get('performance_score', 'N/A')
                            
                            pagespeed_metrics_table = f"""
| Métrica | Mobile (Lighthouse) | Desktop (Lighthouse) |
| :--- | :--- | :--- |
| Performance Score | {mobile_score}/100 | {desktop_score}/100 |
| Largest Contentful Paint (LCP) | {fmt_s(get_val(m, 'lcp'))} | {fmt_s(get_val(d, 'lcp'))} |
| FID / INP (Input Delay) | {get_val(m, 'fid') or get_val(m, 'inp') or 0:.0f}ms | {get_val(d, 'fid') or get_val(d, 'inp') or 0:.0f}ms |
| Cumulative Layout Shift (CLS) | {get_val(m, 'cls') or 0:.3f} | {get_val(d, 'cls') or 0:.3f} |
| First Contentful Paint (FCP) | {fmt_s(get_val(m, 'fcp'))} | {fmt_s(get_val(d, 'fcp'))} |
| Time to First Byte (TTFB) | {get_val(m, 'ttfb') or 0:.0f}ms | {get_val(d, 'ttfb') or 0:.0f}ms |
"""
                        if llm_function and has_any_data:
                            pagespeed_analysis = await PipelineService.generate_pagespeed_analysis(
                                pagespeed_data, llm_function
                            )
                    except Exception as ps_err:
                        logger.warning(f"Error preparing pagespeed data for report: {ps_err}")

                final_context = {
                    "target_audit": target_audit,
                    "external_intelligence": external_intelligence,
                    "search_results": search_results,
                    "competitor_audits": competitor_audits,
                    "pagespeed_metrics": pagespeed_metrics_table,
                    "pagespeed": pagespeed_data,
                    "pagespeed_analysis": pagespeed_analysis,
                    "keywords": keywords_data,
                    "backlinks": backlinks_data,
                    "rank_tracking": rank_tracking_data,
                    "llm_visibility": llm_visibility_data,
                    "ai_content_suggestions": ai_content_suggestions,
                }

                # Minimizar contexto para no exceder límites de tokens (Kimi K2 256K)
                final_context = PipelineService._minimize_context(final_context)
                final_context_input = json.dumps(final_context, ensure_ascii=False, indent=2)

                # Llamar LLM con contexto completo
                report_text = await llm_function(
                    system_prompt=PipelineService.REPORT_PROMPT_V11_COMPLETE,
                    user_prompt=final_context_input,
                )

                # Parsear respuesta (buscar delimitador)
                delimiter = "---START_FIX_PLAN---"
                
                # Robust detection: use regex to handle case and spacing variations
                import re
                # More flexible delimiter patterns
                delimiter_patterns = [
                    r"---START_FIX_PLAN---",
                    r"---\s*START_FIX_PLAN\s*---",
                    r"START_FIX_PLAN",
                    r"fix_plan",
                    r"FIX_PLAN"
                ]

                match = None
                for pattern in delimiter_patterns:
                    match = re.search(pattern, report_text, re.IGNORECASE)
                    if match:
                        logger.info(f"Found delimiter with pattern: {pattern}")
                        break
                
                logger.info(f"Parsing LLM response, looking for delimiter: ---START_FIX_PLAN---")

                if match:
                    idx = match.start()
                    # We look for the start of the JSON block after the delimiter
                    # often the LLM puts it on the next line
                    md_candidate = report_text[:idx].strip()
                    json_candidate = report_text[match.end():].strip()
                    logger.info(f"Found delimiter at position {idx}, JSON candidate length: {len(json_candidate)}")
                elif "```json" in report_text.strip():
                    # Fallback: if no delimiter but contains a json block
                    logger.info("Delimiter not found, but detected JSON block.")
                    last_json_start = report_text.rfind("```json")
                    md_candidate = report_text[:last_json_start].strip()
                    json_candidate = report_text[last_json_start:].strip()
                else:
                    logger.warning("No delimiter or JSON block found in LLM response")
                    md_candidate = None
                    json_candidate = None

                if md_candidate is not None:
                    # In minimal mode, we keep the placeholder set earlier
                    if not minimal_audit:
                        # Limpiar bloques de código del markdown
                        if md_candidate.startswith("```markdown"):
                            md_candidate = md_candidate[11:]
                        if md_candidate.endswith("```"):
                            md_candidate = md_candidate[:-3]
                        markdown_report = md_candidate.strip()

                    # Parsear JSON del fix plan
                    logger.info(f"Parsing JSON candidate: {json_candidate[:200]}...")
                    parsed_json_part = PipelineService.parse_agent_json_or_raw(
                        json_candidate, default_key="fix_plan_raw"
                    )

                    if isinstance(parsed_json_part, list):
                        fix_plan = parsed_json_part
                        logger.info(f"Successfully parsed fix_plan with {len(fix_plan)} items from LLM")
                    else:
                        fix_plan = parsed_json_part.get("fix_plan", [])
                        logger.info(f"Parsed fix_plan from dict, got {len(fix_plan)} items")

                    if not fix_plan:
                        logger.warning("LLM generated empty fix_plan, will rely on enrichment")
                else:
                    logger.warning("No markdown candidate found. Attempting old-style parsing or fallback.")
                    logger.info(f"LLM Response preview: {report_text[:500]}...")
                    # Si no hay delimitador, intentamos buscar cualquier JSON al final
                    import re
                    json_match = re.search(r'(\[[\s\S]*\])', report_text.strip())
                    if json_match:
                        try:
                            fix_plan = json.loads(json_match.group(1))
                            if not minimal_audit:
                                markdown_report = report_text[:json_match.start()].strip()
                            logger.info(f"Parsed fallback fix_plan with {len(fix_plan)} items")
                        except Exception as e:
                            logger.error(f"Failed to parse fallback JSON: {e}")
                            markdown_report = report_text[:2000]
                            fix_plan = []
                    else:
                        logger.warning("No JSON array found in response")
                        if not minimal_audit:
                            markdown_report = report_text[:2000]
                        fix_plan = []

            # Always enrich fix plan with additional specific issues from audit data
            # This ensures comprehensive coverage even if LLM fails to generate some issues
            fix_plan = PipelineService._enrich_fix_plan_with_audit_issues(fix_plan or [], target_audit)

            logger.info("Agente 2: Reporte generado exitosamente")
            return markdown_report, fix_plan

        except Exception as e:
            logger.exception(f"Error en Agente 2: {e}")
            return markdown_report, []


# Funciones de compatibilidad
async def run_initial_audit(
    url: str,
    target_audit: Optional[Dict[str, Any]] = None,
    audit_id: Optional[int] = None,
    llm_function: Optional[callable] = None,
    google_api_key: Optional[str] = None,
    google_cx_id: Optional[str] = None,
    crawler_service: Optional[callable] = None,
    audit_local_service: Optional[callable] = None,
) -> Dict[str, Any]:
    """
    Ejecuta SOLO la auditoría inicial (Rastreo + Competidores + Errores).
    NO carga ni procesa keywords, backlinks ni reporte markdown.
    """
    from .pipeline_service import PipelineService
    pipeline = PipelineService()
    return await pipeline.run_complete_audit(
        url=url,
        target_audit=target_audit,
        audit_id=audit_id,
        pagespeed_data=None,
        additional_context=None,
        crawler_service=crawler_service,
        audit_local_service=audit_local_service,
        llm_function=llm_function,
        google_api_key=google_api_key,
        google_cx_id=google_cx_id,
        minimal_audit=True,
    )

async def run_complete_audit(
    url: str,
    target_audit: Optional[Dict[str, Any]] = None,
    audit_id: Optional[int] = None,
    pagespeed_data: Optional[Dict[str, Any]] = None,
    additional_context: Optional[Dict[str, Any]] = None,
    crawler_service: Optional[callable] = None,
    audit_local_service: Optional[callable] = None,
    llm_function: Optional[callable] = None,
    google_api_key: Optional[str] = None,
    google_cx_id: Optional[str] = None,
    minimal_audit: bool = False,
) -> Dict[str, Any]:
    """Wrapper para ejecución completa (usado en PDF y re-auditorías)."""
    from .pipeline_service import PipelineService
    pipeline = PipelineService()
    return await pipeline.run_complete_audit(
        url=url,
        target_audit=target_audit,
        audit_id=audit_id,
        pagespeed_data=pagespeed_data,
        additional_context=additional_context,
        crawler_service=crawler_service,
        audit_local_service=audit_local_service,
        llm_function=llm_function,
        google_api_key=google_api_key,
        google_cx_id=google_cx_id,
        minimal_audit=minimal_audit,
    )


# Alias for backward compatibility
run_complete_audit_pipeline = run_complete_audit
