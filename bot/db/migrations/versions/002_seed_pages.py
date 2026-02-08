"""seed pages

Revision ID: 002_seed_pages
Revises: 001_initial_schema
Create Date: 2024-01-02 00:00:00.000000
"""

from datetime import datetime

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "002_seed_pages"
down_revision = "001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    now = datetime.utcnow()
    insert_stmt = sa.text(
        """
        INSERT INTO pages (key, content, updated_at)
        VALUES (:key, :content, :updated_at)
        ON CONFLICT (key) DO NOTHING
        """
    )
    keys = ("faq", "contacts", "schedule", "photo")
    for key in keys:
        bind.execute(
            insert_stmt,
            {
                "key": key,
                "content": "",
                "updated_at": now,
            },
        )


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM pages WHERE key IN ('faq', 'contacts', 'schedule', 'photo')")
    )
