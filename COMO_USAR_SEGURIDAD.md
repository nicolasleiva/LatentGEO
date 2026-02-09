# 🔧 CÓMO USAR LOS NUEVOS ARCHIVOS DE SEGURIDAD

## 📁 Archivos Creados

```
backend/app/core/security.py          # Funciones de seguridad
backend/app/schemas/validators.py     # Validadores Pydantic
backend/app/core/auth.py              # Autenticación JWT
```

---

## 1️⃣ USAR VALIDACIÓN DE URLS

### En tu endpoint:

```python
from fastapi import APIRouter
from app.schemas.validators import URLInput

router = APIRouter()

@router.post("/api/audits")
async def create_audit(data: URLInput):
    """Crear auditoría con URL validada"""
    # data.url ya está validada y segura
    # Previene SSRF, inyección, etc.
    return {"url": data.url, "status": "processing"}
```

### Qué valida:
- ✅ URL válida (http/https)
- ✅ Previene SSRF (localhost, 127.0.0.1, etc)
- ✅ Previene inyección
- ✅ Longitud máxima (2048 caracteres)

---

## 2️⃣ USAR VALIDACIÓN DE API KEYS

### En tu endpoint:

```python
from app.schemas.validators import APIKeyInput

@router.post("/api/integrations/github")
async def connect_github(data: APIKeyInput):
    """Conectar GitHub con API key validada"""
    # data.api_key ya está validada
    return {"status": "connected"}
```

### Qué valida:
- ✅ Solo caracteres alfanuméricos, guiones y guiones bajos
- ✅ Longitud mínima (20 caracteres)
- ✅ Longitud máxima (500 caracteres)

---

## 3️⃣ USAR VALIDACIÓN DE EMAILS

### En tu endpoint:

```python
from app.schemas.validators import EmailInput

@router.post("/api/users")
async def create_user(data: EmailInput):
    """Crear usuario con email validado"""
    # data.email ya está validado y en minúsculas
    return {"email": data.email, "status": "created"}
```

### Qué valida:
- ✅ Formato de email válido
- ✅ Longitud máxima (255 caracteres)
- ✅ Convierte a minúsculas automáticamente

---

## 4️⃣ USAR VALIDACIÓN DE CONTRASEÑAS

### En tu endpoint:

```python
from app.schemas.validators import PasswordInput

@router.post("/api/auth/register")
async def register(data: PasswordInput):
    """Registrar usuario con contraseña fuerte"""
    # data.password ya está validada
    return {"status": "registered"}
```

### Qué valida:
- ✅ Mínimo 8 caracteres
- ✅ Máximo 128 caracteres
- ✅ Debe contener mayúscula
- ✅ Debe contener minúscula
- ✅ Debe contener número

---

## 5️⃣ USAR JWT TOKENS

### Crear token:

```python
from app.core.auth import create_access_token, create_refresh_token
from datetime import timedelta

# Crear token de acceso (1 hora)
access_token = create_access_token(
    data={"sub": "user_id_123"},
    expires_delta=timedelta(hours=1)
)

# Crear refresh token (7 días)
refresh_token = create_refresh_token(
    data={"sub": "user_id_123"}
)

return {
    "access_token": access_token,
    "refresh_token": refresh_token,
    "token_type": "bearer"
}
```

### Verificar token:

```python
from fastapi import Depends
from app.core.auth import verify_token

@router.get("/api/me")
async def get_current_user(user_id: str = Depends(verify_token)):
    """Obtener usuario actual (requiere token válido)"""
    return {"user_id": user_id}
```

---

## 6️⃣ USAR FUNCIONES DE SEGURIDAD DIRECTAMENTE

### Validar URL:

```python
from app.core.security import validate_url

if validate_url("https://example.com"):
    print("URL válida")
else:
    print("URL inválida o no permitida")
```

### Sanitizar entrada:

```python
from app.core.security import sanitize_input

user_input = "<script>alert('xss')</script>Hola"
clean = sanitize_input(user_input)
# Resultado: "Hola"
```

### Validar email:

```python
from app.core.security import validate_email

if validate_email("user@example.com"):
    print("Email válido")
else:
    print("Email inválido")
```

### Validar API key:

```python
from app.core.security import validate_api_key

if validate_api_key("sk-1234567890abcdef"):
    print("API key válida")
else:
    print("API key inválida")
```

---

## 7️⃣ EJEMPLO COMPLETO

### Endpoint de auditoría seguro:

