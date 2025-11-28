# 🔗 HubSpot Integration - Plan de Implementación

## 📋 Resumen Ejecutivo

Integración con HubSpot CMS para permitir:
1. **Auditoría automática** de páginas de HubSpot
2. **Aplicación directa de cambios SEO/GEO** desde nuestro sistema
3. **Validación y rollback** de cambios aplicados

---

## 🎯 Caso de Uso Principal

**Flujo completo:**
```
Usuario → Conecta HubSpot → Selecciona páginas → Ejecuta auditoría
→ Revisa recomendaciones → Aprueba cambios → Sistema aplica cambios
→ Re-auditoría automática → Validación de mejoras
```

**Ejemplo práctico:**
- Usuario tiene 50 páginas en HubSpot con meta descriptions faltantes
- Sistema lo detecta y genera descripciones optimizadas con IA
- Usuario aprueba los cambios
- Sistema actualiza las 50 páginas automáticamente
- **Resultado**: 2 horas de trabajo → 5 minutos

---

## 🔌 APIs de HubSpot Necesarias

### 1. **CMS Hub API** (Principal)
```
GET /cms/v3/pages/site-pages
GET /cms/v3/pages/site-pages/{pageId}
PATCH /cms/v3/pages/site-pages/{pageId}
```

**Permite:**
- Listar todas las páginas
- Obtener contenido completo de una página
- Actualizar contenido, meta tags, HTML

### 2. **Content API**
```
GET /content/api/v2/pages
PATCH /content/api/v2/pages/{page_id}
```

**Permite:**
- Acceso a páginas antiguas (v2)
- Retrocompatibilidad

### 3. **Blog Posts API**
```
GET /content/api/v2/blog-posts
PATCH /content/api/v2/blog-posts/{post_id}
```

**Permite:**
- Auditar y editar posts de blog
- Actualizar metadata de artículos

### 4. **OAuth API**
```
POST /oauth/v1/token
```

**Permite:**
- Autenticación segura
- Permisos granulares

---

## 🏗️ Arquitectura de la Integración

### Backend (FastAPI)

```
backend/
├── app/
│   ├── integrations/
│   │   ├── hubspot/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py           # OAuth flow
│   │   │   ├── client.py         # API client
│   │   │   ├── pages.py          # Pages operations
│   │   │   ├── content.py        # Content operations
│   │   │   └── sync.py           # Sync operations
│   ├── api/routes/
│   │   ├── hubspot_auth.py       # OAuth endpoints
│   │   ├── hubspot_pages.py      # Pages management
│   │   └── hubspot_sync.py       # Sync & apply changes
│   ├── models/
│   │   ├── hubspot_connection.py # DB model
│   │   └── hubspot_page.py       # Page snapshot
│   └── services/
│       └── hubspot_service.py    # Business logic
```

### Frontend (Next.js)

```
frontend/
├── app/
│   ├── integrations/
│   │   └── hubspot/
│   │       ├── connect/page.tsx       # OAuth init
│   │       ├── callback/page.tsx      # OAuth callback
│   │       ├── pages/page.tsx         # List pages
│   │       └── editor/[id]/page.tsx   # Edit & apply
│   └── audits/[id]/
│       └── hubspot-apply/page.tsx     # Apply recommendations
```

---

## 📊 Modelo de Datos

### HubSpotConnection
```python
class HubSpotConnection(Base):
    id: UUID
    user_id: UUID
    portal_id: str              # HubSpot Portal ID
    access_token: str           # Encrypted
    refresh_token: str          # Encrypted
    expires_at: datetime
    scopes: List[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
```

### HubSpotPage
```python
class HubSpotPage(Base):
    id: UUID
    connection_id: UUID
    hubspot_page_id: str
    url: str
    title: str
    meta_description: str
    content_html: str
    last_synced_at: datetime
    last_modified_at: datetime
    audit_id: UUID              # Link to audit
```

