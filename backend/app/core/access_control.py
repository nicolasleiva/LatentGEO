"""
Ownership and tenant isolation helpers.
"""

from typing import TypeVar

from app.core.auth import AuthUser
from app.core.config import settings
from app.models import Audit
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

T = TypeVar("T")


def _normalize_email(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    return normalized or None


def ensure_audit_access(audit: Audit | None, user: AuthUser) -> Audit:
    """
    Enforce strict access control over an audit object.
    """
    if audit is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Auditoría no encontrada"
        )

    owner_user_id = (audit.user_id or "").strip()
    owner_email = _normalize_email(audit.user_email)

    # Prefer stable ID matching when available.
    if owner_user_id and owner_user_id == user.user_id:
        return audit

    # Fall back to normalized email matching for legacy rows.
    if owner_email and user.email and owner_email == _normalize_email(user.email):
        return audit

    # Development fallback for legacy local data without ownership.
    if settings.DEBUG and not owner_user_id and not owner_email:
        return audit

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="No autorizado para esta auditoría",
    )


def is_connection_owned_by_user(connection: object, user: AuthUser) -> bool:
    """Ownership check without side effects (useful for list filters)."""
    owner_user_id = (getattr(connection, "owner_user_id", "") or "").strip()
    owner_email = _normalize_email(getattr(connection, "owner_email", None))
    user_email = _normalize_email(user.email)

    if owner_user_id and owner_user_id == user.user_id:
        return True
    if owner_email and user_email and owner_email == user_email:
        return True
    return False


def ensure_connection_access(
    connection: T | None,
    user: AuthUser,
    db: Session,
    resource_label: str = "conexión",
) -> T:
    """
    Enforce ownership on integration connections.
    Legacy rows without owner are blocked in production and auto-claimed in DEBUG.
    """
    if connection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{resource_label.capitalize()} no encontrada",
        )

    if is_connection_owned_by_user(connection, user):
        return connection

    owner_user_id = (getattr(connection, "owner_user_id", "") or "").strip()
    owner_email = _normalize_email(getattr(connection, "owner_email", None))
    user_email = _normalize_email(user.email)

    if not owner_user_id and not owner_email:
        if settings.DEBUG:
            setattr(connection, "owner_user_id", user.user_id)
            setattr(connection, "owner_email", user_email)
            db.add(connection)
            db.commit()
            db.refresh(connection)
            return connection

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"{resource_label.capitalize()} legacy sin owner bloqueada en producción",
        )

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"No autorizado para esta {resource_label}",
    )
