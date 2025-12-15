# 🚀 Cómo Usar GitHub Auto-Fix

## ✅ Estado: IMPLEMENTADO Y FUNCIONANDO

El sistema GitHub Auto-Fix está completamente funcional. Aquí está cómo usarlo:

---

## 📋 Requisitos Previos

1. **GitHub OAuth App configurada:**
   - Ve a GitHub → Settings → Developer Settings → OAuth Apps
   - Crea una nueva OAuth App con:
     - **Homepage URL:** `http://localhost:3000`
     - **Authorization callback URL:** `http://localhost:8000/api/github/oauth/callback`
   - Anota el `Client ID` y `Client Secret`

2. **Configura las variables de entorno:**
   ```bash
   # En tu .env
   GITHUB_CLIENT_ID=tu_client_id_aqui
   GITHUB_CLIENT_SECRET=tu_client_secret_aqui
   ```

3. **Reinicia el backend:**
   ```bash
   docker-compose restart backend
   ```

---

## 🎯 Flujo de Uso

### Paso 1: Conectar GitHub (Primera vez)

1. Ve a cualquier auditoría completada: `/audits/{id}`
2. En la sección "SEO & GEO Tools", haz clic en **GitHub Auto-Fix**
3. Si es la primera vez, verás un botón **"Connect GitHub Account"**
4. Haz clic y autoriza la aplicación en GitHub
5. Serás redirigido de vuelta a la aplicación

### Paso 2: Sincronizar Repositorios

Una vez conectado, el sistema automáticamente:
- Obtiene tus repositorios de GitHub
- Detecta si son Next.js, React, o HTML estáticos
- Los guarda en la base de datos

### Paso 3: Crear Pull Request Automático

1. Abre el dashboard de una auditoría completada
2. Haz clic en **GitHub Auto-Fix** en la sección de herramientas
3. En el modal que se abre:
   - Selecciona tu cuenta de GitHub (si tienes varias)
   - Selecciona el repositorio objetivo
   - Verás un resumen de los issues a arreglar
4. Haz clic en **"Create Auto-Fix PR"**
5. Espera mientras la IA genera el código (puede tardar 30-60 segundos)
6. ¡Listo! Verás un link al Pull Request en GitHub

---

## 🔍 Qué Arregla Automáticamente

La IA tiene acceso a TODO el contexto de tu auditoría:

✅ **Datos de PageSpeed:**
- Métricas Core Web Vitals (LCP, CLS, FID)
- Oportunidades de optimización
- Sugerencias de rendimiento

✅ **Auditoría Técnica:**
- Estado de Schema.org
- Problemas de H1
- Meta descripciones faltantes
- HTML semántico

✅ **Contexto de Negocio:**
- Keywords objetivo
- Competidores principales
- Plan de arreglos (fix_plan)
- Sugerencias de contenido IA

### Ejemplos de Fixes Aplicados:

1. **Metadata:** Titles y descriptions SEO-optimizados
2. **Schema.org:** JSON-LD con datos reales de la página
3. **FAQs:** Preguntas frecuentes relevantes al contenido
4. **H1 Hierarchy:** Estructura de headings correcta (H1→H2→H3)
5. **Alt Text:** Descripciones contextuales para imágenes
6. **Author Bio:** Información de autor y E-E-A-T
7. **Performance:** Optimizaciones sugeridas por PageSpeed

---

## 🐛 Troubleshooting

### El botón no aparece
- Asegúrate de que el frontend esté corriendo: `docker ps | grep frontend`
- Refresca la página con Ctrl+F5

### "Connect GitHub" no funciona
- Verifica que `GITHUB_CLIENT_ID` y `GITHUB_CLIENT_SECRET` estén configurados
- Revisa los logs: `docker logs auditor_backend | grep github`

### No aparecen repositorios
- Primero sincroniza tus repos:
  ```bash
  curl -X POST http://localhost:8000/api/github/connections/{connection_id}/sync
  ```

### El PR falla al crearse
- Verifica que el repositorio sea Next.js (debe tener `next.config.js`)
- Revisa los logs del backend para ver errores específicos
- Asegúrate de que la auditoría tenga datos completos (PageSpeed, keywords, etc.)

---

## 📊 Arquitectura Técnica

```
Frontend (Next.js)
    ↓ (Dialog con GitHubIntegration component)
    |
    ↓ HTTP POST /api/github/create-auto-fix-pr
    |
Backend (FastAPI)
    ↓ GitHubService.create_pr_with_fixes()
    |
GitHub Integration Layer
    ├─ service.py: Extrae contexto de auditoría
    ├─ code_modifier.py: Aplica fixes a cada archivo
    └─ nextjs_modifier.py: Usa Kimi AI para transformar código
        ↓
    Kimi AI (NVIDIA NIM)
        Genera código JSX optimizado
        ↓
    GitHub API
        Crea branch → Commits → Pull Request
```

---

## 🎓 Próximos Pasos

Una vez que el PR esté creado:

1. **Revisa el PR en GitHub** - La IA explica cada cambio
2. **Haz ajustes manuales** si es necesario
3. **Mergea el PR** - Los cambios van a producción
4. **Re-audita** - Verifica que el score mejoró

---

**💡 Tip:** La calidad de los fixes depende de la calidad de la auditoría. Asegúrate de que la auditoría tenga:
- PageSpeed ejecutado
- Keywords descubiertas
- Competidores analizados
- Fix plan generado por el LLM

**Estado del Sistema:** ✅ Backend corriendo | ✅ Frontend actualizado | ⚠️ GitHub OAuth pendiente de configurar
