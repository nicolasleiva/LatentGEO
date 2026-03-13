"""Expand Odoo draft action string lengths.

Revision ID: 0002_expand_odoo_lengths
Revises: 0001_reconcile_runtime_schema
Create Date: 2026-03-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_expand_odoo_lengths"
down_revision = "0001_reconcile_runtime_schema"
branch_labels = None
depends_on = None


def _column_length(bind, table_name: str, column_name: str) -> int | None:
    inspector = sa.inspect(bind)
    if table_name not in inspector.get_table_names():
        return None
    for column in inspector.get_columns(table_name):
        if column.get("name") != column_name:
            continue
        column_type = column.get("type")
        return getattr(column_type, "length", None)
    return None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "odoo_draft_actions" not in inspector.get_table_names():
        return

    action_key_length = _column_length(bind, "odoo_draft_actions", "action_key")
    target_path_length = _column_length(bind, "odoo_draft_actions", "target_path")

    with op.batch_alter_table("odoo_draft_actions") as batch_op:
        if action_key_length is None or action_key_length < 500:
            batch_op.alter_column(
                "action_key",
                existing_type=sa.String(length=255),
                type_=sa.String(length=500),
                existing_nullable=False,
            )
        if target_path_length is None or target_path_length < 2048:
            batch_op.alter_column(
                "target_path",
                existing_type=sa.String(length=500),
                type_=sa.String(length=2048),
                existing_nullable=True,
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "odoo_draft_actions" not in inspector.get_table_names():
        return

    action_key_length = _column_length(bind, "odoo_draft_actions", "action_key")
    target_path_length = _column_length(bind, "odoo_draft_actions", "target_path")

    with op.batch_alter_table("odoo_draft_actions") as batch_op:
        if target_path_length is None or target_path_length > 500:
            batch_op.alter_column(
                "target_path",
                existing_type=sa.String(length=2048),
                type_=sa.String(length=500),
                existing_nullable=True,
            )
        if action_key_length is None or action_key_length > 255:
            batch_op.alter_column(
                "action_key",
                existing_type=sa.String(length=500),
                type_=sa.String(length=255),
                existing_nullable=False,
            )
