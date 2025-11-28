# 🚀 GitHub App - Quick Start Guide

## **¿Qué hace esta integración?**

La GitHub App **convierte automáticamente tus auditorías SEO/GEO en Pull Requests listos para mergear** en tu repositorio.

**En resumen:**
1. Auditas tu sitio (proceso normal que ya tienes)
2. Conectas tu repo de GitHub  
3. GitHub App crea PRs con los fixes aplicados al código
4. Revisas y mergeas

**NO necesitas copiar/pegar fixes manualmente nunca más.**

---

## 🎯 Casos de Uso

### 1. **Equipo de Marketing sin devs**
- Marketing ejecuta auditoría
- GitHub App crea PR con fixes
- Dev revisa y aprueba en 2 minutos
- Deploy automático

### 2. **Freelancer SEO**
- Auditas 10 sitios de clientes
- GitHub App crea 10 PRs (uno por cliente)
- Clientes ven cambios profesionales documentados
- Cobras más por automatización

### 3. **Agencia Enterprise**
- Auditorías mensuales automáticas
- PRs automáticos cada mes
- Tracking de mejoras en el tiempo
- Reportes para clientes

---

## 📋 Pre-requisitos

1. **GitHub Account** con acceso a los repos que quieres optimizar
2. **Auditoría completada** en el sistema
3. **Repositorio** con sitio web (Next.js, Gatsby, HTML, etc.)

---

## 🛠️ Setup Inicial (5 minutos)

### Paso 1: Configurar GitHub App

```bash
# 1. Crear GitHub App en:
https://github.com/settings/apps/new

# 2. Configurar permisos:
Repository permissions:
  - Contents: Read & Write ✅
  - Pull requests: Read & Write ✅
  - Metadata: Read ✅

# 3. Generar Client ID y Secret
# 4. Agregar al .env:
```

```env
GITHUB_CLIENT_ID=Iv1.xxxxxxxxxxxxx
GITHUB_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxx
GITHUB_REDIRECT_URI=http://localhost:3000/integrations/github/callback
GITHUB_WEBHOOK_SECRET=tu_webhook_secret
```

### Paso 2: Generar ENCRYPTION_KEY

```bash
python3 << EOF
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
EOF

# Copiar output al .env:
ENCRYPTION_KEY=tu_key_generada_aqui
```

### Paso 3: Reiniciar backend

```bash
docker-compose restart backend
# o
cd backend && uvicorn app.main:app --reload
```

---

## 🎬 Uso Completo (Ejemplo Real)

### Escenario: Tienes un blog en Next.js que necesita SEO fixes

#### 1. **Ejecutar Auditoría** (ya exists)

```bash
curl -X POST http://localhost:8000/api/audits \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://mi-blog.com"
  }'

# Response:
{
  "id": 42,
  "status": "pending",
  "url": "https://mi-blog.com"
}

# Esperar 2-5 minutos a que complete...
# La auditoría detectará automáticamente:
# - 15 páginas sin meta description
# - 5 páginas con H1 duplicado
# - 20 imágenes sin alt text
```

#### 2. **Conectar GitHub**

```bash
# Frontend:
# Ir a: http://localhost:3000/integrations/github/connect

# O via API:
GET http://localhost:8000/api/github/auth-url

# Response:
{
  "url": "https://github.com/login/oauth/authorize?client_id=...",
  "state": "random_token"
}

# 1. Abrir URL en navegador
# 2. Autorizar aplicación
# 3. Serás redirigido a /callback
# 4. Conexión creada automáticamente
```

#### 3. **Sincronizar Repos**

```bash
# Obtener connection_id de la respuesta del callback
# O listar conexiones:
GET http://localhost:8000/api/github/connections

# Response:
[
  {
    "id": "conn-abc123",
    "username": "tu-usuario",
    "account_type": "user",
    "created_at": "2024-11-26T..."
  }
]

# Sincronizar repos:
POST http://localhost:8000/api/github/sync/conn-abc123

# Response:
{
  "status": "success",
  "synced_count": 12
}
```

