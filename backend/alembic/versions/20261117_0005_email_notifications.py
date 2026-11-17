"""Add email notifications and customer language.

Revision ID: 20261117_0005
Revises: 20261115_0004
Create Date: 2026-11-17
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261117_0005"
down_revision: str | None = "20261115_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Allow email outbox rows and remember the customer's language."""

    with op.batch_alter_table("booking_requests") as batch_op:
        batch_op.add_column(
            sa.Column(
                "customer_language",
                sa.String(length=8),
                server_default="en",
                nullable=False,
            )
        )
        batch_op.create_check_constraint(
            op.f("ck_booking_requests_valid_customer_language"),
            "customer_language IN ('en', 'sw')",
        )

    with op.batch_alter_table("booking_notifications") as batch_op:
        batch_op.drop_constraint(
            op.f("ck_booking_notifications_sms_channel_only"),
            type_="check",
        )
        batch_op.create_check_constraint(
            op.f("ck_booking_notifications_valid_channel"),
            "channel IN ('email', 'sms')",
        )
        batch_op.alter_column("channel", server_default=None)


def downgrade() -> None:
    """Return the outbox to SMS-only storage."""

    op.execute("DELETE FROM booking_notifications WHERE channel = 'email'")
    with op.batch_alter_table("booking_notifications") as batch_op:
        batch_op.drop_constraint(
            op.f("ck_booking_notifications_valid_channel"),
            type_="check",
        )
        batch_op.create_check_constraint(
            op.f("ck_booking_notifications_sms_channel_only"),
            "channel = 'sms'",
        )
        batch_op.alter_column("channel", server_default="sms")

    with op.batch_alter_table("booking_requests") as batch_op:
        batch_op.drop_constraint(
            op.f("ck_booking_requests_valid_customer_language"),
            type_="check",
        )
        batch_op.drop_column("customer_language")
