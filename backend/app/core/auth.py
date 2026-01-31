"""
Autenticación JWT - Production Ready
"""
import jwt
import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer

# HTTPAuthorizationCredentials is the correct name in newer FastAPI versions
try:
    from fastapi.security import HTTPAuthorizationCredentials
except ImportError:
    from fastapi.security import HTTPAuthCredentials as HTTPAuthorizationCredentials

security = HTTPBearer(auto_error=False)  # Don't auto-raise 403

def get_secret_key() -> str:
    """Obtener SECRET_KEY desde variables de entorno"""
    secret = os.getenv("SECRET_KEY")
    if not secret:
        raise ValueError("SECRET_KEY no configurada")
    return secret

def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None
) -> str:
    """Crear JWT token con expiración"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(hours=1)

    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    
    encoded_jwt = jwt.encode(
        to_encode,
        get_secret_key(),
        algorithm="HS256"
    )
    return encoded_jwt

def create_refresh_token(data: dict) -> str:
    """Crear refresh token con expiración de 7 días"""
    return create_access_token(data, expires_delta=timedelta(days=7))

async def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:
    """Verificar JWT token"""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token no proporcionado",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    token = credentials.credentials
    
    try:
        payload = jwt.decode(
            token,
            get_secret_key(),
            algorithms=["HS256"]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido"
            )
        return user_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido"
        )
