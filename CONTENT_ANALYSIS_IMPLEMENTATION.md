# Implementación: Análisis de Contenido Avanzado

## ✅ Completado

### 1. Contenido Duplicado (1 semana)

**Backend:**
- `backend/app/services/duplicate_content_service.py`
  - **difflib**: Similitud de secuencias (0-1)
  - **TF-IDF**: Vectorización y cosine similarity con scikit-learn
  - Comparación interna (entre páginas del sitio)
  - Comparación externa (con competidores)
  - Threshold configurable (default 0.85 interno, 0.75 externo)

**Características:**
- Extracción de texto limpio (sin scripts, nav, footer)
- Normalización de espacios
- Matriz de similitud para múltiples páginas
- Detección de duplicados parciales

### 2. Heatmaps de Issues (1 semana)

**Frontend:**
- `frontend/components/issues-heatmap.tsx`
  - **Canvas API**: Renderizado de alta performance
  - Visualización por severidad (Critical, High, Medium, Low)
  - Intensidad de color basada en frecuencia
  - Escala automática según máximo valor
  - Responsive design

**Colores:**
- Critical: Rojo (#ef4444)
- High: Naranja (#f97316)
- Medium: Amarillo (#eab308)
- Low: Azul (#3b82f6)

### 3. Análisis de Gap de Keywords (1 semana)

**Backend:**
- `backend/app/services/keyword_gap_service.py`
  - Extracción de keywords con pesos (títulos x3, headings x2)
  - Filtrado de stop words
  - Análisis de frecuencias
  - Comparación con competidores
  - Identificación de oportunidades
  - **Integración con Gemini** para recomendaciones estratégicas

**Frontend:**
- `frontend/components/keyword-gap-chart.tsx`
  - BarChart de distribución (Missing, Common, Unique)
  - Gap Score visual
  - Lista de top oportunidades con frecuencias
  - Badges para destacar métricas

**Métricas:**
- Missing Keywords: Keywords que tienen competidores pero tú no
- Unique Keywords: Keywords que tienes pero competidores no
- Common Keywords: Keywords compartidas
- Gap Score: Porcentaje de keywords faltantes
- Opportunities: Top keywords de competidores ordenadas por frecuencia

### 4. API Endpoints

**Content Analysis:**
- `POST /api/content/duplicates` - Detecta contenido duplicado
- `POST /api/content/keywords/extract` - Extrae keywords de HTML
- `POST /api/content/keywords/gap` - Analiza gap entre dos sets
- `GET /api/content/keywords/compare` - Compara dos URLs completas

### 5. Interfaz Unificada

**Página:**
- `frontend/app/content-analysis/page.tsx`
  - Tabs para diferentes análisis
  - Keyword Gap con comparación de URLs
  - Issues Heatmap con datos en tiempo real
  - Duplicate Content (preparado para expansión)

## 🚀 Uso

### Instalación de Dependencias

```bash
cd backend
pip install scikit-learn numpy
```

### Análisis de Keywords

```bash
# Comparar dos URLs
GET http://localhost:8000/api/content/keywords/compare?your_url=https://example.com&competitor_url=https://competitor.com

# Extraer keywords de HTML
POST http://localhost:8000/api/content/keywords/extract
{
  "html": "<html>...</html>",
  "top_n": 50
}
```

### Detección de Duplicados

```bash
POST http://localhost:8000/api/content/duplicates
{
  "pages": [
    {"url": "https://example.com/page1", "html": "..."},
    {"url": "https://example.com/page2", "html": "..."}
  ],
  "threshold": 0.85
}
```

### Frontend

Navegar a: `http://localhost:3000/content-analysis`

## 📊 Algoritmos Utilizados

### TF-IDF (Term Frequency-Inverse Document Frequency)
- Vectorización de texto
- Peso de términos según frecuencia e importancia
- Cosine similarity para comparación
- Ideal para documentos largos

### difflib (SequenceMatcher)
- Similitud de secuencias
- Algoritmo de Ratcliff/Obershelp
- Rápido para comparaciones 1:1
- Ideal para textos cortos

### Keyword Extraction
- Tokenización con regex
- Stop words filtering
- Weighted frequency (títulos, headings)
- Counter para ranking

## 🎯 Casos de Uso

### 1. Contenido Duplicado
- Detectar páginas con contenido similar
- Identificar canibalización de keywords
- Encontrar plagio externo
- Optimizar arquitectura de información

### 2. Keyword Gap
- Descubrir oportunidades de contenido
- Analizar estrategia de competidores
- Priorizar keywords faltantes
- Optimizar contenido existente

### 3. Issues Heatmap
- Visualizar distribución de problemas
- Identificar páginas críticas
- Priorizar correcciones
- Monitorear mejoras

## 🔧 Configuración

### Thresholds Recomendados

**Contenido Duplicado:**
- Interno: 0.85 (85% similitud)
- Externo: 0.75 (75% similitud)

**Keywords:**
- Top N: 50 (ajustable 1-200)
- Stop words: Inglés (expandible)

### Integración con Gemini

```python
from app.services.keyword_gap_service import KeywordGapService

gap_data = KeywordGapService.analyze_gap(your_kw, comp_kw)
recommendations = await KeywordGapService.analyze_with_gemini(gap_data, llm_function)
```

## 📈 Performance

- TF-IDF: O(n*m) donde n=docs, m=términos
- difflib: O(n*m) donde n,m=longitud textos
- Canvas rendering: 60fps para <100 items
- Keyword extraction: <1s por página

## 🔮 Próximas Mejoras

- [ ] Soporte multiidioma (stop words)
- [ ] Clustering de contenido similar
- [ ] Análisis de entidades (NER)
- [ ] Exportación de reportes
- [ ] Integración con Google Search Console
- [ ] Análisis de tendencias temporales
