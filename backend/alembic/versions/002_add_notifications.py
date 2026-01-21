"""add notifications and notification_outbox

Revision ID: 002
Revises: 001
Create Date: 2026-01-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    """Check if a table exists in the database."""
    bind = op.get_bind()
    insp = inspect(bind)
    return table_name in insp.get_table_names()


def _index_exists(index_name: str, table_name: str) -> bool:
    """Check if an index exists on a table."""
    bind = op.get_bind()
    insp = inspect(bind)
    indexes = insp.get_indexes(table_name)
    return any(idx["name"] == index_name for idx in indexes)


def upgrade() -> None:
    """Create notifications and notification_outbox tables."""
    # Create notifications table (if not exists)
    if not _table_exists("notifications"):
        op.create_table(
            "notifications",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("category", sa.String(length=16), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("data", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("read_at", sa.DateTime(), nullable=True),
            sa.CheckConstraint(
                "category IN ('GAME','ROOM','SOCIAL','SYSTEM')",
                name="ck_notifications_category",
            ),
        )
        op.create_index("idx_notifications_user_created_at", "notifications", ["user_id", "created_at"], unique=False)
        op.create_index(
            "idx_notifications_user_read_at_created_at",
            "notifications",
            ["user_id", "read_at", "created_at"],
            unique=False,
        )
        op.create_index("ix_notifications_user_id", "notifications", ["user_id"], unique=False)
        op.create_index("ix_notifications_category", "notifications", ["category"], unique=False)
        op.create_index("ix_notifications_created_at", "notifications", ["created_at"], unique=False)
        op.create_index("ix_notifications_read_at", "notifications", ["read_at"], unique=False)

    # Create notification_outbox table (if not exists)
    if not _table_exists("notification_outbox"):
        op.create_table(
            "notification_outbox",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
            sa.Column("idempotency_key", sa.String(length=255), nullable=False),
            sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("topic", sa.String(length=64), nullable=False, server_default="notifications"),
            sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("status", sa.String(length=16), nullable=False, server_default="PENDING"),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("available_at", sa.DateTime(), nullable=False),
            sa.Column("locked_at", sa.DateTime(), nullable=True),
            sa.Column("locked_by", sa.String(length=128), nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("sent_at", sa.DateTime(), nullable=True),
            sa.CheckConstraint(
                "status IN ('PENDING','SENT','FAILED')",
                name="ck_notification_outbox_status",
            ),
            sa.UniqueConstraint("idempotency_key", name="uq_notification_outbox_idempotency_key"),
        )
        op.create_index("idx_notification_outbox_pending", "notification_outbox", ["status", "available_at", "created_at"], unique=False)
        op.create_index("ix_notification_outbox_status", "notification_outbox", ["status"], unique=False)
        op.create_index("ix_notification_outbox_available_at", "notification_outbox", ["available_at"], unique=False)
        op.create_index("ix_notification_outbox_locked_at", "notification_outbox", ["locked_at"], unique=False)
        op.create_index("ix_notification_outbox_user_id", "notification_outbox", ["user_id"], unique=False)


def downgrade() -> None:
    """Drop notifications and notification_outbox tables."""
    op.drop_index("ix_notification_outbox_user_id", table_name="notification_outbox")
    op.drop_index("ix_notification_outbox_locked_at", table_name="notification_outbox")
    op.drop_index("ix_notification_outbox_available_at", table_name="notification_outbox")
    op.drop_index("ix_notification_outbox_status", table_name="notification_outbox")
    op.drop_index("idx_notification_outbox_pending", table_name="notification_outbox")
    op.drop_table("notification_outbox")

    op.drop_index("ix_notifications_read_at", table_name="notifications")
    op.drop_index("ix_notifications_created_at", table_name="notifications")
    op.drop_index("ix_notifications_category", table_name="notifications")
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_index("idx_notifications_user_read_at_created_at", table_name="notifications")
    op.drop_index("idx_notifications_user_created_at", table_name="notifications")
    op.drop_table("notifications")
