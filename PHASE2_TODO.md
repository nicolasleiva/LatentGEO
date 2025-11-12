# 🚀 FASE 2: CREAR PIPELINE SERVICE

**Objetivo:** Integrar la lógica del `ag2_pipeline.py` en un servicio modular reutilizable.

**Tiempo Estimado:** 1-2 horas

---

## 📋 QUÉ LEER PRIMERO

1. Leer `ag2_pipeline.py` (lineas 1-100) para entender flujo general
2. Leer `ag2_pipeline.py` (lineas 300-500) para ver prompts de agentes
3. Leer `ag2_pipeline.py` (lineas 600-920) para ver procesamiento de resultados

---

## 🎯 PLAN DE IMPLEMENTACIÓN

### Paso 1: Analizar `ag2_pipeline.py`

Identificar:
- Agente 1: Análisis de competencia
- Agente 2: Plan de correcciones  
- Funciones principales
- Manejo de APIs (Gemini, OpenAI)

### Paso 2: Crear `backend/app/services/pipeline_service.py`

Estructura:

```python
class PipelineService:
    
    @staticmethod
    async def get_competitor_intelligence(url: str) -> Dict[str, Any]:
        """Agente 1: Análisis de competencia"""
        # Usa CrawlerService para encontrar competidores
        # Usa AuditLocalService para auditar cada uno
        # Retorna análisis consolidado
    
    @staticmethod
    async def generate_fix_plan(audit_data: Dict) -> List[Dict[str, Any]]:
        """Agente 2: Plan de correcciones"""
        # Procesa resultados de auditoría
        # Genera plan de correcciones priorizado
        # Retorna lista de issues con prioridad
    
    @staticmethod
    async def run_complete_audit(url: str, config: Dict) -> Dict[str, Any]:
        """Orquesta todo el pipeline"""
        # Rastrear sitio (CrawlerService)
        # Auditar páginas (AuditLocalService)
        # Análisis de competencia (Agente 1)
        # Generar plan (Agente 2)
        # Retorna resultado consolidado
```

### Paso 3: Crear endpoint POST /audits/

```python
@router.post("/", response_model=AuditResponse, status_code=201)
async def create_audit(audit_create: AuditCreate, db: Session = Depends(get_db)):
    """Crear auditoría usando todos los servicios"""
    
    audit = AuditService.create_audit(db, audit_create)
    
    # NUEVA LÓGICA: Usar PipelineService
    result = await PipelineService.run_complete_audit(
        url=str(audit_create.url),
        config={
            "max_crawl": audit_create.max_crawl,
            "max_audit": audit_create.max_audit
        }
    )
    
    # Guardar resultados
    AuditService.set_audit_results(db, audit.id, result)
    
    return AuditResponse.from_orm(audit)
```

---

## 🔧 TAREAS CONCRETAS

### ✋ TAREA PARA TI

**Ahora ejecuta este comando:**

```bash
# Lee las primeras 200 líneas del pipeline
Get the main structure of ag2_pipeline.py
```

**Luego dime:**

1. ¿Cuál es el nombre del Agente 1?
2. ¿Cuál es el nombre del Agente 2?
3. ¿Qué APIs externos usa? (Gemini, OpenAI, etc)
4. ¿Cuál es la estructura del output final?
5. ¿Hay alguna función intermedia importante?

---

## 📊 REFERENCIAS

### Servicios ya creados (usa estos):

```python
# Rastrear sitio
from backend.app.services.crawler_service import CrawlerService
urls = await CrawlerService.crawl_site(url)

# Auditar página
from backend.app.services.audit_local_service import AuditLocalService
summary = await AuditLocalService.run_local_audit(url)
```

### Base de datos (usa este):

```python
from backend.app.models import Audit, AuditedPage, Report
from backend.app.services.audit_service import AuditService
```

### Configuración (acceso a APIs):

```python
from backend.app.core.config import settings
# settings.GEMINI_API_KEY
# settings.OPENAI_API_KEY
# settings.GOOGLE_API_KEY
```

---

## 📝 CHECKLIST

Cuando crees PipelineService:

- [ ] Clase con métodos estáticos
- [ ] Docstrings en todas las funciones
- [ ] Type hints 100%
- [ ] Logging de operaciones clave
- [ ] Manejo de errores (try/except)
- [ ] Usar servicios existentes (Crawler, AuditLocal)
- [ ] Compatible con Celery (métodos async)
- [ ] ~300-400 líneas de código

---

## 🎯 SIGUIENTE COMANDO

Cuando estés listo, ejecuta:

```
Crear backend/app/services/pipeline_service.py integrando ag2_pipeline.py
```

---

*Status: Esperando tu análisis del ag2_pipeline.py para continuar.*
