"""
Ownership and tenant isolation helpers.
"""
from fastapi import HTTPException, status

from app.core.auth import AuthUser
from app.core.config import settings
from app.models import Audit


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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Auditoría no encontrada")

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

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado para esta auditoría")
