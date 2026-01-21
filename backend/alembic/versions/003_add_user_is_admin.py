"""add is_admin to users table

Revision ID: 003
Revises: 002
Create Date: 2026-01-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    bind = op.get_bind()
    insp = inspect(bind)
    columns = [col["name"] for col in insp.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    """Add is_admin column to users table."""
    if not _column_exists("users", "is_admin"):
        op.add_column(
            "users",
            sa.Column("is_admin", sa.Boolean(), nullable=False, server_default="0")
        )


def downgrade() -> None:
    """Remove is_admin column from users table."""
    op.drop_column("users", "is_admin")
