# 📝 Blog Auditor - Complete Guide

## 🎯 ¿Qué hace?

El **Blog Auditor** escanea automáticamente TODOS los archivos de blog en un repositorio de GitHub y genera un reporte detallado de issues SEO para cada uno.

**En 1 click:**
- ✅ Encuentra todos los blogs (Next.js, Gatsby, Hugo, Jekyll, Astro)
- ✅ Audita cada blog individualmente  
- ✅ Detecta 8 tipos de issues SEO
- ✅ Genera fixes aplicables automáticamente
- ✅ Puede crear un PR masivo con todos los fixes

---

## 🚀 Quick Start

### Paso 1: Auditar Blogs de un Repo

```bash
POST http://localhost:8000/api/github/audit-blogs/{connection_id}/{repo_id}

#Response:
{
  "status": "completed",
  "repo": "tu-usuario/mi-blog",
  "site_type": "nextjs",
  "summary": {
    "total_blogs": 42,
    "blogs_with_issues": 35,
    "missing_meta_description": 20,
    "missing_title": 5,
    "poor_h1": 12,
    "no_schema": 40,
    "poor_readability": 8,
    "missing_images": 15,
    "broken_structure": 10,
    "outdated_content": 3
  },
  "blogs": [
    {
      "file_path": "app/blog/seo-guide/page.tsx",
      "title": "Complete SEO Guide 2024",
      "url_slug": "seo-guide",
      "word_count": 2500,
      "published_date": "2024-01-15",
      "author": "John Doe",
      "issues": [
        {
          "type": "missing_meta_description",
          "severity": "critical",
          "message": "Blog post missing meta description",
          "recommendation": "Add SEO-optimized meta description (150-160 chars)"
        },
        {
          "type": "no_schema",
          "severity": "high",
          "message": "Blog post missing structured data (schema.org)",
          "recommendation": "Add Article schema with author, date, publisher"
        }
      ],
      "issue_count": 2,
      "severity_score": 40
    }
    // ... 41 blogs más
  ],
  "audited_at": "2024-11-26T18:00:00Z"
}
```

### Paso 2: Crear PR con Fixes

```bash
POST http://localhost:8000/api/github/create-blog-fixes-pr/{connection_id}/{repo_id}
{
  "blog_paths": [
    "app/blog/seo-guide/page.tsx",
    "app/blog/ai-tools/page.tsx",
    "app/blog/content-marketing/page.tsx"
  ]
}

# Response:
{
  "status": "success",
  "pr": {
    "id": "pr-123",
    "pr_number": 45,
    "html_url": "https://github.com/.../pull/45",
    "title": "🔴 Critical Blog SEO Fixes - 15 improvements",
    "files_changed": 3
  },
  "fixes_applied": 15,
  "blogs_fixed": 3
}
```

---

## 📊 Tipos de Issues Detectados

### 1. **Missing Meta Description** (Crítico)
```
✗ Blog sin meta description
✗ Meta description < 120 caracteres

✓ Meta description 150-160 caracteres
✓ Keyword incluido
✓ Call-to-action claro
```

### 2. **Missing/Poor Title** (Crítico)
```
✗ Blog sin title tag
✗ Title > 70 caracteres

✓ Title 50-60 caracteres
✓ Keyword al inicio
✓ Descriptivo y atractivo
```

### 3. **Poor H1** (Crítico)
```
✗ Sin H1
✗ Múltiples H1 (confuso para SEO)

✓ Un solo H1
✓ Coincide con title
✓ Incluye keyword principal
```

### 4. **No Schema Markup** (Alto)
```
✗ Sin structured data

✓ Article schema present
✓ Incluye: author, date, publisher
✓ Validado por Google
```

### 5. **Poor Readability** (Alto)
```
✗ < 300 palabras (muy corto)

✓ 800-2000 palabras
✓ Subtítulos cada 300 palabras
✓ Listas y bullets
```

### 6. **Missing Images** (Medio)
```
✗ Sin imágenes
✗ Imágenes sin alt text

✓ 1-3 imágenes relevantes
✓ Todas con alt text descriptivo
✓ Optimizadas para web
```

### 7. **Broken Structure** (Medio)
```
✗ Sin H2/H3 subheadings

✓ Estructura H1 > H2 > H3 lógica
✓ No skipping de niveles
✓ Escanneable
```

