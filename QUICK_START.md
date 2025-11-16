# 🚀 Quick Start - 5 Minutos

## ⚡ Instalación Express

### Paso 1: Ejecutar Script (2 min)
```bash
# Doble click en:
install_chat_flow.bat
```

Esto hará:
- ✅ Instalar `openai` package
- ✅ Migrar base de datos
- ✅ Rebuild Docker containers
- ✅ Instalar dependencias frontend

### Paso 2: Iniciar Frontend (1 min)
```bash
cd frontend
npm run dev
```

### Paso 3: Probar (2 min)
1. Abrir: `http://localhost:3000`
2. Ingresar URL: `https://ceibo.digital`
3. ¡Ver el chat en acción!

---

## 🎬 Demo del Flujo

### 1️⃣ Pantalla Inicial
```
┌─────────────────────────────────────┐
│  AI-Powered SEO & GEO Auditing      │
│                                     │
│  [Ingresa URL aquí...]              │
│                                     │
│  [Full Site Audit] [Competitor]    │
└─────────────────────────────────────┘
```

### 2️⃣ Usuario Ingresa URL
```
Usuario escribe: https://example.com
```

### 3️⃣ Chat Aparece - Selector de Idioma
```
┌─────────────────────────────────────┐
│ 🤖 ¡Hola! Voy a ayudarte a         │
│    configurar tu auditoría.         │
│    Primero, selecciona el idioma:   │
└─────────────────────────────────────┘

    [🇪🇸 Español]    [🇺🇸 English]
```

### 4️⃣ Usuario Selecciona Español
```
┌─────────────────────────────────────┐
│ 👤 Español                          │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ 🤖 Perfecto, el reporte será en     │
│    español. ¿Deseas agregar         │
│    análisis competitivo?            │
└─────────────────────────────────────┘

[https://competitor.com...] [Agregar]

Competidores agregados:
• https://competitor1.com [Eliminar]

[Continuar sin competidores]
[Continuar con 1 competidor]
```

### 5️⃣ Usuario Agrega Competidor (Opcional)
```
┌─────────────────────────────────────┐
│ 👤 1 competidor agregado            │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ 🤖 ¿Deseas seleccionar un mercado   │
│    objetivo para análisis regional? │
└─────────────────────────────────────┘
```

### 6️⃣ Selector de Mercado
```
┌──────────────┬──────────────┐
│   🇺🇸        │   🌎         │
│ Estados      │ Latinoamérica│
│ Unidos       │              │
└──────────────┴──────────────┘
┌──────────────┬──────────────┐
│   🇪🇺        │   🇦🇷        │
│ España/EMEA  │ Argentina    │
└──────────────┴──────────────┘

[Continuar sin mercado específico]
```

### 7️⃣ Usuario Selecciona Latinoamérica
```
┌─────────────────────────────────────┐
│ 👤 Latinoamérica                    │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ 🤖 ¡Perfecto! Iniciando auditoría   │
│    completa...                      │
└─────────────────────────────────────┘

        ⏳ Configurando auditoría...
```

### 8️⃣ Redirección a Dashboard
```
→ Redirige a: /audits/123

┌─────────────────────────────────────┐
│ Auditoría #123                      │
│ https://example.com                 │
│                                     │
│ Estado: Running... 45%              │
│ ████████░░░░░░░░░░░░                │
│                                     │
│ PageSpeed: ✅ Completado            │
│ Crawling: 🔄 En progreso            │
│ Análisis IA: ⏳ Pendiente           │
└─────────────────────────────────────┘
```

---

## 🔍 Verificación

### Verificar que todo funciona:

#### 1. Backend está corriendo
```bash
docker-compose ps

# Deberías ver:
# auditor_backend   Up
# auditor_worker    Up
# auditor_db        Up
# auditor_redis     Up
```

#### 2. Frontend está corriendo
```bash
# En otra terminal:
cd frontend
npm run dev

# Deberías ver:
# ▲ Next.js 14.x.x
# - Local: http://localhost:3000
```

#### 3. Base de datos tiene nuevos campos
```bash
# Conectar a PostgreSQL
docker exec -it auditor_db psql -U auditor -d auditor_db

# Ejecutar:
\d audits

# Deberías ver:
# language    | character varying(10)
# competitors | json
# market      | character varying(50)
```

#### 4. NVIDIA API Key está configurada
```bash
# Ver .env
cat backend/.env | grep NVIDIA_API_KEY

# Deberías ver:
# NVIDIA_API_KEY=nvapi-REDACTED
```

---

## 🐛 Solución Rápida de Problemas

### ❌ Error: "Module 'openai' not found"
```bash
cd backend
pip install openai
docker-compose restart backend worker
```

### ❌ Chat no aparece
1. Verificar que URL empieza con `http://` o `https://`
2. Abrir DevTools (F12) → Console
3. Buscar errores en rojo

### ❌ "Cannot connect to backend"
```bash
# Verificar que backend está corriendo
docker-compose ps

# Si no está, iniciar:
docker-compose up -d
```

### ❌ Migración falla
```bash
# Si usas PostgreSQL, editar:
backend/migrate_add_chat_fields.py

# Cambiar sintaxis según tu BD
# Luego ejecutar:
python backend/migrate_add_chat_fields.py
```

---

## 📝 Checklist Final

Antes de usar en producción:

- [ ] ✅ Backend corriendo sin errores
- [ ] ✅ Frontend corriendo en localhost:3000
- [ ] ✅ Chat aparece al ingresar URL
- [ ] ✅ Selector de idioma funciona
- [ ] ✅ Input de competidores funciona
- [ ] ✅ Selector de mercado funciona
- [ ] ✅ Redirección a dashboard funciona
- [ ] ✅ PageSpeed inicia automáticamente
- [ ] ✅ Datos se guardan en BD
- [ ] ✅ PDF se genera correctamente

---

## 🎉 ¡Listo!

Tu herramienta ahora tiene:
- ✅ Chat conversacional
- ✅ LLM KIMI (40K tokens)
- ✅ Reportes multiidioma
- ✅ Análisis competitivo
- ✅ Segmentación por mercado

**Siguiente paso**: Probar con un sitio real y ver los resultados.

**Documentación completa**: Ver `IMPLEMENTATION_CHAT_FLOW.md`

**Estrategia de pricing**: Ver `PRICING_STRATEGY.md`

---

## 💬 Comandos Útiles

```bash
# Ver logs del backend
docker-compose logs -f backend

# Ver logs del worker
docker-compose logs -f worker

# Reiniciar todo
docker-compose restart

# Parar todo
docker-compose down

# Iniciar todo
docker-compose up -d

# Rebuild completo
docker-compose down
docker-compose up -d --build

# Ver base de datos
docker exec -it auditor_db psql -U auditor -d auditor_db
```

---

**¿Problemas?** Revisa `IMPLEMENTATION_CHAT_FLOW.md` sección Troubleshooting.
