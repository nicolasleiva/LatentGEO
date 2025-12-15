"""Add user fields to audits table

Revision ID: add_user_fields_001
Revises: 
Create Date: 2024-12-04

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_user_fields_001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add user_id and user_email columns to audits table"""
    # Add user_id column
    op.add_column('audits', sa.Column('user_id', sa.String(255), nullable=True))
    op.add_column('audits', sa.Column('user_email', sa.String(255), nullable=True))
    
    # Create indexes for faster lookups
    op.create_index('ix_audits_user_id', 'audits', ['user_id'])
    op.create_index('ix_audits_user_email', 'audits', ['user_email'])


def downgrade() -> None:
    """Remove user fields from audits table"""
    op.drop_index('ix_audits_user_email', 'audits')
    op.drop_index('ix_audits_user_id', 'audits')
    op.drop_column('audits', 'user_email')
    op.drop_column('audits', 'user_id')