### 8. **Outdated Content** (Bajo)
```
✗ Publicado hace > 1 año

✓ Fresco o actualizado
✓ Estadísticas recientes
✓ Links vigentes
```

---

## 🎨 Frameworks Soportados

### Next.js ✅
```typescript
// App Router: app/blog/[slug]/page.tsx
export const metadata = {
  title: "...",
  description: "..."
}

// Pages Router: pages/blog/*.tsx
<Head>
  <title>...</title>
  <meta name="description" content="..." />
</Head>
```

**Detecta:**
- Carpetas `app/blog` y `pages/blog`
- Archivos `page.tsx`, `page.jsx`, `page.mdx`
- Metadata exports
- Head components

### Gatsby ✅
```markdown
---
title: "My Blog Post"
description: "..."
date: "2024-01-15"
author: "John Doe"
---

# Content here
```

**Detecta:**
- `src/pages/blog/*.mdx`
- `content/blog/*.md`
- Frontmatter metadata
- React Helmet

### Hugo ✅
```markdown
---
title: "My Post"
description: "..."
date: 2024-01-15
---

# Content
```

**Detecta:**
- `content/posts/*.md`
- `content/blog/*.md`
- TOML/YAML frontmatter

### Jekyll ✅
```markdown
---
layout: post
title: "My Post"
date: 2024-01-15
---

Content here
```

**Detecta:**
- `_posts/*.md`
- Fecha en filename: `2024-01-15-title.md`
- YAML frontmatter

### Astro ✅
```astro
---
title: "My Post"
description: "..."
pubDate: 2024-01-15
---

<h1>{title}</h1>
```

**Detecta:**
- `src/pages/blog/*.astro`
- `src/content/blog/*.md`
- Frontmatter + Astro components

---

## 📈 Scores y Métricas

### Severity Score (0-100)
```
0-20:   ✅ Excelente (minor issues)
21-40:  ⚠️  Bueno (some improvements needed)
41-60:  🟠 Regular (important fixes required)
61-80:  🔴 Malo (critical issues)
81-100: 💀 Terrible (needs immediate attention)

Cálculo:
- Critical issue: +25 puntos
- High issue: +15 puntos
- Medium issue: +8 puntos
- Low issue: +3 puntos
```

### Issue Distribution
```json
{
  "total_blogs": 50,
  "blogs_with_issues": 42,
  "distribution": {
    "critical_issues": 25,  // 60% de blogs
    "high_issues": 30,      // 60% de blogs
    "medium_issues": 20,    // 40% de blogs
    "low_issues": 5         // 10% de blogs
  }
}
```

---

## 🔧 Uso Avanzado

### Auditar Solo Blogs Específicos

```python
# Custom filter por fecha
POST /api/github/audit-blogs/{conn_id}/{repo_id}?since=2024-01-01

# Custom filter por autor
POST /api/github/audit-blogs/{conn_id}/{repo_id}?author=john-doe

# Custom filter por carpeta
POST /api/github/audit-blogs/{conn_id}/{repo_id}?path=content/tutorials
```

### Batch Fix Creation

```bash
# Aplicar fixes solo a blogs con severity > 60
POST /api/github/create-blog-fixes-pr/{conn_id}/{repo_id}
{
  "blog_paths": [...],  # De audit results
  "min_severity": 60,
  "fix_types": ["missing_meta_description", "no_schema"]
}
```

### Programar Auditorías Recurrentes

```python
# Celery task (agregar a tasks.py)
@celery_app.task
def audit_blogs_weekly(repo_id: str):
    """Audita blogs semanalmente"""
    # Ejecutar audit
    # Si hay issues nuevos, notificar
    # Si hay > 10 issues críticos, crear PR auto
```

---

## 💡 Best Practices

### 1. **Auditar Regularmente**
```
Frecuencia recomendada:
- Blogs activos: Semanal
- Blogs semi-activos: Mensual
- Blogs legacy: Trimestral
```

### 2. **Priorizar Fixes**
```
1º Critical (meta, title, H1)
2º High (schema, readability)
3º Medium (images, structure)
4º Low (freshness)
```

### 3. **Aplicar en Batches**
```
No aplicar 50 fixes de golpe:
- Batch 1: 10 blogs más importantes
- Batch 2: Siguiente 10
- Etc.
```

