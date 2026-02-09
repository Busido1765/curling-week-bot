"""expand posts table

Revision ID: 005_expand_posts_table
Revises: 004_add_page_content_entities
Create Date: 2024-01-04 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "005_expand_posts_table"
down_revision = "004_add_page_content_entities"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "posts",
        "content",
        new_column_name="text",
        existing_type=sa.Text(),
        existing_nullable=False,
    )
    op.alter_column("posts", "text", nullable=True)

    op.add_column(
        "posts",
        sa.Column(
            "created_by",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column("posts", sa.Column("entities", postgresql.JSONB(), nullable=True))
    op.add_column("posts", sa.Column("file_id", sa.Text(), nullable=True))
    op.add_column("posts", sa.Column("caption", sa.Text(), nullable=True))
    op.add_column("posts", sa.Column("caption_entities", postgresql.JSONB(), nullable=True))
    op.add_column(
        "posts",
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'draft'"),
        ),
    )
    op.add_column("posts", sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "posts",
        sa.Column(
            "sent_count_success",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "posts",
        sa.Column(
            "sent_count_failed",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    op.create_index("ix_posts_created_at", "posts", ["created_at"])
    op.create_index("ix_posts_status", "posts", ["status"])


def downgrade() -> None:
    op.drop_index("ix_posts_status", table_name="posts")
    op.drop_index("ix_posts_created_at", table_name="posts")
    op.drop_column("posts", "sent_count_failed")
    op.drop_column("posts", "sent_count_success")
    op.drop_column("posts", "sent_at")
    op.drop_column("posts", "status")
    op.drop_column("posts", "caption_entities")
    op.drop_column("posts", "caption")
    op.drop_column("posts", "file_id")
    op.drop_column("posts", "entities")
    op.drop_column("posts", "created_by")
    op.alter_column(
        "posts",
        "text",
        new_column_name="content",
        existing_type=sa.Text(),
        existing_nullable=True,
    )
