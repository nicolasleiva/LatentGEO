# 🚀 GitHub App Integration - README

## ¿Qué es esto?

**Convierte automáticamente auditorías SEO/GEO en Pull Requests listos para mergear.**

Tu flujo actual:
```
Auditas → Ves issues → Copias/pegas fixes manualmente → Deploy
```

Nuevo flujo con GitHub App:
```
Auditas → Click botón → PR creado con fixes aplicados → Mergeas → Deploy
```

---

## ¿Cómo funciona?

### 1. **Tu sistema audita el sitio** (proceso normal que ya tienes)
- Crawler detecta problemas
- Genera `fix_plan` con issues y soluciones recomendadas

### 2. **GitHub App traduce issues a código** (NUEVO)
```python
# Issue de auditoría:
{
  "issue": "Missing meta description",
  "page": "/about",
  "recommended_value": "Learn about our mission..."
}

# Se convierte en:
# app/about/page.tsx
export const metadata = {
  description: "Learn about our mission..."
}
```

### 3. **Crea PR automáticamente** (NUEVO)
- Detecta framework (Next.js, Gatsby, etc.)
- Encuentra archivos correctos
- Aplica cambios
- Hace commits
- Crea PR profesional en GitHub

---

## Instalación Rápida (5 min)

### 1. Instalar dependencias

```bash
cd backend
pip install PyGithub==2.1.1 cryptography==41.0.7
```

### 2. Crear GitHub App

```
https://github.com/settings/apps/new

Permisos:
- Repository contents: Read & Write ✅
- Pull requests: Read & Write ✅

Webhook URL: https://tu-dominio.com/api/github/webhook
```

### 3. Agregar credenciales

```bash
# .env
GITHUB_CLIENT_ID=Iv1.xxxxx
GITHUB_CLIENT_SECRET=xxxxx
GITHUB_REDIRECT_URI=http://localhost:3000/integrations/github/callback

# Generar encryption key:
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Copiar output:
ENCRYPTION_KEY=tu_key_aqui
```

### 4. Reiniciar

```bash
docker-compose restart backend
# o
uvicorn app.main:app --reload
```

---

## Uso

### Método 1: Via Frontend (cuando esté listo)

```
1. Ir a /integrations/github/connect
2. Conectar GitHub
3. Seleccionar repo
4. Ver fixes sugeridos
5. Click "Create PR"
6. ✨ Done!
```

### Método 2: Via API (ahora)

```bash
# 1. Auditoresultados tu sitio
POST /api/audits
{"url": "https://mi-sitio.com"}
# → audit_id = 42

# 2. Conectar GitHub
GET /api/github/auth-url
# → Abrir URL, autorizar

# 3. Sync repos
POST /api/github/sync/{connection_id}

# 4. Analizar repo
POST /api/github/analyze/{connection_id}/{repo_id}

# 5. Ver fixes disponibles
GET /api/github/audit-to-fixes/42

# 6. Crear PR
POST /api/github/create-pr
{
  "connection_id": "...",
  "repo_id": "...",
  "audit_id": 42,
  "fixes": [...]  # Del paso 5
}

# 7. Ir a GitHub y mergear el PR
```

---

## Frameworks Soportados

- ✅ **Next.js** (App Router + Pages Router)
- ✅ **Gatsby** (Helmet + Head API)
- ✅ **Astro**
- ✅ **HTML estático**
- ⏳ Hugo (parcial)
- ⏳ Jekyll (parcial)
- ⏳ 11ty (parcial)

**¿Tu framework no está?** Es fácil agregarlo - ver `code_modifier.py`

---

## Tipos de Fixes

- ✅ Meta descriptions
- ✅ Title tags
- ✅ H1 headings
- ✅ Image alt text
- ✅ Open Graph tags
- ⏳ Schema markup (próximamente)
- ⏳ Canonical URLs (próximamente)

---

## Ejemplo Real

