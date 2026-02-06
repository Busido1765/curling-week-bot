"""initial schema

Revision ID: 001_initial_schema
Revises: 
Create Date: 2024-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


status_enum = sa.Enum(
    "NONE",
    "TOKEN_VERIFIED",
    "SUBSCRIPTION_VERIFIED",
    "CONFIRMED",
    name="registrationstatus",
)


def upgrade() -> None:
    status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tg_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("status", status_enum, nullable=False, server_default="NONE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "posts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("content_type", sa.String(length=50), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "pages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(length=100), nullable=False, unique=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("pages")
    op.drop_table("posts")
    op.drop_table("users")
    status_enum.drop(op.get_bind(), checkfirst=True)