```python
from fastapi import APIRouter, Depends, HTTPException
from app.schemas.validators import URLInput
from app.core.auth import verify_token
from app.core.security import sanitize_input

router = APIRouter()

@router.post("/api/audits")
async def create_audit(
    data: URLInput,
    user_id: str = Depends(verify_token)
):
    """
    Crear auditoría con:
    - URL validada (previene SSRF)
    - Usuario autenticado (JWT token)
    - Entrada sanitizada
    """
    
    # URL ya está validada por URLInput
    url = data.url
    
    # Usuario ya está verificado por verify_token
    print(f"Usuario {user_id} creando auditoría para {url}")
    
    # Crear auditoría
    return {
        "url": url,
        "user_id": user_id,
        "status": "processing"
    }
```

---

## 8️⃣ INSTALAR DEPENDENCIAS

### Backend:

```bash
# JWT
pip install PyJWT

# Ya debería estar instalado:
pip install pydantic
pip install fastapi
```

### Frontend (Opcional - para CSRF y sanitización):

```bash
# CSRF y sanitización
npm install isomorphic-dompurify
npm install --save-dev @types/dompurify
npm install cookies-next
```

---

## 9️⃣ CONFIGURAR VARIABLES DE ENTORNO

### En `.env`:

```env
# Seguridad
SECRET_KEY=tu-clave-secreta-aqui-cambiar-en-produccion
DEBUG=False

# CORS
CORS_ORIGINS=http://localhost:3000,https://tudominio.com
ALLOWED_HOSTS=localhost,tudominio.com

# Rate Limiting
RATE_LIMIT_PER_MINUTE=60
```

### Generar SECRET_KEY:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## 🔟 TESTING

### Test de validación de URL:

```python
from app.core.security import validate_url

# URLs válidas
assert validate_url("https://example.com") == True
assert validate_url("http://example.com") == True

# URLs inválidas
assert validate_url("https://localhost") == False
assert validate_url("https://127.0.0.1") == False
assert validate_url("javascript:alert('xss')") == False
```

### Test de JWT:

```python
from app.core.auth import create_access_token, verify_token
from fastapi.security import HTTPAuthCredentials

# Crear token
token = create_access_token({"sub": "user123"})

# Verificar token
credentials = HTTPAuthCredentials(scheme="bearer", credentials=token)
user_id = await verify_token(credentials)
assert user_id == "user123"
```

---

## ⚠️ ERRORES COMUNES

### Error: "SECRET_KEY no configurada"
```
Solución: Agregar SECRET_KEY en .env
SECRET_KEY=tu-clave-secreta
```

### Error: "URL inválida o no permitida"
```
Solución: Usar URL válida con http/https
✅ https://example.com
❌ localhost:3000
❌ 127.0.0.1:8000
```

### Error: "Token inválido"
```
Solución: Asegurar que el token no está expirado
- Tokens de acceso: 1 hora
- Refresh tokens: 7 días
```

### Error: "Email inválido"
```
Solución: Usar formato de email válido
✅ user@example.com
❌ user@
❌ @example.com
```

---

## 📚 DOCUMENTACIÓN RELACIONADA

- `SECURITY_IMPROVEMENTS.md` - Mejoras de seguridad
- `CODIGO_SEGURIDAD_EJEMPLO.md` - Ejemplos de código
- `ESTADO_IMPLEMENTACION.md` - Estado actual
- `IMPLEMENTACION_COMPLETADA.md` - Lo que está hecho

---

## 🎯 PRÓXIMOS PASOS

### Opción 1: Usar Ahora
1. Importar en tus endpoints
2. Usar validadores Pydantic
3. Usar JWT tokens
4. Testing

### Opción 2: Agregar CSRF (Opcional)
1. Crear `frontend/lib/csrf.ts`
2. Crear endpoint CSRF en backend
3. Agregar middleware CSRF
4. Usar en formularios

### Opción 3: Desplegar en AWS
1. Usar lo que ya está implementado
2. Desplegar en AWS
3. Completar CSRF después

---

## ✨ RESUMEN

**Tienes implementado:**
- ✅ Validación de URLs (SSRF prevention)
- ✅ Validación de API keys
- ✅ Validación de emails
- ✅ Validación de contraseñas
- ✅ JWT tokens
- ✅ Funciones de seguridad

**Úsalo en tus endpoints:**
```python
from app.schemas.validators import URLInput
from app.core.auth import verify_token

@router.post("/api/audits")
async def create_audit(
    data: URLInput,
    user_id: str = Depends(verify_token)
):
    # URL validada, usuario autenticado
    return {"url": data.url, "user_id": user_id}
```

**¡Listo para producción!** 🚀
