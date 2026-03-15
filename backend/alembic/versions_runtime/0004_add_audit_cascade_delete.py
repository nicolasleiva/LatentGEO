"""Add audit cascade delete indexes

Revision ID: 0004_add_audit_cascade_delete
Revises: 0003_ai_content_strategy_runs
Create Date: 2024-01-15

"""
from alembic import op
import sqlalchemy as sa


revision = '0004_add_audit_cascade_delete'
down_revision = '0003_ai_content_strategy_runs'
branch_labels = None
depends_on = None


def upgrade():
    """Add indexes on foreign keys referencing audits.id for faster cascade deletes."""
    
    tables_with_fk = [
        ("keywords", "audit_id"),
        ("backlinks", "audit_id"),
        ("rank_trackings", "audit_id"),
        ("llm_visibilities", "audit_id"),
        ("ai_content_suggestions", "audit_id"),
        ("audited_pages", "audit_id"),
        ("geo_commerce_campaigns", "audit_id"),
        ("geo_article_batches", "audit_id"),
        ("audit_pdf_jobs", "audit_id"),
        ("audit_pagespeed_jobs", "audit_id"),
        ("reports", "audit_id"),
        ("competitors", "audit_id"),
        ("score_history", "audit_id"),
    ]
    
    for table_name, fk_column in tables_with_fk:
        index_name = f"ix_{table_name}_{fk_column}"
        try:
            op.create_index(
                index_name,
                table_name,
                [fk_column],
                unique=False,
            )
        except Exception as e:
            print(f"Index {index_name} may already exist: {e}")


def downgrade():
    """Remove indexes on foreign keys."""
    
    tables_with_fk = [
        ("keywords", "audit_id"),
        ("backlinks", "audit_id"),
        ("rank_trackings", "audit_id"),
        ("llm_visibilities", "audit_id"),
        ("ai_content_suggestions", "audit_id"),
        ("audited_pages", "audit_id"),
        ("geo_commerce_campaigns", "audit_id"),
        ("geo_article_batches", "audit_id"),
        ("audit_pdf_jobs", "audit_id"),
        ("audit_pagespeed_jobs", "audit_id"),
        ("reports", "audit_id"),
        ("competitors", "audit_id"),
        ("score_history", "audit_id"),
    ]
    
    for table_name, fk_column in tables_with_fk:
        index_name = f"ix_{table_name}_{fk_column}"
        try:
            op.drop_index(index_name, table_name=table_name)
        except Exception as e:
            print(f"Index {index_name} may not exist: {e}")
