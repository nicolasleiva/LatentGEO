"""Add webhook_url column to audits table

Revision ID: add_webhook_url_to_audits
Revises: add_geo_score_to_audits
Create Date: 2025-12-22

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "add_webhook_url_to_audits"
down_revision = "add_geo_score_to_audits"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add webhook_url column to audits table"""
    op.add_column(
        "audits", sa.Column("webhook_url", sa.String(length=500), nullable=True)
    )


def downgrade() -> None:
    """Remove webhook_url column from audits table"""
    op.drop_column("audits", "webhook_url")
