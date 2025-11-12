# 🎯 PRÓXIMOS PASOS - Guía de Implementación

## 1️⃣ Integración del Código Existente

Tu código anterior (`ag2_pipeline.py`, `crawler.py`, etc.) debe integrarse como **servicios en la carpeta `backend/app/workers/`**

### Paso A: Migrar Módulos Existentes

```bash
# Copiar funciones core a servicios
backend/app/services/
├── audit_service.py       ✅ Creado
├── crawler_service.py     # TODO: Crear
├── pipeline_service.py    # TODO: Crear
├── pdf_service.py         # TODO: Crear
└── llm_service.py         # TODO: Crear
```

### Paso B: Crear Crawler Service

Archivo: `backend/app/services/crawler_service.py`

```python
from ..core.logger import get_logger
# Importar funciones de crawler.py original

class CrawlerService:
    @staticmethod
    def crawl_site(url: str, max_pages: int = 50) -> List[str]:
        # Reutilizar código de crawler.py
        pass
```

### Paso C: Crear Pipeline Service

Archivo: `backend/app/services/pipeline_service.py`

```python
class PipelineService:
    @staticmethod
    async def run_full_audit(audit_id: int, db: Session):
        # Integrar ag2_pipeline.py
        # Llamar a Agente 1 y Agente 2
        pass
```

---

## 2️⃣ Crear Tareas Celery (Asincrónicas)

Archivo: `backend/app/workers/tasks.py`

```python
from celery import Celery, shared_task
from ..core.config import settings

celery_app = Celery(
    'auditor',
    broker=settings.CELERY_BROKER,
    backend=settings.CELERY_BACKEND
)

@shared_task
def run_audit_task(audit_id: int):
    """Ejecutar auditoría en background"""
    # Llamar PipelineService
    pass

@shared_task
def generate_pdf_task(audit_id: int):
    """Generar PDF en background"""
    pass
```

Luego actualizar los routers:

```python
# En backend/app/api/routes/audits.py
from ...workers.tasks import run_audit_task

@router.post("/")
async def create_audit(audit_create: AuditCreate, db: Session = Depends(get_db)):
    audit = AuditService.create_audit(db, audit_create)
    
    # Ejecutar en background
    task = run_audit_task.delay(audit.id)
    audit.task_id = task.id
    db.commit()
    
    return AuditResponse.from_orm(audit)
```

---

## 3️⃣ Mejorar el Dashboard

Archivo: `frontend/dashboard.html` - Agregar secciones:

```javascript
// Agregar al App Component
{activeSection === 'reports' && <ReportsSection />}
{activeSection === 'analytics' && <AnalyticsSection />}
{activeSection === 'competitors' && <CompetitorsSection />}
```

Crear componentes React separados para:
- Visualización de reportes
- Gráficos de analytics
- Tabla comparativa de competidores
- Descarga de archivos

---

## 4️⃣ Implementar Autenticación

Archivo: `backend/app/core/security.py`

```python
from jose import JWTError, jwt
from datetime import datetime, timedelta
from fastapi.security import HTTPBearer, HTTPAuthCredentials

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthCredentials = Depends(security)
):
    try:
        token = credentials.credentials
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: int = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401)
    return user_id
```

Usar en routers:

```python
@router.get("/audits/")
async def list_audits(
    current_user: int = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Filtrar auditorías del usuario
    pass
```

---

## 5️⃣ Crear Tests

Archivo: `backend/tests/test_audits.py`

```python
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_create_audit():
    response = client.post(
        "/audits/",
        json={"url": "https://test.com"}
    )
    assert response.status_code == 201
    assert response.json()["domain"] == "test.com"

def test_list_audits():
    response = client.get("/audits/")
    assert response.status_code == 200
    assert "data" in response.json()
```

Ejecutar:
```bash
cd backend
pytest tests/ -v --cov=app
```

---

## 6️⃣ Configurar CI/CD (GitHub Actions)

Archivo: `.github/workflows/test.yml`

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_PASSWORD: postgres
    
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      
      - run: pip install -r backend/requirements.txt
      - run: cd backend && pytest tests/
```

---

## 7️⃣ Agregar Monitoreo (Prometheus + Grafana)

Archivo: `backend/app/core/metrics.py`

```python
from prometheus_client import Counter, Histogram

audit_counter = Counter('audits_total', 'Total audits')
audit_duration = Histogram('audit_duration_seconds', 'Audit duration')
api_requests = Counter('api_requests_total', 'API requests')
```

Actualizar `docker-compose.yml`:

```yaml
prometheus:
  image: prom/prometheus
  volumes:
    - ./prometheus.yml:/etc/prometheus/prometheus.yml

