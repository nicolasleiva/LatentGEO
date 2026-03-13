"""Reconcile runtime schema into a single official Alembic head.

Revision ID: 0001_reconcile_runtime_schema
Revises:
Create Date: 2026-03-11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.core.database import Base
from app import models  # noqa: F401

revision = "0001_reconcile_runtime_schema"
down_revision = None
branch_labels = None
depends_on = None


def _table_names(bind) -> set[str]:
    return set(sa.inspect(bind).get_table_names())


def _column_names(bind, table_name: str) -> set[str]:
    inspector = sa.inspect(bind)
    if table_name not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(bind, table_name: str) -> set[str]:
    inspector = sa.inspect(bind)
    if table_name not in inspector.get_table_names():
        return set()
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _ensure_column(table_name: str, column_name: str, column: sa.Column) -> None:
    bind = op.get_bind()
    if table_name not in _table_names(bind):
        return
    if column_name in _column_names(bind, table_name):
        return
    op.add_column(table_name, column)


def _ensure_index(table_name: str, index_name: str, columns_sql: str, *, unique: bool = False) -> None:
    bind = op.get_bind()
    if table_name not in _table_names(bind):
        return
    if index_name in _index_names(bind, table_name):
        return
    uniqueness = "UNIQUE " if unique else ""
    op.execute(
        sa.text(
            f"CREATE {uniqueness}INDEX IF NOT EXISTS {index_name} "
            f"ON {table_name} ({columns_sql})"
        )
    )


def _ensure_owner_columns() -> None:
    owner_columns = [
        ("github_connections", "owner_user_id"),
        ("github_connections", "owner_email"),
        ("hubspot_connections", "owner_user_id"),
        ("hubspot_connections", "owner_email"),
        ("odoo_connections", "owner_user_id"),
        ("odoo_connections", "owner_email"),
    ]
    for table_name, column_name in owner_columns:
        _ensure_column(
            table_name,
            column_name,
            sa.Column(column_name, sa.String(length=255), nullable=True),
        )


def _ensure_runtime_columns() -> None:
    _ensure_column(
        "audits",
        "source",
        sa.Column("source", sa.String(length=50), nullable=True, server_default="web"),
    )
    _ensure_column(
        "audits",
        "user_id",
        sa.Column("user_id", sa.String(length=255), nullable=True),
    )
    _ensure_column(
        "audits",
        "user_email",
        sa.Column("user_email", sa.String(length=255), nullable=True),
    )
    _ensure_column(
        "audits",
        "geo_score",
        sa.Column("geo_score", sa.Float(), nullable=False, server_default="0"),
    )
    _ensure_column(
        "audits",
        "webhook_url",
        sa.Column("webhook_url", sa.String(length=500), nullable=True),
    )
    _ensure_column(
        "audit_pdf_jobs",
        "waiting_on",
        sa.Column("waiting_on", sa.String(length=40), nullable=True),
    )
    _ensure_column(
        "audit_pdf_jobs",
        "dependency_job_id",
        sa.Column("dependency_job_id", sa.Integer(), nullable=True),
    )


def _ensure_runtime_indexes() -> None:
    indexes = [
        ("audits", "ix_audits_user_id", "user_id"),
        ("audits", "ix_audits_user_email", "user_email"),
        ("audits", "idx_audits_user_created", "user_email, created_at"),
        ("audits", "idx_audits_user_status", "user_email, status"),
        ("audited_pages", "idx_audited_pages_audit", "audit_id"),
        ("competitors", "idx_competitors_audit", "audit_id"),
        ("reports", "idx_reports_audit_type", "audit_id, report_type"),
        ("keywords", "idx_keywords_audit", "audit_id"),
        ("backlinks", "idx_backlinks_audit", "audit_id"),
        ("rank_trackings", "idx_rank_tracking_audit", "audit_id"),
        ("llm_visibilities", "idx_llm_visibility_audit", "audit_id"),
        ("score_history", "idx_score_history_domain_date", "domain, recorded_at"),
        (
            "geo_commerce_campaigns",
            "idx_geo_commerce_campaigns_audit",
            "audit_id, created_at",
        ),
        (
            "geo_article_batches",
            "idx_geo_article_batches_audit",
            "audit_id, created_at",
        ),
        (
            "github_connections",
            "idx_github_connections_owner_user_id",
            "owner_user_id",
        ),
        ("github_connections", "idx_github_connections_owner_email", "owner_email"),
        (
            "hubspot_connections",
            "idx_hubspot_connections_owner_user_id",
            "owner_user_id",
        ),
        ("hubspot_connections", "idx_hubspot_connections_owner_email", "owner_email"),
        ("odoo_connections", "ix_odoo_connections_owner_user_id", "owner_user_id"),
        ("odoo_connections", "ix_odoo_connections_owner_email", "owner_email"),
        (
            "audit_pdf_jobs",
            "ix_audit_pdf_jobs_requested_by_user_id",
            "requested_by_user_id",
        ),
        ("audit_pdf_jobs", "ix_audit_pdf_jobs_celery_task_id", "celery_task_id"),
        ("audit_pdf_jobs", "ix_audit_pdf_jobs_report_id", "report_id"),
        ("audit_pdf_jobs", "ix_audit_pdf_jobs_dependency_job_id", "dependency_job_id"),
        ("audit_pdf_jobs", "ix_audit_pdf_jobs_created_at", "created_at"),
        ("audit_pdf_jobs", "uq_audit_pdf_jobs_audit_id", "audit_id"),
        (
            "audit_pagespeed_jobs",
            "ix_audit_pagespeed_jobs_requested_by_user_id",
            "requested_by_user_id",
        ),
        (
            "audit_pagespeed_jobs",
            "ix_audit_pagespeed_jobs_celery_task_id",
            "celery_task_id",
        ),
        ("audit_pagespeed_jobs", "ix_audit_pagespeed_jobs_created_at", "created_at"),
        ("audit_pagespeed_jobs", "uq_audit_pagespeed_jobs_audit_id", "audit_id"),
    ]

    for table_name, index_name, columns_sql in indexes:
        _ensure_index(
            table_name,
            index_name,
            columns_sql,
            unique=index_name.startswith("uq_"),
        )


def _ensure_runtime_tables() -> None:
    bind = op.get_bind()
    table_names = _table_names(bind)
    for table_name in ("audit_pdf_jobs", "audit_pagespeed_jobs"):
        if table_name in table_names:
            continue
        Base.metadata.tables[table_name].create(bind=bind, checkfirst=True)


def upgrade() -> None:
    _ensure_runtime_tables()
    _ensure_runtime_columns()
    _ensure_owner_columns()
    _ensure_runtime_indexes()


def downgrade() -> None:
    # Baseline reconciliation is intentionally irreversible.
    pass
