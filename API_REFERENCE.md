# 📖 API Reference - GEO Audit Platform

## Base URL
```
http://localhost:8000
```

## Authentication
Actualmente sin autenticación. Adicionar JWT Bearer si es necesario.

---

## 1️⃣ AUDITORÍAS

### 1.1 Crear Nueva Auditoría
```http
POST /audits/
Content-Type: application/json

{
  "url": "https://ejemplo.com",
  "max_crawl": 50,
  "max_audit": 5
}
```

**Response (201):**
```json
{
  "id": 1,
  "url": "https://ejemplo.com",
  "domain": "ejemplo.com",
  "status": "pending",
  "progress": 0.0,
  "task_id": null,
  "created_at": "2024-01-15T10:30:00"
}
```

### 1.2 Listar Auditorías
```http
GET /audits/?page=1&page_size=20
```

**Response (200):**
```json
{
  "total": 42,
  "page": 1,
  "page_size": 20,
  "pages": 3,
  "data": [
    {
      "id": 1,
      "url": "https://ejemplo.com",
      "domain": "ejemplo.com",
      "status": "completed",
      "progress": 100.0,
      "total_pages": 5,
      "critical_issues": 2,
      "high_issues": 5,
      "medium_issues": 12,
      "low_issues": 8,
      "is_ymyl": false,
      "category": "E-commerce",
      "created_at": "2024-01-15T10:30:00",
      "completed_at": "2024-01-15T11:45:00"
    }
  ]
}
```

### 1.3 Obtener Detalle de Auditoría
```http
GET /audits/1
```

**Response (200):**
```json
{
  "id": 1,
  "url": "https://ejemplo.com",
  "domain": "ejemplo.com",
  "status": "completed",
  "progress": 100.0,
  "total_pages": 5,
  "critical_issues": 2,
  "high_issues": 5,
  "medium_issues": 12,
  "low_issues": 8,
  "is_ymyl": false,
  "category": "E-commerce",
  "created_at": "2024-01-15T10:30:00",
  "completed_at": "2024-01-15T11:45:00",
  "report_markdown": "# Reporte...",
  "fix_plan": [
    {
      "page_path": "/",
      "issue_code": "H1_MISSING",
      "priority": "CRITICAL",
      "description": "Falta H1 en página",
      "suggestion": "Agregar H1 con palabra clave principal"
    }
  ],
  "pages": [
    {
      "url": "https://ejemplo.com/",
      "path": "/",
      "overall_score": 7.5,
      "critical_issues": 1,
      "high_issues": 2,
      "medium_issues": 3,
      "low_issues": 2
    }
  ]
}
```

### 1.4 Filtrar por Estado
```http
GET /audits/status/completed
```

**Estados posibles:** `pending`, `running`, `completed`, `failed`

### 1.5 Obtener Estadísticas
```http
GET /audits/stats/summary
```

**Response (200):**
```json
{
  "total": 42,
  "pending": 5,
  "running": 2,
  "completed": 33,
  "failed": 2
}
```

### 1.6 Eliminar Auditoría
```http
DELETE /audits/1
```

**Response (204):** Sin contenido

---

## 2️⃣ REPORTES

### 2.1 Obtener Reportes de Auditoría
```http
GET /reports/audit/1
```

**Response (200):**
```json
{
  "audit_id": 1,
  "total_reports": 2,
  "reports": [
    {
      "id": 1,
      "audit_id": 1,
      "report_type": "markdown",
      "file_path": "/reports/ejemplo.com/report.md",
      "file_size": 15240,
      "created_at": "2024-01-15T11:45:00"
    },
    {
      "id": 2,
      "audit_id": 1,
      "report_type": "pdf",
      "file_path": "/reports/ejemplo.com/report.pdf",
      "file_size": 2048000,
      "created_at": "2024-01-15T11:50:00"
    }
  ]
}
```

### 2.2 Generar PDF (V11 Complete Context)
Genera un reporte PDF comprensivo que incluye:
- Análisis PageSpeed (Mobile/Desktop)
- Investigación de Keywords (Volumen, Dificultad)
- Perfil de Backlinks (DA, Anchor text)
- Rank Tracking & Visibilidad en LLMs
- Sugerencias de Contenido IA

```http
POST /audits/{audit_id}/generate-pdf?force_pagespeed_refresh=false
```

**Response (200):**
```json
{
  "success": true,
  "pdf_path": "/app/reports/ejemplo.com/Reporte_Consolidado_....pdf",
  "message": "PDF generated successfully with PageSpeed data",
  "pagespeed_included": true,
  "file_size": 125000
}
```

### 2.3 Obtener Markdown
```http
GET /reports/markdown/1
```

**Response (200):**
```json
{
  "audit_id": 1,
  "markdown": "# Informe de Auditoría...",
  "created_at": "2024-01-15T11:45:00"
}
```

### 2.4 Obtener JSON
```http
GET /reports/json/1
```

**Response (200):**
```json
{
  "audit_id": 1,
  "url": "https://ejemplo.com",
  "domain": "ejemplo.com",
  "status": "completed",
  "is_ymyl": false,
  "category": "E-commerce",
  "target_audit": {...},
  "external_intelligence": {...},
  "search_results": {...},
  "fix_plan": [...],
  "created_at": "2024-01-15T10:30:00",
  "completed_at": "2024-01-15T11:45:00"
}
```

### 2.5 Descargar Reporte
```http
GET /reports/download/1
```

