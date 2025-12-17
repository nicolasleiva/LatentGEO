# Configuración para Cualquier Proyecto

Este sistema ha sido modificado para funcionar con **cualquier proyecto** que ingrese el usuario. Ya no está hardcodeado para "auditor_geo".

## 🚀 Inicio Rápido

### 1. Configurar Variables de Entorno

Copia el archivo `.env.template` a `.env` y personaliza los valores:

```bash
cp .env.template .env
```

### 2. Personalizar tu Proyecto

Edita el archivo `.env` y configura:

```env
# Nombre de tu proyecto (aparecerá en la UI)
PROJECT_NAME=Mi Proyecto Increíble

# Slug del proyecto (usado para rutas y archivos)
PROJECT_SLUG=mi_proyecto

# Base de datos (ajusta según tu necesidad)
DATABASE_URL=postgresql+psycopg2://usuario:password@db:5432/mi_db
```

### 3. Configurar APIs (Opcional)

Según las funcionalidades que necesites:

#### APIs Básicas (Recomendadas)
```env
GOOGLE_API_KEY=tu_clave
GOOGLE_PAGESPEED_API_KEY=tu_clave
```

#### APIs de IA (Para análisis avanzado)
```env
NVIDIA_API_KEY=tu_clave
GEMINI_API_KEY=tu_clave
```

#### Integraciones (Opcional)
```env
GITHUB_CLIENT_ID=tu_id
GITHUB_CLIENT_SECRET=tu_secret
```

## 📁 Estructura Genérica

El sistema ahora usa configuración dinámica:

```
tu_proyecto/
├── .env                    # Tu configuración personalizada
├── .env.template          # Plantilla de ejemplo
├── backend/
│   ├── app/
│   │   ├── core/
│   │   │   └── config.py  # Configuración dinámica
│   │   └── main.py        # App principal
│   └── main.py
├── frontend/
└── docker-compose.yml
```

## 🔧 Configuraciones Clave

### Base de Datos

**PostgreSQL (Producción/Docker):**
```env
DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/dbname
```

**SQLite (Desarrollo Local):**
```env
DATABASE_URL=sqlite:///./mi_proyecto.db
```

### Redis (Para tareas asíncronas)

```env
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
```

### CORS (Frontend)

```env
CORS_ORIGINS=http://localhost:3000,http://localhost:8000
```

## 🎯 Características Configurables

### 1. Nombre del Proyecto
- Se usa en logs, UI y documentación
- Configurable vía `PROJECT_NAME`

### 2. Base de Datos
- Soporta PostgreSQL, SQLite, MySQL
- Configurable vía `DATABASE_URL`

### 3. APIs Externas
- Todas las APIs son opcionales
- El sistema funciona sin ellas (con funcionalidad limitada)

### 4. Integraciones
- GitHub, HubSpot, Auth0 son opcionales
- Se activan solo si están configuradas

## 🐳 Docker

El sistema funciona con Docker sin cambios:

```bash
# Iniciar con Docker
docker-compose up -d

# Ver logs
docker-compose logs -f backend

# Detener
docker-compose down
```

## 🔒 Seguridad

### Claves Importantes

1. **SECRET_KEY**: Cambia en producción
```env
SECRET_KEY=genera-una-clave-segura-aleatoria
```

2. **ENCRYPTION_KEY**: Para integraciones (32 bytes base64)
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

3. **GITHUB_WEBHOOK_SECRET**: Para webhooks
```env
GITHUB_WEBHOOK_SECRET=tu-secreto-aleatorio
```

## 📊 Ejemplos de Configuración

### Proyecto Mínimo (Solo auditorías básicas)
```env
PROJECT_NAME=Mi Auditor
DATABASE_URL=sqlite:///./auditor.db
DEBUG=True
SECRET_KEY=mi-clave-secreta
```

### Proyecto Completo (Todas las funcionalidades)
```env
PROJECT_NAME=Auditor Pro
DATABASE_URL=postgresql+psycopg2://user:pass@db:5432/auditor
REDIS_URL=redis://redis:6379/0
GOOGLE_API_KEY=...
GOOGLE_PAGESPEED_API_KEY=...
NVIDIA_API_KEY=...
GITHUB_CLIENT_ID=...
GITHUB_CLIENT_SECRET=...
DEBUG=False
SECRET_KEY=clave-super-segura
```

## 🧪 Validación

El sistema valida automáticamente la configuración al iniciar:

```bash
# Iniciar backend
cd backend
python -m backend.main
```

Verás mensajes como:
- ✅ Environment validation passed
- ⚠️ GOOGLE_PAGESPEED_API_KEY is not set - PageSpeed analysis will be limited
- ❌ DATABASE_URL is required

## 🔄 Migración desde Versión Anterior

Si tenías el código hardcodeado:

1. Copia tu `.env` actual
2. Agrega las nuevas variables:
```env
PROJECT_NAME=Tu Nombre
PROJECT_SLUG=tu_slug
```
3. Reinicia los servicios

## 📝 Notas

- **PROJECT_NAME**: Nombre legible para humanos
- **PROJECT_SLUG**: Nombre técnico (sin espacios, minúsculas)
- **DATABASE_URL**: Debe ser válida para SQLAlchemy
- **APIs opcionales**: El sistema funciona sin ellas

## 🆘 Solución de Problemas

### Error: "DATABASE_URL is required"
```env
# Agrega en .env:
DATABASE_URL=sqlite:///./auditor.db
```

### Error: "Missing required environment variables"
```bash
# Verifica que .env existe y tiene las variables críticas
cat .env | grep DATABASE_URL
```

### Error: "CORS policy"
```env
# Agrega tu dominio frontend a CORS_ORIGINS
CORS_ORIGINS=http://localhost:3000,http://tu-dominio.com
```

## 📚 Recursos

- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [SQLAlchemy Docs](https://docs.sqlalchemy.org/)
- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)

---

**¡Listo!** Tu proyecto ahora es completamente configurable y puede adaptarse a cualquier caso de uso.
