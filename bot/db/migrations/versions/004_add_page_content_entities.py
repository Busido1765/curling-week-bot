"""add page content entities

Revision ID: 004_add_page_content_entities
Revises: 003_add_editing_page_to_users
Create Date: 2024-01-03 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "004_add_page_content_entities"
down_revision = "003_add_editing_page_to_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pages",
        sa.Column(
            "content_type",
            sa.String(length=20),
            nullable=False,
            server_default="text",
        ),
    )
    op.add_column("pages", sa.Column("text", sa.Text(), nullable=True))
    op.add_column("pages", sa.Column("entities", postgresql.JSONB(), nullable=True))
    op.add_column("pages", sa.Column("file_id", sa.Text(), nullable=True))
    op.add_column("pages", sa.Column("caption", sa.Text(), nullable=True))
    op.add_column("pages", sa.Column("caption_entities", postgresql.JSONB(), nullable=True))

    op.execute("UPDATE pages SET text = content WHERE text IS NULL")


def downgrade() -> None:
    op.drop_column("pages", "caption_entities")
    op.drop_column("pages", "caption")
    op.drop_column("pages", "file_id")
    op.drop_column("pages", "entities")
    op.drop_column("pages", "text")
    op.drop_column("pages", "content_type")
