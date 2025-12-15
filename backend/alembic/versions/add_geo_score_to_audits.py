"""Add geo_score column to audits table

Revision ID: add_geo_score_to_audits
Revises: add_user_fields_001
Create Date: 2025-12-11

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_geo_score_to_audits'
down_revision = 'add_user_fields_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add geo_score column to audits table"""
    op.add_column('audits', sa.Column('geo_score', sa.Float(), nullable=False, server_default='0'))


def downgrade() -> None:
    """Remove geo_score column from audits table"""
    op.drop_column('audits', 'geo_score')
