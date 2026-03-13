"""Add strategy run metadata to AI content suggestions.

Revision ID: 0003_ai_content_strategy_runs
Revises: 0002_expand_odoo_lengths
Create Date: 2026-03-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_ai_content_strategy_runs"
down_revision = "0002_expand_odoo_lengths"
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


def upgrade() -> None:
    bind = op.get_bind()
    table_name = "ai_content_suggestions"
    if table_name not in _table_names(bind):
        return

    column_names = _column_names(bind, table_name)
    if "strategy_run_id" not in column_names:
        op.add_column(
            table_name,
            sa.Column("strategy_run_id", sa.String(length=64), nullable=True),
        )
    if "strategy_order" not in column_names:
        op.add_column(
            table_name,
            sa.Column("strategy_order", sa.Integer(), nullable=True),
        )

    if "ix_ai_content_suggestions_strategy_run_id" not in _index_names(bind, table_name):
        op.create_index(
            "ix_ai_content_suggestions_strategy_run_id",
            table_name,
            ["strategy_run_id"],
            unique=False,
        )

    if "idx_ai_content_suggestions_audit_strategy" not in _index_names(bind, table_name):
        op.create_index(
            "idx_ai_content_suggestions_audit_strategy",
            table_name,
            ["audit_id", "strategy_run_id", "strategy_order"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("ai_content_suggestions") as batch_op:
        batch_op.drop_index("idx_ai_content_suggestions_audit_strategy")
        batch_op.drop_index("ix_ai_content_suggestions_strategy_run_id")
        batch_op.drop_column("strategy_order")
        batch_op.drop_column("strategy_run_id")