**Response (200):** Descarga archivo binario

---

## 3️⃣ ANALYTICS

### 3.1 Análisis de Auditoría
```http
GET /analytics/audit/1
```

**Response (200):**
```json
{
  "audit_id": 1,
  "domain": "ejemplo.com",
  "total_pages": 5,
  "is_ymyl": false,
  "category": "E-commerce",
  "issues": {
    "critical": 2,
    "high": 5,
    "medium": 12,
    "low": 8,
    "total": 27
  },
  "scores": {
    "h1_score": 8.5,
    "structure_score": 7.2,
    "content_score": 6.8,
    "eeat_score": 7.0,
    "schema_score": 5.5,
    "overall_score": 7.0
  },
  "pages": [
    {
      "url": "https://ejemplo.com/",
      "path": "/",
      "overall_score": 7.5,
      "issues": {
        "critical": 1,
        "high": 2,
        "medium": 3,
        "low": 2
      }
    }
  ]
}
```

### 3.2 Análisis Competitivo
```http
GET /analytics/competitors/1
```

**Response (200):**
```json
{
  "audit_id": 1,
  "total_competitors": 3,
  "your_geo_score": 7.5,
  "average_competitor_score": 8.2,
  "position": "Por debajo del promedio",
  "competitors": [
    {
      "domain": "competidor1.com",
      "url": "https://competidor1.com",
      "geo_score": 8.9
    },
    {
      "domain": "competidor2.com",
      "url": "https://competidor2.com",
      "geo_score": 8.1
    }
  ],
  "identified_gaps": [
    "Schema faltante: FAQPage",
    "Schema faltante: Article"
  ]
}
```

### 3.3 Dashboard
```http
GET /analytics/dashboard
```

**Response (200):**
```json
{
  "summary": {
    "total_audits": 42,
    "completed_audits": 33,
    "running_audits": 2,
    "failed_audits": 2,
    "success_rate": 78.57
  },
  "recent_audits": [
    {
      "id": 1,
      "url": "https://ejemplo.com",
      "domain": "ejemplo.com",
      "status": "completed",
      "progress": 100.0,
      "total_pages": 5,
      "issues": {
        "critical": 2,
        "high": 5,
        "medium": 12,
        "low": 8
      },
      "created_at": "2024-01-15T10:30:00"
    }
  ],
  "metrics": {
    "unique_domains": 15,
    "total_issues": 847,
    "average_issues_per_audit": 20.17
  }
}
```

### 3.4 Issues por Prioridad
```http
GET /analytics/issues/1
```

**Response (200):**
```json
{
  "audit_id": 1,
  "total_issues": 27,
  "by_priority": {
    "CRITICAL": [
      {
        "page_path": "/",
        "issue_code": "H1_MISSING",
        "description": "Falta H1",
        "suggestion": "Agregar H1"
      }
    ],
    "HIGH": [
      {
        "page_path": "/product",
        "issue_code": "HEADER_HIERARCHY",
        "description": "Jerarquía de headers incorrecta",
        "suggestion": "Usar H2 después de H1"
      }
    ],
    "MEDIUM": [...],
    "LOW": [...]
  }
}
```

---

## 4️⃣ HEALTH & INFO

### 4.1 Health Check
```http
GET /health
```

**Response (200):**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "database": "ok",
  "redis": "ok",
  "api_name": "GEO Audit Platform"
}
```

### 4.2 Configuración Pública
```http
GET /config
```

**Response (200):**
```json
{
  "app_name": "GEO Audit Platform",
  "app_version": "1.0.0",
  "debug": false,
  "max_crawl_default": 50,
  "max_audit_default": 5,
  "default_page_size": 20,
  "max_page_size": 100
}
```

### 4.3 Información API
```http
GET /info
```

**Response (200):**
```json
{
  "title": "GEO Audit Platform",
  "version": "1.0.0",
  "description": "API profesional para auditorías SEO/GEO con arquitectura modular",
  "documentation": "/docs",
  "endpoints": {
    "audits": "/audits",
    "reports": "/reports",
    "analytics": "/analytics",
    "crawler": "/crawler"
  }
}
```

---

## 🔍 HTTP Status Codes

| Código | Significado |
|--------|------------|
| 200 | OK - Solicitud exitosa |
| 201 | Created - Recurso creado |
| 202 | Accepted - Solicitud aceptada (asincrónica) |
| 204 | No Content - Eliminado exitosamente |
| 400 | Bad Request - Parámetros inválidos |
| 404 | Not Found - Recurso no encontrado |
| 500 | Internal Server Error - Error del servidor |
| 503 | Service Unavailable - Servicio no disponible |

---

## 📋 Esquemas de Datos

### Audit Status
```
pending   - Esperando procesamiento
running   - En ejecución
completed - Completada
failed    - Falló
```

### Issue Priority
```
CRITICAL - Acción inmediata
HIGH     - Impacto alto
MEDIUM   - Optimización
LOW      - Mejora menor
```

---

## 🔐 Notas de Seguridad

- ⚠️ Actualmente sin autenticación
- ⚠️ CORS configurado para desarrollo
- ⚠️ Cambiar SECRET_KEY en producción
- ✅ Se recomienda usar HTTPS en producción
- ✅ Implementar JWT Bearer token
- ✅ Rate limiting en endpoints críticos

---

## 📞 Soporte

Para issues o preguntas: [support@geoaudit.local](mailto:support@geoaudit.local)