### 4. **Validar Resultados**
```
Después de mergear PR:
- Re-auditar en 1 semana
- Verificar mejoras reales
- Ajustar approach si es necesario
```

---

## 🐛 Troubleshooting

### "No blogs found"
```
Posibles causas:
1. Repo no tiene blogs
2. Estructura no estándar
3. Framework no soportado

Solución:
- Verificar rutas manualmente
- Agregar soporte custom en blog_auditor.py
```

### "Parsing errors"
```
Causa: Frontmatter mal formado

Solución:
- Validar YAML/TOML
- Asegurar --- delimiters
- Verificar encoding (UTF-8)
```

### "Too many files"
```
Límite actual: 50 blogs por llamada

Solución para más:
- Ejecutar en batches
- Usar filters (fecha, autor)
- Aumentar límite en código
```

---

## 📊 Ejemplo Completo

### Caso: Blog con 30 posts en Next.js

```bash
# 1. Auditar
POST /api/github/audit-blogs/conn-abc/repo-xyz

# Resultados:
{
  "total_blogs": 30,
  "blogs_with_issues": 28,
  "summary": {
    "missing_meta_description": 15,
    "no_schema": 30,  # Ninguno tiene schema!
    "poor_h1": 5
  }
}

# 2. Priorizar: Primero schema (afecta a todos)
POST /api/github/create-blog-fixes-pr/conn-abc/repo-xyz
{
  "blog_paths": [...all 30...],  # Todos
  "fix_types": ["no_schema"]     # Solo schema
}

# 3. PR creado:
"🟠 Add Article schema to 30 blog posts"

# 4. Mergear y esperar 1 semana

# 5. Re-auditar
POST /api/github/audit-blogs/conn-abc/repo-xyz

# Nuevos resultados:
{
  "total_blogs": 30,
  "blogs_with_issues": 15,  # ✅ Mejoró!
  "no_schema": 0             # ✅ Resuelto!
}

# 6. Siguiente batch: Meta descriptions
POST /api/github/create-blog-fixes-pr/conn-abc/repo-xyz
{
  "blog_paths": [...15 con issues...],
  "fix_types": ["missing_meta_description"]
}
```

---

## 🎯 Roadmap

### Fase Actual (Implementado) ✅
- Escaneo automático de blogs
- 8 tipos de issues
- Soporte para 5 frameworks
- PR creation con fixes

### Próxima Fase (1-2 semanas)
- [ ] Auditoría scheduled automática
- [ ] Webhooks: auditar en cada PR
- [ ] AI-generated fixes (LLM sugiere meta descriptions)
- [ ] Competitive analysis (vs otros blogs)

### Futuro (1-2 meses)
- [ ] Content quality score (más allá de SEO técnico)
- [ ] Readability analysis (Flesch, grade level)
- [ ] Keyword density analysis
- [ ] Internal linking suggestions
- [ ] Image optimization checks

---

## 📚 API Reference

### `POST /api/github/audit-blogs/{connection_id}/{repo_id}`

**Request:**
```
No body required
```

**Response:**
```json
{
  "status": "completed" | "no_blogs_found",
  "repo": "owner/name",
  "site_type": "nextjs" | "gatsby" | "hugo" | ...,
  "summary": {
    "total_blogs": 50,
    "blogs_with_issues": 42,
    "missing_meta_description": 20,
    // ... más contadores
  },
  "blogs": [
    {
      "file_path": "...",
      "title": "...",
      "url_slug": "...",
      "word_count": 2500,
      "published_date": "2024-01-15",
      "author": "...",
      "issues": [...],
      "issue_count": 3,
      "severity_score": 45
    }
  ],
  "audited_at": "2024-11-26T..."
}
```

### `POST /api/github/create-blog-fixes-pr/{connection_id}/{repo_id}`

**Request:**
```json
{
  "blog_paths": [
    "app/blog/post-1/page.tsx",
    "app/blog/post-2/page.tsx"
  ]
}
```

**Response:**
```json
{
  "status": "success" | "no_fixes_needed",
  "pr": {
    "id": "pr-123",
    "pr_number": 45,
    "html_url": "...",
    "title": "...",
    "files_changed": 2
  },
  "fixes_applied": 10,
  "blogs_fixed": 2
}
```

---

**🎉 Blog Auditor listo para usar! Audita 50 blogs en segundos.** 🚀
