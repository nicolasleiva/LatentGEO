"""Add persistent audit PDF jobs table

Revision ID: add_audit_pdf_jobs_001
Revises: add_performance_indexes_001, add_webhook_url_to_audits
Create Date: 2026-03-11

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "add_audit_pdf_jobs_001"
down_revision = ("add_performance_indexes_001", "add_webhook_url_to_audits")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_pdf_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("audit_id", sa.Integer(), nullable=False),
        sa.Column("requested_by_user_id", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("celery_task_id", sa.String(length=255), nullable=True),
        sa.Column(
            "force_pagespeed_refresh",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "force_report_refresh",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "force_external_intel_refresh",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("warnings", sa.JSON(), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("report_id", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["audit_id"], ["audits.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("audit_id", name="uq_audit_pdf_jobs_audit_id"),
    )
    op.create_index(
        "ix_audit_pdf_jobs_requested_by_user_id",
        "audit_pdf_jobs",
        ["requested_by_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_audit_pdf_jobs_report_id", "audit_pdf_jobs", ["report_id"], unique=False
    )
    op.create_index(
        "ix_audit_pdf_jobs_celery_task_id",
        "audit_pdf_jobs",
        ["celery_task_id"],
        unique=False,
    )
    op.create_index(
        "ix_audit_pdf_jobs_created_at", "audit_pdf_jobs", ["created_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_audit_pdf_jobs_created_at", table_name="audit_pdf_jobs")
    op.drop_index("ix_audit_pdf_jobs_celery_task_id", table_name="audit_pdf_jobs")
    op.drop_index("ix_audit_pdf_jobs_report_id", table_name="audit_pdf_jobs")
    op.drop_index(
        "ix_audit_pdf_jobs_requested_by_user_id", table_name="audit_pdf_jobs"
    )
    op.drop_table("audit_pdf_jobs")
