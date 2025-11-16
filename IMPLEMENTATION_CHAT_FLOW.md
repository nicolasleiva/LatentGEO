# Implementación del Flujo de Chat con KIMI

## Cambios Realizados

### Backend

1. **Nuevo servicio LLM con KIMI** (`backend/app/core/llm_kimi.py`)
   - Usa NVIDIA NIM API con modelo `moonshotai/kimi-k2-instruct-0905`
   - Gemini queda comentado como fallback
   - 40K tokens de output vs 8K de Gemini

2. **Configuración actualizada** (`backend/app/core/config.py`)
   - Agregado `NVIDIA_API_KEY`

3. **Schemas actualizados** (`backend/app/schemas/__init__.py`)
   - `AuditCreate`: agregados `language`, `competitors`, `market`
   - Nuevos schemas: `AuditConfigRequest`, `ChatMessage`

4. **Modelo de base de datos** (`backend/app/models/__init__.py`)
   - Agregados campos: `language`, `competitors`, `market` a tabla `audits`

5. **Nuevo endpoint de chat** (`backend/app/api/routes/audits.py`)
   - `POST /api/audits/chat/config` - Configura auditoría mediante chat

6. **Servicios actualizados**
   - `audit_service.py`: usa `llm_kimi` en lugar de `llm`
   - `tasks.py`: usa `llm_kimi`

### Frontend

1. **Nuevo componente** (`frontend/components/audit-chat-flow.tsx`)
   - Flujo conversacional con 3 pasos:
     - Selección de idioma (ES/EN)
     - Agregar competidores (opcional)
     - Seleccionar mercado objetivo (US, LATAM, EMEA, Argentina)

2. **Página principal actualizada** (`frontend/app/page.tsx`)
   - Detecta URLs automáticamente
   - Muestra chat de configuración antes de iniciar auditoría
   - Redirige al dashboard después de configurar

## Flujo de Usuario

1. Usuario ingresa URL → Se crea auditoría
2. Aparece chat con selector de idioma (🇪🇸 Español / 🇺🇸 English)
3. Usuario selecciona idioma → Chat pregunta por competidores
4. Usuario puede:
   - Agregar URLs de competidores
   - Continuar sin competidores
5. Chat pregunta por mercado objetivo
6. Usuario selecciona mercado (o skip)
7. Configuración se envía al backend
8. PageSpeed inicia automáticamente en background
9. Redirige a dashboard de auditoría

## Instalación

### 1. Migrar Base de Datos

```bash
cd backend
python migrate_add_chat_fields.py
```

### 2. Instalar Dependencias

```bash
# Backend
cd backend
pip install openai

# Frontend (ya instalado)
```

### 3. Configurar Variables de Entorno

El archivo `.env` ya está configurado con:
```
NVIDIA_API_KEY=nvapi-REDACTED
```

### 4. Rebuild Docker

```bash
docker-compose down
docker-compose up -d --build backend worker
```

### 5. Rebuild Frontend

```bash
cd frontend
npm run build
npm run dev
```

## Próximos Pasos (Opcional)

### Integración con Google Search para Mercados

Cuando se selecciona un mercado, el sistema puede:
- Buscar top 10 competidores en esa región usando Google Custom Search
- Agregar parámetros de geolocalización (`gl=us`, `gl=ar`, etc.)
- Analizar automáticamente esos competidores

### Análisis de Competidores

Si el usuario agrega URLs de competidores:
- Ejecutar auditoría local en cada competidor
- Calcular GEO scores
- Generar análisis comparativo en el reporte

### Reportes Multiidioma

El campo `language` se puede usar para:
- Generar prompts del LLM en el idioma seleccionado
- Traducir secciones del reporte
- Adaptar recomendaciones según región

## Testing

1. Ir a `http://localhost:3000`
2. Ingresar URL: `https://example.com`
3. Verificar que aparece chat de configuración
4. Seleccionar idioma, agregar competidores (opcional), seleccionar mercado
5. Verificar redirección a dashboard
6. Verificar que datos se guardaron en BD:

```sql
SELECT id, url, language, competitors, market FROM audits ORDER BY id DESC LIMIT 1;
```

## Notas Técnicas

- **KIMI vs Gemini**: KIMI tiene 5x más tokens de output, ideal para reportes largos
- **Chat Flow**: Componente reutilizable, se puede extender con más pasos
- **PageSpeed**: Inicia automáticamente al crear auditoría, no espera configuración
- **Competidores**: Se guardan como JSON array en BD
- **Mercado**: String simple, se puede expandir a objeto con más metadata

## Troubleshooting

### Error: "NVIDIA_API_KEY not found"
- Verificar `.env` tiene `NVIDIA_API_KEY`
- Rebuild Docker: `docker-compose up -d --build backend`

### Chat no aparece
- Verificar que URL es válida (debe empezar con http:// o https://)
- Verificar console del navegador para errores

### Migración falla
- Si usas PostgreSQL, ajustar sintaxis en `migrate_add_chat_fields.py`
- Para SQLite, debería funcionar sin cambios
