import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from ..core.database import Base


class HubSpotConnection(Base):
    """Conexión con un portal de HubSpot"""

    __tablename__ = "hubspot_connections"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # En un sistema real, esto debería estar vinculado a un usuario o tenant
    # user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    portal_id = Column(String(50), nullable=False)
    access_token = Column(Text, nullable=False)  # Encrypted
    refresh_token = Column(Text, nullable=False)  # Encrypted
    expires_at = Column(DateTime, nullable=False)
    scopes = Column(Text, nullable=False)  # Comma separated or JSON
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    pages = relationship(
        "HubSpotPage", back_populates="connection", cascade="all, delete-orphan"
    )


class HubSpotPage(Base):
    """Página sincronizada de HubSpot"""

    __tablename__ = "hubspot_pages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    connection_id = Column(
        String(36), ForeignKey("hubspot_connections.id"), nullable=False
    )

    hubspot_id = Column(String(50), nullable=False)  # ID interno de HubSpot
    url = Column(String(500), nullable=False)
    title = Column(String(500), nullable=True)
    meta_description = Column(Text, nullable=True)
    html_title = Column(String(500), nullable=True)

    # Metadata de sincronización
    last_synced_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    hubspot_updated_at = Column(DateTime, nullable=True)

    connection = relationship("HubSpotConnection", back_populates="pages")
    changes = relationship(
        "HubSpotChange", back_populates="page", cascade="all, delete-orphan"
    )


class ChangeStatus(str, enum.Enum):
    PENDING = "pending"
    APPLIED = "applied"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class HubSpotChange(Base):
    """Registro de cambios aplicados a HubSpot"""

    __tablename__ = "hubspot_changes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    page_id = Column(String(36), ForeignKey("hubspot_pages.id"), nullable=False)
    audit_id = Column(Integer, ForeignKey("audits.id"), nullable=True)

    field = Column(String(50), nullable=False)  # meta_description, title, content, etc.
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)

    status = Column(Enum(ChangeStatus), default=ChangeStatus.PENDING)
    error_message = Column(Text, nullable=True)

    applied_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    page = relationship("HubSpotPage", back_populates="changes")
    audit = relationship("Audit")