### HubSpotChange
```python
class HubSpotChange(Base):
    id: UUID
    page_id: UUID
    audit_id: UUID
    field: str                  # "meta_description", "title", "content"
    old_value: str
    new_value: str
    status: str                 # "pending", "approved", "applied", "rejected"
    applied_at: datetime
    applied_by: UUID
    rollback_available: bool
```

---

## 🔐 Flujo de Autenticación

### 1. OAuth Setup
```python
# app/integrations/hubspot/auth.py

HUBSPOT_CLIENT_ID = settings.HUBSPOT_CLIENT_ID
HUBSPOT_CLIENT_SECRET = settings.HUBSPOT_CLIENT_SECRET
REDIRECT_URI = f"{settings.APP_URL}/integrations/hubspot/callback"

SCOPES = [
    "content",           # Read/write CMS content
    "cms.pages.write",   # Modify pages
    "cms.pages.read",    # Read pages
]

def get_authorization_url():
    return (
        f"https://app.hubspot.com/oauth/authorize"
        f"?client_id={HUBSPOT_CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&scope={' '.join(SCOPES)}"
    )

async def exchange_code_for_token(code: str):
    # Exchange authorization code for access token
    pass
```

### 2. Token Management
```python
async def refresh_access_token(connection: HubSpotConnection):
    # Refresh expired token
    pass

async def ensure_valid_token(connection: HubSpotConnection):
    if connection.expires_at < datetime.now():
        return await refresh_access_token(connection)
    return connection.access_token
```

---

## 🚀 Funcionalidades Clave

### Feature 1: Sync Pages
```python
@router.post("/api/hubspot/sync")
async def sync_hubspot_pages(
    connection_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Sincroniza todas las páginas de HubSpot con nuestra DB
    """
    connection = get_hubspot_connection(db, connection_id)
    client = HubSpotClient(connection)
    
    pages = await client.get_all_pages()
    
    for page in pages:
        # Store in our DB
        save_hubspot_page(db, page)
    
    return {"synced": len(pages)}
```

### Feature 2: Audit HubSpot Pages
```python
@router.post("/api/hubspot/audit")
async def audit_hubspot_pages(
    connection_id: UUID,
    page_ids: List[str],
    db: Session = Depends(get_db)
):
    """
    Ejecuta auditoría en páginas de HubSpot
    """
    # Similar to existing audit but for HubSpot pages
    audit = create_audit(db, source="hubspot")
    
    for page_id in page_ids:
        page = get_hubspot_page(db, page_id)
        # Run audit on page.url
        await run_audit_on_url(page.url, audit.id)
    
    return audit
```

### Feature 3: Generate & Apply Recommendations
```python
@router.post("/api/hubspot/apply-recommendations")
async def apply_recommendations(
    audit_id: UUID,
    changes: List[HubSpotChangeRequest],
    db: Session = Depends(get_db)
):
    """
    Aplica cambios recomendados directamente a HubSpot
    """
    audit = get_audit(db, audit_id)
    connection = get_hubspot_connection_for_audit(db, audit_id)
    client = HubSpotClient(connection)
    
    results = []
    for change in changes:
        # Apply change to HubSpot
        success = await client.update_page(
            page_id=change.page_id,
            field=change.field,
            value=change.new_value
        )
        
        if success:
            # Record change in DB
            record_change(db, change, status="applied")
            results.append({"page_id": change.page_id, "status": "success"})
        else:
            results.append({"page_id": change.page_id, "status": "failed"})
    
    return {"applied": results}
```

### Feature 4: Rollback Changes
```python
@router.post("/api/hubspot/rollback")
async def rollback_changes(
    change_ids: List[UUID],
    db: Session = Depends(get_db)
):
    """
    Revierte cambios aplicados
    """
    for change_id in change_ids:
        change = get_change(db, change_id)
        client = HubSpotClient(change.connection)
        
        # Revert to old value
        await client.update_page(
            page_id=change.page_id,
            field=change.field,
            value=change.old_value
        )
        
        update_change_status(db, change_id, "rolled_back")
    
    return {"rolled_back": len(change_ids)}
```

