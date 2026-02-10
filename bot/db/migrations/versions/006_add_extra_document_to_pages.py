"""add extra document fields to pages

Revision ID: 006_add_extra_document_to_pages
Revises: 005_expand_posts_table
Create Date: 2026-02-10 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "006_add_extra_document_to_pages"
down_revision = "005_expand_posts_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pages", sa.Column("extra_document_file_id", sa.Text(), nullable=True))
    op.add_column("pages", sa.Column("extra_document_caption", sa.Text(), nullable=True))
    op.add_column("pages", sa.Column("extra_document_caption_entities", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("pages", "extra_document_caption_entities")
    op.drop_column("pages", "extra_document_caption")
    op.drop_column("pages", "extra_document_file_id")