**Input (auditoría detecta):**
```json
{
  "issue": "Missing meta description",
  "page": "/blog/seo-guide",
  "priority": "CRITICAL"
}
```

**Output (PR aplica):**
```tsx
// app/blog/seo-guide/page.tsx
export const metadata = {
  title: "Complete SEO Guide 2024",
  description: "Learn everything about SEO with our comprehensive guide. From basics to advanced techniques."
}
```

**Resultado:**
- PR#42 creado: "🔴 Critical SEO Fixes"
- 15 archivos modificados
- Mejora esperada: +18.5 puntos SEO

---

## Arquitectura

```
Auditoría genera fix_plan
         ↓
/api/github/audit-to-fixes/{id}
Convierte issues → fixes aplicables
         ↓
GitHub Service
1. Detecta framework
2. Encuentra archivos
3. Aplica cambios
         ↓
Code Modifier
Modifica código según tipo
         ↓
GitHub Client
Crea branch, commits, PR
         ↓
PR Generator
Template profesional + métricas
```

---

## Archivos Importantes

```
backend/app/integrations/github/
├── oauth.py              - OAuth flow
├── client.py             - GitHub API wrapper
├── code_modifier.py      - Aplica fixes a código
├── pr_generator.py       - Template de PRs
└── service.py            - Lógica principal

backend/app/api/routes/
└── github.py             - API endpoints

backend/app/models/
└── github.py             - BD models

Documentación:
├── GITHUB_APP_SUMMARY.md         - Resumen completo
├── GITHUB_APP_QUICK_START.md     - Guía paso a paso
└── GITHUB_APP_AUDIT_INTEGRATION.md - Integración técnica
```

---

## Seguridad

- ✅ OAuth tokens encriptados (Fernet/AES)
- ✅ Webhook signatures verificadas
- ✅ Scopes mínimos
- ✅ No hay hardcoded secrets
- ✅ Environment variables

---

## Testing

```bash
# Unit tests
pytest tests/test_github_*.py

# Integration test (requiere GitHub token)
pytest tests/integration/test_github_flow.py
```

---

## Troubleshooting

### "No page files found"
→ El repo no parece ser un sitio web. Asegúrate de tener `package.json`, `index.html`, etc.

### "Repository not found"
→ Ejecuta `POST /api/github/sync/{connection_id}` primero

### "Access denied"
→ Re-conecta GitHub: `GET /api/github/auth-url`

### "No fixes were applied"
→ Verifica que los fixes sean del tipo correcto con `/audit-to-fixes`

---

## Logs

```bash
# Ver logs del backend:
docker-compose logs -f backend

# Buscar GitHub operations:
docker-compose logs backend | grep "GitHub"
```

---

## Próximos Pasos

1. [x] Backend completo
2. [ ] Frontend para seleccionar fixes
3. [ ] Dashboard de PRs con métricas
4. [ ] Auto-PR en cada push (webhooks)
5. [ ] A/B testing de fixes
6. [ ] Batch PR para múltiples repos

---

## Contribuir

Para agregar soporte de un nuevo framework:

```python
# 1. Agregar detección en client.py
def detect_site_type(self, repo):
    # ...
    if "mi-framework.config.js" in file_names:
        config["site_type"] = "mi-framework"

# 2. Agregar modificador en code_modifier.py
def _apply_fixes_to_mi_framework(content, fixes):
    # Parsear y modificar archivos del framework
    return modified_content

# 3. Agregar test
def test_mi_framework_detection():
    assert detect_site_type(...) == "mi-framework"
```

---

## Soporte

- 📚 **Docs completas:** Ver `GITHUB_APP_*.md`
- 🐛 **Issues:** [GitHub Issues](tu-repo/issues)
- 💬 **Preguntas:** [Discussions](tu-repo/discussions)

---

## License

Same as main project

---

**🎉 ¡Ahorra horas de trabajo manual con PRs automáticos!**