---

## 🎨 UI/UX Flow

### 1. Connect HubSpot
```tsx
// frontend/app/integrations/hubspot/connect/page.tsx

export default function HubSpotConnect() {
  const handleConnect = async () => {
    const authUrl = await fetch('/api/hubspot/auth-url').then(r => r.json())
    window.location.href = authUrl.url
  }
  
  return (
    <div>
      <h1>Connect HubSpot</h1>
      <button onClick={handleConnect}>
        Connect Your HubSpot Portal
      </button>
    </div>
  )
}
```

### 2. Select Pages to Audit
```tsx
// frontend/app/integrations/hubspot/pages/page.tsx

export default function HubSpotPages() {
  const [pages, setPages] = useState([])
  const [selected, setSelected] = useState([])
  
  const handleAudit = async () => {
    const audit = await fetch('/api/hubspot/audit', {
      method: 'POST',
      body: JSON.stringify({ page_ids: selected })
    }).then(r => r.json())
    
    router.push(`/audits/${audit.id}`)
  }
  
  return (
    <div>
      <h1>HubSpot Pages</h1>
      <PageList 
        pages={pages} 
        onSelect={setSelected}
      />
      <button onClick={handleAudit}>Audit Selected</button>
    </div>
  )
}
```

### 3. Review & Apply Changes
```tsx
// frontend/app/audits/[id]/hubspot-apply/page.tsx

export default function HubSpotApply() {
  const [recommendations, setRecommendations] = useState([])
  const [selectedChanges, setSelectedChanges] = useState([])
  
  const handleApply = async () => {
    const result = await fetch('/api/hubspot/apply-recommendations', {
      method: 'POST',
      body: JSON.stringify({ changes: selectedChanges })
    }).then(r => r.json())
    
    toast.success(`Applied ${result.applied.length} changes!`)
  }
  
  return (
    <div>
      <h1>Apply SEO Recommendations to HubSpot</h1>
      
      {recommendations.map(rec => (
        <ChangeCard
          key={rec.id}
          recommendation={rec}
          onSelect={(change) => setSelectedChanges([...selectedChanges, change])}
        />
      ))}
      
      <button onClick={handleApply}>
        Apply {selectedChanges.length} Changes
      </button>
    </div>
  )
}
```

---

## 🔒 Seguridad y Mejores Prácticas

### 1. **Encriptación de Tokens**
```python
from cryptography.fernet import Fernet

def encrypt_token(token: str) -> str:
    cipher = Fernet(settings.ENCRYPTION_KEY)
    return cipher.encrypt(token.encode()).decode()

def decrypt_token(encrypted_token: str) -> str:
    cipher = Fernet(settings.ENCRYPTION_KEY)
    return cipher.decrypt(encrypted_token.encode()).decode()
```

### 2. **Validación Pre-Aplicación**
```python
async def validate_change(change: HubSpotChange) -> bool:
    """Valida que el cambio sea seguro antes de aplicar"""
    
    # 1. Verificar que no rompa HTML
    if change.field == "content_html":
        if not is_valid_html(change.new_value):
            return False
    
    # 2. Verificar longitud de meta tags
    if change.field == "meta_description":
        if len(change.new_value) > 160:
            return False
    
    # 3. Verificar que no contenga contenido malicioso
    if contains_malicious_content(change.new_value):
        return False
    
    return True
```

### 3. **Audit Trail**
```python
# Registrar TODOS los cambios
class HubSpotAuditLog(Base):
    id: UUID
    change_id: UUID
    user_id: UUID
    action: str  # "preview", "apply", "rollback"
    timestamp: datetime
    ip_address: str
    user_agent: str
```

---

## 📈 Roadmap de Implementación

