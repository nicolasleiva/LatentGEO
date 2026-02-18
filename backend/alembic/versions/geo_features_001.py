"""Add GEO features tables

Revision ID: geo_features_001
Revises: 
Create Date: 2024-11-25

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "geo_features_001"
down_revision = None  # Actualizar con la última revisión existente
branch_labels = None
depends_on = None


def upgrade():
    # CitationTracking table
    op.create_table(
        "citation_tracking",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("audit_id", sa.Integer(), nullable=False),
        sa.Column("query", sa.String(length=500), nullable=False),
        sa.Column("llm_name", sa.String(length=50), nullable=False),
        sa.Column("is_mentioned", sa.Boolean(), default=False),
        sa.Column("citation_text", sa.Text(), nullable=True),
        sa.Column("sentiment", sa.String(length=20), nullable=True),
        sa.Column("position", sa.Integer(), nullable=True),
        sa.Column("full_response", sa.Text(), nullable=True),
        sa.Column("tracked_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["audit_id"],
            ["audits.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_citation_tracking_tracked_at"),
        "citation_tracking",
        ["tracked_at"],
        unique=False,
    )

    # DiscoveredQuery table
    op.create_table(
        "discovered_queries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("audit_id", sa.Integer(), nullable=False),
        sa.Column("query", sa.String(length=500), nullable=False),
        sa.Column("intent", sa.String(length=50), nullable=True),
        sa.Column("mentions_brand", sa.Boolean(), default=False),
        sa.Column("potential_score", sa.Integer(), default=0),
        sa.Column("sample_response", sa.Text(), nullable=True),
        sa.Column("discovered_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["audit_id"],
            ["audits.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # CompetitorCitationAnalysis table
    op.create_table(
        "competitor_citation_analysis",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("audit_id", sa.Integer(), nullable=False),
        sa.Column("your_mentions", sa.Integer(), default=0),
        sa.Column("competitor_data", sa.JSON(), nullable=True),
        sa.Column("gap_analysis", sa.JSON(), nullable=True),
        sa.Column("analyzed_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["audit_id"],
            ["audits.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("competitor_citation_analysis")
    op.drop_table("discovered_queries")
    op.drop_index(
        op.f("ix_citation_tracking_tracked_at"), table_name="citation_tracking"
    )
    op.drop_table("citation_tracking")
