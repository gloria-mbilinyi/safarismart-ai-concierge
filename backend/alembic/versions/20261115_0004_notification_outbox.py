"""Add transactional booking notification outbox.

Revision ID: 20261115_0004
Revises: 20261114_0003
Create Date: 2026-11-15
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261115_0004"
down_revision: str | None = "20261114_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the SMS notification outbox and worker claim fields."""

    op.create_table(
        "booking_notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("booking_request_id", sa.Uuid(), nullable=False),
        sa.Column("channel", sa.String(length=16), server_default="sms", nullable=False),
        sa.Column("kind", sa.String(length=50), nullable=False),
        sa.Column("language", sa.String(length=8), server_default="en", nullable=False),
        sa.Column(
            "status", sa.String(length=20), server_default="queued", nullable=False
        ),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="3", nullable=False),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("claim_token", sa.String(length=64), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claim_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_message_id", sa.String(length=160), nullable=True),
        sa.Column("last_error_code", sa.String(length=64), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "attempt_count >= 0 AND attempt_count <= max_attempts",
            name=op.f("ck_booking_notifications_valid_attempt_count"),
        ),
        sa.CheckConstraint(
            "channel = 'sms'",
            name=op.f("ck_booking_notifications_sms_channel_only"),
        ),
        sa.CheckConstraint(
            "kind IN ('booking_received', 'status_updated', "
            "'synthetic_quote_available', 'booking_rejected', "
            "'synthetic_booking_confirmed')",
            name=op.f("ck_booking_notifications_valid_kind"),
        ),
        sa.CheckConstraint(
            "language IN ('en', 'sw')",
            name=op.f("ck_booking_notifications_valid_language"),
        ),
        sa.CheckConstraint(
            "max_attempts BETWEEN 1 AND 10",
            name=op.f("ck_booking_notifications_valid_max_attempts"),
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'processing', 'accepted', 'delivered', "
            "'failed', 'unknown')",
            name=op.f("ck_booking_notifications_valid_status"),
        ),
        sa.ForeignKeyConstraint(
            ["booking_request_id"],
            ["booking_requests.id"],
            name=op.f(
                "fk_booking_notifications_booking_request_id_booking_requests"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_booking_notifications")),
        sa.UniqueConstraint(
            "idempotency_key",
            name=op.f("uq_booking_notifications_idempotency_key"),
        ),
    )
    op.create_index(
        op.f("ix_booking_notifications_booking_request_id"),
        "booking_notifications",
        ["booking_request_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_booking_notifications_provider_message_id"),
        "booking_notifications",
        ["provider_message_id"],
        unique=False,
    )
    op.create_index(
        "ix_booking_notifications_outbox",
        "booking_notifications",
        ["status", "next_attempt_at", "claim_expires_at"],
        unique=False,
    )


def downgrade() -> None:
    """Drop the notification outbox."""

    op.drop_index(
        "ix_booking_notifications_outbox", table_name="booking_notifications"
    )
    op.drop_index(
        op.f("ix_booking_notifications_provider_message_id"),
        table_name="booking_notifications",
    )
    op.drop_index(
        op.f("ix_booking_notifications_booking_request_id"),
        table_name="booking_notifications",
    )
    op.drop_table("booking_notifications")
