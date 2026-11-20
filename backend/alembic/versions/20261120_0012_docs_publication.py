"""Add live documentation publication controls.

Revision ID: 20261120_0012
Revises: 20261119_0011
"""
from alembic import op
import sqlalchemy as sa

revision = "20261120_0012"
down_revision = "20261119_0011"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "docs_publications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("content_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "docs_publication_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("publication_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=True),
    )
    op.create_index("ix_docs_publication_versions_publication_id", "docs_publication_versions", ["publication_id"])


def downgrade():
    op.drop_index("ix_docs_publication_versions_publication_id", table_name="docs_publication_versions")
    op.drop_table("docs_publication_versions")
    op.drop_table("docs_publications")
