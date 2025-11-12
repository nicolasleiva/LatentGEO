# 🚀 GEO Audit Platform - Guía de Instalación y Uso

## 📋 Requisitos Previos

- Python 3.11+
- Node.js 18+ (opcional, para frontend standalone)
- Docker & Docker Compose (para deployment)
- PostgreSQL 16 (o SQLite para desarrollo)
- Redis 7 (para caché y colas de tareas)

## 🏗️ Estructura del Proyecto

```
auditor/
├── backend/                    # FastAPI Backend
│   ├── app/
│   │   ├── api/
│   │   │   └── routes/        # Endpoints modulares
│   │   ├── core/              # Configuración y BD
│   │   ├── models/            # Modelos SQLAlchemy
│   │   ├── schemas/           # Esquemas Pydantic
│   │   ├── services/          # Lógica de negocio
│   │   └── main.py            # Aplicación FastAPI
│   ├── requirements.txt
│   ├── main.py                # Entry point
│   └── README.md
├── frontend/                   # Dashboard HTML/React
│   └── dashboard.html
├── docker-compose.yml         # Stack completo
└── README.md
```

## 🛠️ Instalación Local

### 1️⃣ Clonar/Descargar el Proyecto

```bash
cd c:\Users\Dell\Documents\auditor
```

### 2️⃣ Crear Archivo .env

```bash
cd backend
cp .env.example .env
```

Editar `.env` con tus API keys:
```env
GEMINI_API_KEY=sk-...
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=...
CSE_ID=...
DATABASE_URL=sqlite:///./auditor.db
```

### 3️⃣ Instalar Dependencias Backend

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate

pip install -r requirements.txt
```

### 4️⃣ Iniciar el Backend

```bash
python main.py
```

Debería ver:
```
✅ GEO Audit Platform v1.0.0 iniciado
📚 Documentación: http://localhost:8000/docs
```

### 5️⃣ Acceder al Dashboard

- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Frontend Dashboard**: Abrir `frontend/dashboard.html` en el navegador

## 🐳 Instalación con Docker

### Opción 1: Docker Compose (Recomendado)

```bash
# En la raíz del proyecto
docker-compose up --build

# En background
docker-compose up -d --build
```

Esto levantará:
- Backend FastAPI (puerto 8000)
- Frontend (puerto 3000)
- PostgreSQL (puerto 5432)
- Redis (puerto 6379)
- Celery Worker (para tareas asincrónicas)

### Opción 2: Contenedores Individuales

```bash
# Backend
docker build -f Dockerfile.backend -t auditor-backend .
docker run -p 8000:8000 auditor-backend

# Frontend
docker build -f Dockerfile.frontend -t auditor-frontend .
docker run -p 3000:3000 auditor-frontend
```

## 📡 API Endpoints

### Auditorías
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/audits/` | Crear nueva auditoría |
| GET | `/audits/` | Listar auditorías |
| GET | `/audits/{id}` | Obtener detalle |
| DELETE | `/audits/{id}` | Eliminar auditoría |
| GET | `/audits/status/{status}` | Filtrar por estado |
| GET | `/audits/stats/summary` | Estadísticas |

### Reportes
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/reports/audit/{id}` | Obtener reportes |
| POST | `/reports/generate-pdf` | Generar PDF |
| GET | `/reports/markdown/{id}` | Descargar Markdown |
| GET | `/reports/json/{id}` | Descargar JSON |

### Analytics
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/analytics/audit/{id}` | Analytics de auditoría |
| GET | `/analytics/competitors/{id}` | Análisis competitivo |
| GET | `/analytics/dashboard` | Datos del dashboard |
| GET | `/analytics/issues/{id}` | Issues por prioridad |

### Health
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/config` | Configuración pública |
| GET | `/info` | Información API |

## 💡 Ejemplos de Uso

### Crear una Auditoría

```bash
curl -X POST "http://localhost:8000/audits/" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://ejemplo.com",
    "max_crawl": 50,
    "max_audit": 5
  }'
```

Response:
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

### Listar Auditorías

```bash
curl "http://localhost:8000/audits/?page=1&page_size=20"
```

### Obtener Dashboard

```bash
curl "http://localhost:8000/analytics/dashboard"
```

### Generar PDF

```bash
curl -X POST "http://localhost:8000/reports/generate-pdf" \
  -H "Content-Type: application/json" \
  -d '{
    "audit_id": 1,
    "include_competitor_analysis": true
  }'
```

## 🎨 Dashboard Features

- ✅ Crear auditorías
- ✅ Visualizar estado en tiempo real
- ✅ Gráficos de progreso
- ✅ Estadísticas de issues
- ✅ Análisis competitivo
- ✅ Descargar reportes
- ✅ Configuración

## 🔧 Configuración Avanzada

### PostgreSQL en lugar de SQLite

```env
DATABASE_URL=postgresql+psycopg2://user:password@localhost:5432/auditor_db
```

### Redis para Caché

```env
REDIS_URL=redis://localhost:6379/0
```

### Celery para Tareas Asincrónicas

```env
CELERY_BROKER=redis://localhost:6379/0
CELERY_BACKEND=redis://localhost:6379/1
```

## 🧪 Testing

```bash
cd backend
pytest tests/
pytest tests/ -v --cov=app
```

## 🚀 Deployment en Producción

### Usando Gunicorn + Nginx

```bash
# Backend
gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:8000

# O con Uvicorn directamente
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Usando Docker Swarm

```bash
docker swarm init
docker stack deploy -c docker-compose.yml auditor
```

### Usando Kubernetes

Crear manifiestos en `k8s/`:
- `deployment.yaml`
- `service.yaml`
- `configmap.yaml`

## 📊 Monitoreo

### Logs

```bash
# Docker
docker-compose logs -f backend

# Local
tail -f logs/app.log
```

### Métricas

Endpoint `/health` proporciona:
- Estado de base de datos
- Estado de Redis
- Versión de aplicación

## 🐛 Troubleshooting

### Error: "API Key no configurada"

```bash
# Verificar .env existe
ls -la backend/.env

# Verificar variables
grep GEMINI_API_KEY backend/.env
```

### Error: "Database connection failed"

```bash
# Verificar PostgreSQL está corriendo
docker ps | grep postgres

# O en Docker Compose
docker-compose ps
```

### Error: "Port already in use"

```bash
# Cambiar puerto en .env
PORT=8001

# O liberar puerto
# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Linux/Mac
lsof -i :8000
kill -9 <PID>
```

## 📚 Documentación Adicional

- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [SQLAlchemy Docs](https://docs.sqlalchemy.org/)
- [Pydantic Docs](https://docs.pydantic.dev/)
- [Celery Docs](https://docs.celeryproject.io/)

## 🤝 Contribución

1. Fork el proyecto
2. Crear rama de feature (`git checkout -b feature/AmazingFeature`)
3. Commit cambios (`git commit -m 'Add AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abrir Pull Request

## 📝 Licencia

Este proyecto está bajo licencia MIT.

## ✉️ Contacto

Para preguntas o soporte: support@geoaudit.local

---

**¡Happy Auditing! 🎉**
