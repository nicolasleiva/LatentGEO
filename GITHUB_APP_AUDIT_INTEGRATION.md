# 🔗 Integración GitHub App con Flujo de Auditoría

## 📊 ¿Cómo sabe la GitHub App qué está mal?

La GitHub App **NO detecta problemas por sí misma**. En cambio, **utiliza los resultados de tus auditorías existentes**.

### Flujo Completo de Integración

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. AUDITORÍA NORMAL (ya existe en tu sistema)                   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
    Usuario audita su sitio → Crawler detecta problemas
                              ↓
                        Genera fix_plan:
                        [
                          {
                            "issue": "Missing meta description",
                            "priority": "CRITICAL",
                            "page": "/about",
                            "recommended_value": "Learn about..."
                          },
                          {
                            "issue": "Duplicate H1",
                            "priority": "HIGH",
                            ...
                          }
                        ]
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. GITHUB APP INTEGRATION (NUEVO)                               │
└─────────────────────────────────────────────────────────────────┘
                              ↓
    Usuario conecta su repo de GitHub
                              ↓
    GitHub App analiza repo y detecta:
    - Framework (Next.js, Gatsby, etc.)
    - Archivos de páginas
    - Estructura del proyecto
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. CONVERSIÓN DE FIXES (NUEVO)                                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
    GitHub Service toma el fix_plan de la auditoría
                              ↓
    Para cada fix en fix_plan:
      - Identifica el archivo correcto (page.tsx, index.html, etc.)
      - Convierte fix abstracto → código real
      - Ejemplo:
          "Missing meta description" 
          → 
          <meta name="description" content="..." />
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. APLICACIÓN DE CAMBIOS (NUEVO)                                │
└─────────────────────────────────────────────────────────────────┘
                              ↓
    CodeModifierService aplica cambios a archivos:
      - HTML: BeautifulSoup modifica DOM
      - React/Next.js: Regex actualiza JSX/metadata
      - Astro: Modifica frontmatter
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 5. CREACIÓN DE PR (NUEVO)                                       │
└─────────────────────────────────────────────────────────────────┘
                              ↓
    GitHub Client:
      - Crea branch nueva
      - Hace commits con cambios
      - Crea Pull Request profesional
                              ↓
    PR incluye:
      - Archivos modificados
      - Explicación de cada cambio
      - Métricas esperadas de mejora
      - Link al audit report completo
```

---

## 🔌 Endpoints de Integración

### 1. Convertir Auditoría a Fixes Aplicables

**NUEVO ENDPOINT NECESARIO:**

```python
@router.get("/github/audit-to-fixes/{audit_id}")
async def convert_audit_to_fixes(audit_id: int, db: Session = Depends(get_db)):
    """
    Convierte el fix_plan de una auditoría en fixes aplicables a código
    
    INPUT: Audit ID
    OUTPUT: Lista de fixes con información técnica
    """
    audit = db.query(Audit).filter(Audit.id == audit_id).first()
    
    fixes = []
    for item in audit.fix_plan:
        fix = {
            "type": _map_issue_to_fix_type(item["issue"]),
            "priority": item["priority"],
            "value": item.get("recommended_value", ""),
            "page_url": item.get("page", ""),
            "description": item.get("issue", "")
        }
        fixes.append(fix)
    
    return {"audit_id": audit_id, "fixes": fixes}
```

### 2. Mapeo de Issues a Fix Types

```python
def _map_issue_to_fix_type(issue: str) -> str:
    """
    Mapea issues detectados en auditoría a tipos de fixes aplicables
    
    Examples:
        "Missing meta description" → "meta_description"
        "Duplicate H1" → "h1"
        "Missing alt text" → "alt_text"
    """
    mapping = {
        "missing meta description": "meta_description",
        "meta description too short": "meta_description",
        "duplicate h1": "h1",
        "missing h1": "h1",
        "multiple h1": "h1",
        "title tag missing": "title",
        "title too long": "title",
        "missing alt text": "alt_text",
        "missing og:title": "og_title",
        "missing og:description": "og_description",
        # Agregar más según tus issues
    }
    
    issue_lower = issue.lower()
    for key, value in mapping.items():
        if key in issue_lower:
            return value
    
    return "other"
```

---

## 💡 Ejemplo Completo End-to-End

### Paso 1: Usuario audita su sitio

```bash
POST /api/audits
{
  "url": "https://example.com"
}

