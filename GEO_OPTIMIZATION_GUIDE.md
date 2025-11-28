# 🤖 GEO Optimization Guide - Domina la Búsqueda con IA

## 🎯 ¿Qué es GEO?

**GEO (Generative Engine Optimization)** es el proceso de optimizar contenido para ser **descubierto, entendido y CITADO** por Grandes Modelos de Lenguaje (LLMs) como ChatGPT, Gemini, Claude y Perplexity.

A diferencia del SEO tradicional (que busca clicks en una lista de enlaces), el GEO busca ser la **fuente de la respuesta** generada por la IA.

---

## 📊 El GEO Score (0-100)

Nuestro sistema evalúa tu contenido en 6 pilares fundamentales:

### 1. Estructura (20%)
**Objetivo:** Facilitar la extracción de "fragmentos" de información.
- ✅ **Formato Q&A:** Preguntas claras con respuestas directas.
- ✅ **Listas y Tablas:** Datos estructurados visualmente.
- ✅ **Jerarquía:** H1 > H2 > H3 lógica.
- ✅ **Pirámide Invertida:** Respuesta directa al inicio, detalles después.

### 2. E-E-A-T (25%) - CRÍTICO
**Objetivo:** Demostrar que eres una fuente confiable.
- ✅ **Autor Identificado:** Nombre, biografía, credenciales.
- ✅ **Fuentes Citadas:** Enlaces a estudios, .edu, .gov.
- ✅ **Experiencia:** Uso de "yo", "nosotros", casos reales.
- ✅ **Datos Originales:** Estadísticas propias o investigación única.

### 3. Contenido (20%)
**Objetivo:** Ser conversacional y natural.
- ✅ **Lenguaje Natural:** Evitar keyword stuffing.
- ✅ **Contexto Semántico:** Uso de sinónimos y conceptos relacionados.
- ✅ **Profundidad:** Cubrir el tema exhaustivamente (>800 palabras).

### 4. Schema Markup (15%)
**Objetivo:** Hablar el idioma de las máquinas.
- ✅ **Article Schema:** Para blogs y noticias.
- ✅ **FAQPage Schema:** Para secciones de preguntas.
- ✅ **Organization Schema:** Para la entidad de la marca.

### 5. Técnico (10%)
**Objetivo:** Accesibilidad y velocidad.
- ✅ **HTML Semántico:** `<article>`, `<section>`, `<nav>`.
- ✅ **Metadata:** Títulos y descripciones optimizados.
- ✅ **Velocidad:** Carga rápida para crawlers.

### 6. Citación Actual (10%)
**Objetivo:** Medir visibilidad actual.
- ✅ **Menciones en LLMs:** Frecuencia con la que la marca aparece en respuestas.

---

## 🚀 Cómo Usar el GEO Auditor

### 1. Auditar un Repositorio (SEO + GEO)

```bash
POST /api/github/audit-blogs-geo/{connection_id}/{repo_id}
```

**Lo que obtienes:**
- Reporte completo de todos los blogs.
- **GEO Score** individual por blog.
- Lista de **GEO Issues** específicos (ej: "Falta formato Q&A").
- Potencial de citación ("High", "Medium", "Low").

### 2. Ver GEO Score de una Auditoría

```bash
GET /api/github/geo-score/{audit_id}
```

**Respuesta:**
```json
{
  "overall_score": 65.5,
  "grade": "B-",
  "citation_potential": "Medium",
  "breakdown": {
    "structure": { "score": 80, "description": "..." },
    "eeat": { "score": 40, "description": "Falta autor y fuentes" },
    ...
  },
  "recommendations": [
    {
      "priority": "CRITICAL",
      "action": "Agregar firmas de autor con biografía"
    },
    {
      "priority": "HIGH",
      "action": "Implementar sección FAQ con Schema"
    }
  ]
}
```

### 3. Aplicar Fixes GEO Automáticamente

```bash
POST /api/github/create-geo-fixes-pr/{connection_id}/{repo_id}
{
  "blog_paths": ["app/blog/post-1/page.tsx"],
  "include_geo": true
}
```

**Fixes que aplica:**
- 🔧 Agrega metadata de autor.
- 🔧 Estructura introducciones como pirámide invertida.
- 🔧 Sugiere secciones FAQ.
- 🔧 Agrega Schema markup faltante.

---

## 💡 Estrategias de Optimización

### Para Blogs Existentes
1. **Agregar Autor:** Asegúrate que cada post tenga un autor real visible.
2. **Añadir FAQ:** Al final de cada post, agrega 3-5 preguntas comunes con respuestas concisas.
3. **Citar Fuentes:** Enlaza a 2-3 fuentes de alta autoridad para respaldar afirmaciones.

### Para Contenido Nuevo
1. **Empezar con la Respuesta:** Las primeras 2-3 oraciones deben responder la intención principal del usuario.
2. **Usar "Yo" y "Nosotros":** Comparte experiencia personal para mejorar E-E-A-T.
3. **Incluir Datos Únicos:** Si puedes, agrega una estadística o dato que solo tú tengas.

---

## 📈 Interpretando los Resultados

| Score | Grado | Significado | Acción |
|-------|-------|-------------|--------|
| 90-100| A+ | **Líder de IA** | Mantener y monitorear. |
| 80-89 | A/A-| **Optimizado** | Pequeños ajustes en E-E-A-T. |
| 70-79 | B | **Bueno** | Mejorar estructura y schema. |
| 60-69 | C | **Promedio** | Riesgo de ser ignorado por LLMs. |
| < 60  | D/F | **Invisible** | Requiere reestructuración completa. |

---

## 🤖 ¿Por qué importa esto?

Los motores de búsqueda están cambiando de **"Buscadores"** a **"Motores de Respuesta"**.
- **Antes:** Usuario busca -> Click en 10 enlaces -> Lee -> Sintetiza.
- **Ahora:** Usuario pregunta -> IA sintetiza respuesta -> Cita fuentes.

Si tu contenido no está optimizado para GEO, **la IA no lo entenderá, no confiará en él y no lo citará.**

---

**GEO Auditor** te da la ventaja competitiva para ser la voz confiable en la era de la IA.