#### 4. **Ver Repos Disponibles**

```bash
GET http://localhost:8000/api/github/repos/conn-abc123

# Response:
[
  {
    "id": "repo-xyz789",
    "full_name": "tu-usuario/mi-blog",
    "name": "mi-blog",
    "url": "https://github.com/tu-usuario/mi-blog",
    "site_type": null,  # Aún no analizado
    "auto_audit": false,
    "auto_pr": false
  }
]
```

#### 5. **Analizar Repo (detectar framework)**

```bash
POST http://localhost:8000/api/github/analyze/conn-abc123/repo-xyz789

# Response:
{
  "id": "repo-xyz789",
  "full_name": "tu-usuario/mi-blog",
  "site_type": "nextjs",  # ✅ Detectado!
  "build_command": "npm run build",
  "output_dir": ".next"
}
```

#### 6. **Convertir Auditoría a Fixes**

```bash
GET http://localhost:8000/api/github/audit-to-fixes/42

# Response:
{
  "audit_id": 42,
  "total_fixes": 40,
  "fixes": [
    {
      "type": "meta_description",
      "priority": "CRITICAL",
      "value": "Learn how to build amazing Next.js apps with our comprehensive guide",
      "page_url": "/blog/nextjs-guide",
      "description": "Missing meta description"
    },
    {
      "type": "h1",
      "priority": "HIGH",
      "value": "Complete Next.js Guide 2024",
      "page_url": "/blog/nextjs-guide",
      "description": "Duplicate H1 tags"
    },
    // ... 38 more fixes
  ]
}
```

#### 7. **Crear Pull Request** 🎉

```bash
POST http://localhost:8000/api/github/create-pr \
  -H "Content-Type: application/json" \
  -d '{
    "connection_id": "conn-abc123",
    "repo_id": "repo-xyz789",
    "audit_id": 42,
    "fixes": [
      {
        "type": "meta_description",
        "page_url": "/blog/nextjs-guide",
        "value": "Learn how to build amazing Next.js apps..."
      },
      {
        "type": "h1",
        "page_url": "/blog/nextjs-guide",
        "value": "Complete Next.js Guide 2024"
      }
      // Puedes seleccionar solo algunos fixes o todos
    ]
  }'

# Response:
{
  "id": "pr-123",
  "pr_number": 42,
  "title": "🟠 High Priority SEO/GEO Fixes - 40 improvements (2024-11-26)",
  "html_url": "https://github.com/tu-usuario/mi-blog/pull/42",
  "status": "open",
  "files_changed": 15,
  "expected_improvements": {
    "current": 65.5,
    "expected": 89.2,
    "improvement": 23.7
  }
}
```

#### 8. **Revisar PR en GitHub**

```
https://github.com/tu-usuario/mi-blog/pull/42

Verás:
- ✅ Título profesional
- ✅ Descripción detallada con métricas
- ✅ Lista de cambios aplicados
- ✅ Archivos modificados con diffs
- ✅ Link al audit report completo
- ✅ Impacto esperado en SEO/GEO
```

#### 9. **Mergear y Deploy** ✨

```bash
# En GitHub:
# 1. Review changes
# 2. Si se ve bien, click "Merge pull request"
# 3. Tu CI/CD deployea automáticamente

# Resultado:
# - Sitio optimizado ✅
# - SEO mejorado ✅
# - Sin trabajo manual ✅
```

---

## 📊 Casos Especiales

### Aplicar solo algunos fixes (no todos)

```bash
# En vez de pasar el array completo de fixes,
# filtra solo los que quieres:

POST /api/github/create-pr
{
  "fixes": [
    {
      "type": "meta_description",
      "page_url": "/home",
      "value": "..."
    }
    // Solo este fix, no los demás
  ]
}
```

### Auto-PR para cada push

