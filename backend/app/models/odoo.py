import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from ..core.database import Base


class OdooConnection(Base):
    __tablename__ = "odoo_connections"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_user_id = Column(String(255), nullable=True, index=True)
    owner_email = Column(String(255), nullable=True, index=True)
    base_url = Column(String(500), nullable=False)
    database = Column(String(255), nullable=False)
    expected_email = Column(String(255), nullable=False)
    label = Column(String(255), nullable=True)
    api_key = Column(Text, nullable=False)
    odoo_version = Column(String(120), nullable=True)
    capabilities = Column(JSON, nullable=True)
    warnings = Column(JSON, nullable=True)
    detected_user = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True)
    last_validated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    audits = relationship("Audit", back_populates="odoo_connection")
    sync_runs = relationship(
        "OdooSyncRun", back_populates="connection", cascade="all, delete-orphan"
    )
    record_snapshots = relationship(
        "OdooRecordSnapshot", back_populates="connection", cascade="all, delete-orphan"
    )
    draft_actions = relationship(
        "OdooDraftAction", back_populates="connection", cascade="all, delete-orphan"
    )


class OdooSyncRun(Base):
    __tablename__ = "odoo_sync_runs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    connection_id = Column(
        String(36), ForeignKey("odoo_connections.id"), nullable=False, index=True
    )
    audit_id = Column(Integer, ForeignKey("audits.id"), nullable=False, index=True)
    status = Column(String(40), default="pending")
    summary = Column(JSON, nullable=True)
    warnings = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)

    connection = relationship("OdooConnection", back_populates="sync_runs")
    audit = relationship("Audit", back_populates="odoo_sync_runs")
    snapshots = relationship(
        "OdooRecordSnapshot", back_populates="sync_run", cascade="all, delete-orphan"
    )
    draft_actions = relationship(
        "OdooDraftAction", back_populates="sync_run", cascade="all, delete-orphan"
    )


class OdooRecordSnapshot(Base):
    __tablename__ = "odoo_record_snapshots"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    connection_id = Column(
        String(36), ForeignKey("odoo_connections.id"), nullable=False, index=True
    )
    audit_id = Column(Integer, ForeignKey("audits.id"), nullable=False, index=True)
    sync_run_id = Column(
        String(36), ForeignKey("odoo_sync_runs.id"), nullable=True, index=True
    )
    odoo_model = Column(String(120), nullable=False, index=True)
    odoo_record_id = Column(String(120), nullable=False, index=True)
    record_name = Column(String(500), nullable=True)
    record_path = Column(String(500), nullable=True, index=True)
    record_url = Column(String(1000), nullable=True)
    is_published = Column(Boolean, default=False)
    field_snapshot = Column(JSON, nullable=True)
    write_capabilities = Column(JSON, nullable=True)
    capabilities = Column(JSON, nullable=True)
    external_updated_at = Column(String(120), nullable=True)
    last_synced_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), index=True
    )

    connection = relationship("OdooConnection", back_populates="record_snapshots")
    audit = relationship("Audit", back_populates="odoo_record_snapshots")
    sync_run = relationship("OdooSyncRun", back_populates="snapshots")
    draft_actions = relationship(
        "OdooDraftAction", back_populates="snapshot", cascade="all, delete-orphan"
    )


class OdooDraftAction(Base):
    __tablename__ = "odoo_draft_actions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    connection_id = Column(
        String(36), ForeignKey("odoo_connections.id"), nullable=False, index=True
    )
    audit_id = Column(Integer, ForeignKey("audits.id"), nullable=False, index=True)
    snapshot_id = Column(
        String(36), ForeignKey("odoo_record_snapshots.id"), nullable=True, index=True
    )
    sync_run_id = Column(
        String(36), ForeignKey("odoo_sync_runs.id"), nullable=True, index=True
    )
    action_key = Column(String(255), nullable=False, index=True)
    draft_type = Column(String(50), nullable=False)
    status = Column(String(50), default="draft", index=True)
    title = Column(String(500), nullable=True)
    target_model = Column(String(120), nullable=True)
    target_record_id = Column(String(120), nullable=True)
    target_path = Column(String(500), nullable=True)
    external_record_id = Column(String(120), nullable=True)
    draft_payload = Column(JSON, nullable=True)
    evidence = Column(JSON, nullable=True)
    acceptance_criteria = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    connection = relationship("OdooConnection", back_populates="draft_actions")
    audit = relationship("Audit", back_populates="odoo_draft_actions")
    snapshot = relationship("OdooRecordSnapshot", back_populates="draft_actions")
    sync_run = relationship("OdooSyncRun", back_populates="draft_actions")
