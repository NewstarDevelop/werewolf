"""add notification_broadcasts table and broadcast_id fields

Revision ID: 004
Revises: 003
Create Date: 2026-01-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create notification_broadcasts table and add broadcast_id to notifications/outbox."""
    # Create notification_broadcasts table
    op.create_table(
        "notification_broadcasts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("idempotency_key", sa.String(128), nullable=False, unique=True, index=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("category", sa.String(16), nullable=False, index=True),
        sa.Column("data", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("persist_policy", sa.String(16), nullable=False, server_default="DURABLE"),
        sa.Column("status", sa.String(16), nullable=False, server_default="DRAFT", index=True),
        sa.Column("total_targets", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sent_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("resend_of_id", sa.String(36), sa.ForeignKey("notification_broadcasts.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now(), index=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("sent_at", sa.DateTime(), nullable=True, index=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True, index=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "category IN ('GAME','ROOM','SOCIAL','SYSTEM')",
            name="ck_notification_broadcasts_category",
        ),
        sa.CheckConstraint(
            "persist_policy IN ('DURABLE','VOLATILE')",
            name="ck_notification_broadcasts_persist_policy",
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT','SENDING','SENT','PARTIAL_FAILED','FAILED','DELETED')",
            name="ck_notification_broadcasts_status",
        ),
    )

    # Add composite indexes
    op.create_index(
        "idx_notification_broadcasts_status_created_at",
        "notification_broadcasts",
        ["status", "created_at"],
    )
    op.create_index(
        "idx_notification_broadcasts_category_created_at",
        "notification_broadcasts",
        ["category", "created_at"],
    )

    # Add broadcast_id to notifications table
    op.add_column(
        "notifications",
        sa.Column(
            "broadcast_id",
            sa.String(36),
            sa.ForeignKey("notification_broadcasts.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
    )

    # Add broadcast_id to notification_outbox table
    op.add_column(
        "notification_outbox",
        sa.Column(
            "broadcast_id",
            sa.String(36),
            sa.ForeignKey("notification_broadcasts.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
    )


def downgrade() -> None:
    """Remove broadcast_id fields and notification_broadcasts table."""
    # Remove broadcast_id from notification_outbox
    op.drop_column("notification_outbox", "broadcast_id")

    # Remove broadcast_id from notifications
    op.drop_column("notifications", "broadcast_id")

    # Drop indexes
    op.drop_index("idx_notification_broadcasts_category_created_at", table_name="notification_broadcasts")
    op.drop_index("idx_notification_broadcasts_status_created_at", table_name="notification_broadcasts")

    # Drop notification_broadcasts table
    op.drop_table("notification_broadcasts")
