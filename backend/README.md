# FastAPI Backend Entry Point

## Installation

```bash
cd backend
pip install -r requirements.txt
```

## Configuration

Copy `.env.example` to `.env` and update with your API keys:

```bash
cp .env.example .env
```

## Running the Server

### Development Mode (with auto-reload)
```bash
python main.py
```

Or with uvicorn directly:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Production Mode
```bash
DEBUG=False python main.py
```

Or with gunicorn:
```bash
gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:8000
```

## API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI JSON: http://localhost:8000/openapi.json

## Project Structure

```
backend/
├── app/
│   ├── api/
│   │   └── routes/
│   │       ├── audits.py         # Endpoints de auditorías
│   │       ├── reports.py        # Endpoints de reportes
│   │       ├── analytics.py      # Endpoints de análisis
│   │       └── health.py         # Health checks
│   ├── core/
│   │   ├── config.py             # Configuración global
│   │   ├── database.py           # Conexión a BD
│   │   └── logger.py             # Sistema de logs
│   ├── models/
│   │   └── __init__.py           # Modelos SQLAlchemy
│   ├── schemas/
│   │   └── __init__.py           # Esquemas Pydantic
│   ├── services/
│   │   └── audit_service.py      # Lógica de negocio
│   └── main.py                   # Aplicación FastAPI
├── main.py                        # Entry point
├── requirements.txt               # Dependencias
└── .env.example                   # Configuración de ejemplo
```

## API Endpoints

### Auditorías
- `POST /audits/` - Crear nueva auditoría
- `GET /audits/` - Listar auditorías
- `GET /audits/{audit_id}` - Obtener auditoría
- `DELETE /audits/{audit_id}` - Eliminar auditoría
- `GET /audits/status/{status_filter}` - Filtrar por estado

### Reportes
- `GET /reports/audit/{audit_id}` - Obtener reportes
- `POST /reports/generate-pdf` - Generar PDF
- `GET /reports/markdown/{audit_id}` - Obtener Markdown
- `GET /reports/json/{audit_id}` - Obtener JSON

### Analytics
- `GET /analytics/audit/{audit_id}` - Analytics de auditoría
- `GET /analytics/competitors/{audit_id}` - Análisis competitivo
- `GET /analytics/dashboard` - Datos del dashboard
- `GET /analytics/issues/{audit_id}` - Issues por prioridad

### Health
- `GET /health` - Health check
- `GET /config` - Configuración pública
- `GET /info` - Información de la API

## Database Migrations (Optional)

Setup Alembic for database migrations:

```bash
alembic init migrations
alembic revision --autogenerate -m "Initial migration"
alembic upgrade head
```

## Celery Integration (Optional)

For async task processing:

```bash
# Terminal 1: Celery worker
celery -A app.workers.tasks worker --loglevel=info

# Terminal 2: Celery beat (for scheduled tasks)
celery -A app.workers.tasks beat --loglevel=info
```

## Testing

```bash
cd backend
pytest -q tests/
pytest -q tests/ -v --cov=app
```

### Docker (recommended)

Inside the backend container, the project root is `/app`, so tests must use `tests/...` paths:

```bash
docker compose up -d db redis backend worker
docker compose exec backend pytest -q tests/test_competitor_queries.py tests/test_pdf_fast_mode.py
```

### Live manual tests (opt-in)

These tests are disabled by default and only run when explicitly enabled:

```bash
docker compose exec backend sh -lc 'RUN_INTEGRATION_TESTS=1 RUN_LIVE_E2E=1 LIVE_TARGET_URL=https://plataforma5.la/ pytest -q tests/test_live_plataforma5_agent1_pdf.py -s'
```