# Auditoría corre y detecta:
# - Missing meta descriptions en 5 páginas
# - Duplicate H1 en 2 páginas
# - Missing alt text en 10 imágenes
```

### Paso 2: Auditoría genera fix_plan

```json
{
  "audit_id": 123,
  "fix_plan": [
    {
      "issue": "Missing meta description",
      "priority": "CRITICAL",
      "page": "/about",
      "current_value": null,
      "recommended_value": "Learn about our mission to revolutionize SEO with AI-powered tools."
    },
    {
      "issue": "Duplicate H1",
      "priority": "HIGH",
      "page": "/blog/post-1",
      "current_value": "Welcome | Welcome",
      "recommended_value": "Complete Guide to SEO in 2024"
    }
  ]
}
```

### Paso 3: Usuario conecta GitHub repo

```bash
# Frontend:
GET /api/github/auth-url
# → Usuario autoriza app
# → OAuth callback crea GitHubConnection

POST /api/github/sync/{connection_id}
# → Sincroniza repos

POST /api/github/analyze/{connection_id}/{repo_id}
# → Detecta que es Next.js 14 con App Router
```

### Paso 4: Crear PR con fixes

```bash
POST /api/github/create-pr
{
  "connection_id": "conn-123",
  "repo_id": "repo-456",
  "audit_id": 123,
  "fixes": [
    {
      "type": "meta_description",
      "page_url": "/about",
      "value": "Learn about our mission..."
    },
    {
      "type": "h1",
      "page_url": "/blog/post-1",
      "value": "Complete Guide to SEO in 2024"
    }
  ]
}

# GitHub App:
# 1. Encuentra app/about/page.tsx
# 2. Agrega/modifica:
#    export const metadata = {
#      description: "Learn about our mission..."
#    }
# 3. Encuentra app/blog/post-1/page.tsx  
# 4. Modifica <h1>...</h1>
# 5. Crea branch "seo-geo-fixes-123-20241126"
# 6. Hace commits
# 7. Crea PR con todo documentado
```

### Paso 5: PR Creado

```markdown
## 🚀 Automated SEO/GEO Improvements

### 📊 Audit Summary
- Total Pages Analyzed: 15
- Critical Issues Found: 5
- High Priority Issues: 2

### ✅ Changes Applied

#### Meta Description (1 file)
- `app/about/page.tsx`: Added meta description

#### H1 Heading (1 file)
- `app/blog/post-1/page.tsx`: Fixed duplicate H1

### 📈 Expected Impact
- Search Visibility: +15%
- Click-through Rate: +8%
- AI Citation Potential: +12%

[View full audit report](https://your-app.com/audits/123)
```

---

## ⚙️ Configuración Requerida

### 1. Variables de Entorno

```env
# .env
GITHUB_CLIENT_ID=your_github_app_client_id
GITHUB_CLIENT_SECRET=your_github_app_client_secret
GITHUB_REDIRECT_URI=http://localhost:3000/integrations/github/callback
GITHUB_WEBHOOK_SECRET=your_webhook_secret
ENCRYPTION_KEY=your_32_byte_base64_key
```

### 2. GitHub App Settings

Ir a https://github.com/settings/apps/new

**Permisos:**
- Repository contents: Read & Write
- Pull requests: Read & Write
- Metadata: Read
- Webhooks: Read & Write

**Webhooks:**
- URL: `https://tu-dominio.com/api/github/webhook`
- Events: `push`, `pull_request`

---

## 🧪 Testing

### Test 1: OAuth Flow

```bash
# 1. Get auth URL
curl http://localhost:8000/api/github/auth-url

# 2. Visit URL in browser, authorize app

# 3. Callback will be called automatically
# Verify connection created in DB
```

### Test 2: Create PR

```bash
# Crear auditoría de prueba
curl -X POST http://localhost:8000/api/audits \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}'

# Esperar a que complete (audit_id=1)

# Conectar GitHub y crear PR
curl -X POST http://localhost:8000/api/github/create-pr \
  -H "Content-Type: application/json" \
  -d '{
    "connection_id": "your-conn-id",
    "repo_id": "your-repo-id",
    "audit_id": 1,
    "fixes": [
      {
        "type": "meta_description",
        "page_url": "/",
        "value": "Test meta description"
      }
    ]
  }'

# Verificar PR creado en GitHub
```

---

## 📝 Próximos Pasos

1. ✅ Backend completo implementado
2. ⏳ **Crear endpoint `/github/audit-to-fixes/{audit_id}`**
3. ⏳ Frontend para conectar repos
4. ⏳ Frontend para ver/aplicar fixes
5. ⏳ Webhooks para auto-auditoría
6. ⏳ Tests automatizados

---

## 🔒 Seguridad

- ✅ Tokens OAuth encriptados en BD
- ✅ Webhook signatures verificadas
- ✅ No hay hardcoded credentials
- ✅ Scopes mínimos necesarios
- ⏳ Rate limiting (TODO)
- ⏳ User permissions (TODO)