grafana:
  image: grafana/grafana
  ports:
    - "3001:3000"
```

---

## 8️⃣ Documentación Swagger Mejorada

Actualizar `backend/app/main.py`:

```python
# Agregar tags_metadata
tags_metadata = [
    {
        "name": "audits",
        "description": "Operaciones de auditorías",
        "externalDocs": {
            "description": "Documentación completa",
            "url": "https://docs.geoaudit.local/audits",
        },
    },
]

app = FastAPI(
    openapi_tags=tags_metadata,
    ...
)
```

---

## 9️⃣ Integración de Notificaciones (Email, Slack)

Archivo: `backend/app/services/notification_service.py`

```python
import smtplib
from email.mime.text import MIMEText

class NotificationService:
    @staticmethod
    def send_audit_complete_email(audit_id: int, email: str):
        # Enviar email cuando auditoría complete
        pass
    
    @staticmethod
    def send_slack_notification(message: str):
        # Enviar notificación a Slack
        pass
```

---

## 🔟 Deployment en Producción

### Opción A: Heroku

```bash
# Crear Procfile
web: gunicorn -w 4 app.main:app
worker: celery -A app.workers.tasks worker

# Deploy
git push heroku main
```

### Opción B: AWS ECS

```bash
aws ecr get-login-password | docker login --username AWS --password-stdin $ECR_URL
docker build -t auditor-backend .
docker tag auditor-backend:latest $ECR_URL/auditor-backend:latest
docker push $ECR_URL/auditor-backend:latest
```

### Opción C: DigitalOcean App Platform

```bash
# Conectar GitHub repo y deploy automático
```

---

## ✅ Checklist de Implementación

- [ ] **Semana 1**: Integrar código existente en servicios
- [ ] **Semana 2**: Implementar Celery workers
- [ ] **Semana 3**: Mejorar dashboard (reportes, analytics)
- [ ] **Semana 4**: Autenticación JWT
- [ ] **Semana 5**: Tests unitarios e integración
- [ ] **Semana 6**: CI/CD GitHub Actions
- [ ] **Semana 7**: Monitoreo Prometheus/Grafana
- [ ] **Semana 8**: Deploy a producción

---

## 📚 Recursos Útiles

### Documentación
- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [SQLAlchemy Docs](https://docs.sqlalchemy.org/)
- [Celery Docs](https://docs.celeryproject.io/)
- [React Docs](https://react.dev/)

### Tutoriales
- [FastAPI Full Stack](https://github.com/tiangolo/full-stack-fastapi-postgresql)
- [Real Python FastAPI](https://realpython.com/fastapi-python-web-apis/)
- [Miguel Grinberg Flask Mega-Tutorial](https://blog.miguelgrinberg.com/post/the-flask-mega-tutorial-part-i-hello-world)

### Herramientas
- [Postman](https://www.postman.com/) - API testing
- [Insomnia](https://insomnia.rest/) - API client
- [DBeaver](https://dbeaver.io/) - Database IDE
- [Redis Insights](https://redis.com/redis-enterprise/redis-insight/) - Redis GUI

---

## 🎓 Best Practices a Implementar

```python
# 1. Type Hints Completos
from typing import List, Optional, Dict, Any

@router.get("/audits/", response_model=List[AuditSummary])
async def list_audits() -> List[AuditSummary]:
    pass

# 2. Docstrings Detallados
def create_audit(url: str) -> Audit:
    """
    Crear nueva auditoría.
    
    Args:
        url: URL del sitio a auditar
    
    Returns:
        Audit creada con ID
    
    Raises:
        ValueError: Si URL es inválida
    """
    pass

# 3. Logging en Todos Lados
logger.info(f"Auditoría {audit_id} completada")
logger.warning(f"Issue encontrado en {page_url}")
logger.error(f"Error crítico: {exception}")

# 4. Validación de Entrada
class AuditCreate(BaseModel):
    url: HttpUrl
    max_crawl: int = Field(50, ge=1, le=500)
    max_audit: int = Field(5, ge=1, le=50)

# 5. Exception Handling
try:
    result = risky_operation()
except SpecificException as e:
    logger.exception(f"Error: {e}")
    raise HTTPException(status_code=400, detail=str(e))
```

---

## 🚀 Próximo Milestone

**Objetivo**: Sistema completo listo para producción con:
- ✅ API REST estable
- ✅ Dashboard funcional
- ✅ Tests automatizados
- ✅ CI/CD pipeline
- ✅ Monitoreo activo
- ✅ Documentación OpenAPI
- ✅ Deployed en servidor

---

**¿Necesitas ayuda con algún paso específico? Pregunta en cualquier momento.** 💬

*Última actualización: 2024*