### Fase 1: MVP (2-3 semanas)
- [ ] OAuth integration
- [ ] Sync pages from HubSpot
- [ ] Display pages in dashboard
- [ ] Run audit on HubSpot pages
- [ ] Manual application of simple changes (meta tags only)

### Fase 2: Automation (2 semanas)
- [ ] Batch apply recommendations
- [ ] AI-generated content suggestions
- [ ] Preview changes before applying
- [ ] Rollback mechanism

### Fase 3: Advanced (3 semanas)
- [ ] Content editor integrado
- [ ] Bulk operations (50+ pages)
- [ ] Scheduled auto-fixes
- [ ] A/B testing integration
- [ ] Advanced analytics

### Fase 4: Enterprise (4 semanas)
- [ ] Multi-portal support
- [ ] Team workflows (approval process)
- [ ] Compliance checks
- [ ] Custom rules engine
- [ ] Webhook integrations

---

## 💰 Modelo de Monetización

### Pricing Tiers

**Basic (Gratis)**
- Connect 1 HubSpot portal
- Audit up to 10 pages/month
- View recommendations

**Pro ($99/mes)**
- Unlimited portals
- Audit unlimited pages
- Apply up to 100 changes/month
- Basic rollback

**Enterprise ($299/mes)**
- Everything in Pro
- Unlimited changes
- Advanced rollback & versioning
- Team workflows
- Priority support
- Custom integrations

---

## 🎯 Diferenciadores vs Competencia

| Feature | Semrush | Ahrefs | **Tu Software** |
|---------|---------|--------|-----------------|
| Audit HubSpot | ❌ | ❌ | ✅ |
| Apply Changes | ❌ | ❌ | ✅ |
| AI Content Fix | ❌ | ❌ | ✅ |
| Rollback | ❌ | ❌ | ✅ |
| Real-time Sync | ❌ | ❌ | ✅ |
| GEO-specific | ❌ | ❌ | ✅ |

**Tu ventaja**: Única herramienta que AUDITA + EJECUTA cambios en HubSpot con foco GEO.

---

## 📚 Recursos Necesarios

### Documentación
- [HubSpot CMS API](https://developers.hubspot.com/docs/api/cms/pages)
- [HubSpot OAuth](https://developers.hubspot.com/docs/api/working-with-oauth)

### Stack Técnico
- `httpx` - HTTP client para Python
- `pydantic` - Data validation
- Encryption: `cryptography`
- Frontend: React components para editor

### Costos
- HubSpot Developer Account: **Gratis**
- HubSpot CMS Hub requerido para clientes: **$23-$360/mes** (ellos pagan)
- Infraestructura adicional: **$20-50/mes** (Redis para job queues)

---

## 🚨 Riesgos y Mitigaciones

### Riesgo 1: Rate Limits de HubSpot
**Mitigación**: 
- Implementar queue system con Celery
- Respetar límites: 100 requests/10 segundos
- Implementar exponential backoff

### Riesgo 2: Cambios incorrectos
**Mitigación**:
- Preview obligatorio antes de aplicar
- Validación exhaustiva
- Rollback automático en 24hrs
- Backup de contenido original

### Riesgo 3: Cambios en API de HubSpot
**Mitigación**:
- Usar versiones estables de API
- Monitoreo de deprecation notices
- Tests automatizados de integración

---

## ✅ Conclusión

**VIABILIDAD: ALTA ✅**

Esta integración es:
1. ✅ Técnicamente factible
2. ✅ Comercialmente valiosa
3. ✅ Diferenciador único en el mercado
4. ✅ Escalable y mantenible

**RECOMENDACIÓN**: Implementar en fases, empezando con MVP de read-only (audit) y luego agregar write (apply changes).

**ROI ESTIMADO**: 
- Tiempo de desarrollo: 8-12 semanas
- Potencial de ingresos: +$5k-15k/mes MRR
- Diferenciación competitiva: 🚀 ENORME