```bash
# Actualizar configuración del repo:
PATCH /api/github/repos/{repo_id}
{
  "auto_audit": true,  # Auditar en cada push
  "auto_pr": true      # Crear PR automáticamente
}

# Ahora:
# 1. Haces push a main
# 2. Webhook detecta cambio
# 3. Sistema audita sitio
# 4. Si hay issues, crea PR automático
```

### Múltiples repos de un mismo sitio

```bash
# Ejemplo: Frontend en un repo, Backend en otro

# Repo Frontend:
POST /api/github/create-pr
{
  "repo_id": "repo-frontend",
  "audit_id": 42,
  "fixes": [/* fixes de frontend */]
}

# Repo Backend:
POST /api/github/create-pr
{
  "repo_id": "repo-backend",
  "audit_id": 42,
  "fixes": [/* fixes de backend (si aplica) */]
}
```

---

## 🐛 Troubleshooting

### "Repository not found"
```bash
# Asegúrate de haber sincronizado repos:
POST /api/github/sync/{connection_id}
```

### "No page files found"
```bash
# El repo no parece ser un sitio web, o el tipo no está detectado.
# Analiza el repo primero:
POST /api/github/analyze/{connection_id}/{repo_id}

# Tipos soportados:
# - nextjs, gatsby, astro, hugo, jekyll, 11ty, html
```

### "No fixes were modified"
```bash
# Posibles causas:
# 1. Los fixes no aplican a este repo
# 2. Los valores ya están correctos
# 3. El tipo de fix no es soportado aún

# Solución: Verificar audit-to-fixes:
GET /api/github/audit-to-fixes/{audit_id}
# Asegúrate que type != "other"
```

### "Access token expired"
```bash
# Los tokens OAuth de GitHub NO expiran
# (a diferencia de HubSpot que sí)
# Si hay error de autenticación, reconecta:
# 1. Ir a /integrations/github/connect
# 2. Re-autorizar
```

---

## 📈 Métricas y Tracking

```bash
# Ver PRs creados para un repo:
GET /api/github/prs/{repo_id}

# Response:
[
  {
    "id": "pr-123",
    "pr_number": 42,
    "title": "SEO Fixes...",
    "status": "merged",  # open, merged, closed
    "files_changed": 15,
    "created_at": "2024-11-26T...",
    "merged_at": "2024-11-27T...",
    "expected_improvements": {...}
  }
]

# Calcular ROI:
# - Tiempo ahorrado: 15 files × 5 min/file = 75 min
# - Costo dev: 75 min × $100/hr = $125 ahorrados
# - Mejora SEO: +23.7 puntos = más tráfico orgánico
```

---

## 🎓 Best Practices

### 1. **Audita primero, luego aplica**
No crear PRs sin revisar el audit report completo.

### 2. **Revisa siempre los PRs**
Aunque los cambios son automáticos, verifica que el tono/voice sea correcto.

### 3. **Empieza con pocos fixes**
Primera vez: Aplica 5-10 fixes, no los 50 de golpe.

### 4. **Usa branches de feature**
Config el repo para crear PRs en `develop`, no en `main` directo.

### 5. **Monitorea resultados**
Después de mergear, audita de nuevo en 1 semana para validar mejoras.

---

## 🔒 Seguridad Checklist

- [ ] `GITHUB_CLIENT_SECRET` en `.env`, NO en código
- [ ] `ENCRYPTION_KEY` generada con Fernet, no hardcoded
- [ ] Webhook signature verificada en producción
- [ ] Tokens encriptados en base de datos
- [ ] Scopes mínimos necesarios (no `admin`)
- [ ] Rate limiting configurado (TODO)

---

## 📚 Próximos Pasos

1. ✅ Setup completado
2. ⏭️ Frontend para seleccionar fixes visualmente
3. ⏭️ Dashboard de PRs con métricas
4. ⏭️ A/B testing de fixes
5. ⏭️ Auto-merge con confidence score

---

**¿Preguntas?** Ver documentación completa en `GITHUB_APP_IMPLEMENTATION_PLAN.md`
