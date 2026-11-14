"""Add synthetic booking quotes.

Revision ID: 20261114_0003
Revises: 20261114_0002
Create Date: 2026-11-14
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261114_0003"
down_revision: str | None = "20261114_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the one-to-one synthetic quote table."""

    op.create_table(
        "booking_quotes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("booking_request_id", sa.Uuid(), nullable=False),
        sa.Column("operator_id", sa.Uuid(), nullable=False),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("terms", sa.Text(), nullable=True),
        sa.Column("is_demo", sa.Boolean(), server_default=sa.true(), nullable=False),
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
            "amount_minor > 0",
            name=op.f("ck_booking_quotes_positive_amount"),
        ),
        sa.CheckConstraint(
            "length(currency) = 3 AND currency = upper(currency)",
            name=op.f("ck_booking_quotes_valid_currency"),
        ),
        sa.ForeignKeyConstraint(
            ["booking_request_id"],
            ["booking_requests.id"],
            name=op.f("fk_booking_quotes_booking_request_id_booking_requests"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["operator_id"],
            ["operators.id"],
            name=op.f("fk_booking_quotes_operator_id_operators"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_booking_quotes")),
        sa.UniqueConstraint(
            "booking_request_id",
            name=op.f("uq_booking_quotes_booking_request_id"),
        ),
    )
    op.create_index(
        op.f("ix_booking_quotes_operator_id"),
        "booking_quotes",
        ["operator_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop synthetic booking quotes."""

    op.drop_index(op.f("ix_booking_quotes_operator_id"), table_name="booking_quotes")
    op.drop_table("booking_quotes")
