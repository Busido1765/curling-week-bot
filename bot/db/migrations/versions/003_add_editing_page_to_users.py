"""add editing page key to users

Revision ID: 003_add_editing_page_to_users
Revises: 002_seed_pages
Create Date: 2024-01-01 00:00:01.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "003_add_editing_page_to_users"
down_revision = "002_seed_pages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("editing_page_key", sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "editing_page_key")
