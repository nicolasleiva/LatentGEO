"""Add performance indexes

Revision ID: add_performance_indexes_001
Revises: add_geo_score_to_audits
Create Date: 2026-01-26

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_performance_indexes_001'
down_revision = 'add_geo_score_to_audits'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create performance indexes required by tests"""
    # Audits
    op.create_index('idx_audits_user_created', 'audits', ['user_email', 'created_at'])
    op.create_index('idx_audits_user_status', 'audits', ['user_email', 'status'])

    # Audited Pages
    op.create_index('idx_audited_pages_audit', 'audited_pages', ['audit_id'])

    # Competitors
    op.create_index('idx_competitors_audit', 'competitors', ['audit_id'])

    # Reports
    op.create_index('idx_reports_audit_type', 'reports', ['audit_id', 'report_type'])


def downgrade() -> None:
    """Drop indexes created in upgrade"""
    op.drop_index('idx_reports_audit_type', 'reports')
    op.drop_index('idx_competitors_audit', 'competitors')
    op.drop_index('idx_audited_pages_audit', 'audited_pages')
    op.drop_index('idx_audits_user_status', 'audits')
    op.drop_index('idx_audits_user_created', 'audits')
