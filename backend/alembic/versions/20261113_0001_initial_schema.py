"""Create destination and booking tables.

Revision ID: 20261113_0001
Revises: None
Create Date: 2026-11-13
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261113_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the initial application schema."""

    op.create_table(
        "operators",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("contact_email", sa.String(length=320), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_operators")),
        sa.UniqueConstraint("slug", name=op.f("uq_operators_slug")),
    )

    op.create_table(
        "destinations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("operator_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column(
            "country",
            sa.String(length=100),
            server_default="Tanzania",
            nullable=False,
        ),
        sa.Column("region", sa.String(length=120), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "is_featured", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
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
            "category IN ('beach', 'conservation_area', 'mountain', 'national_park')",
            name=op.f("ck_destinations_valid_category"),
        ),
        sa.ForeignKeyConstraint(
            ["operator_id"],
            ["operators.id"],
            name=op.f("fk_destinations_operator_id_operators"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_destinations")),
        sa.UniqueConstraint(
            "name", "country", name="uq_destinations_name_country"
        ),
        sa.UniqueConstraint("slug", name=op.f("uq_destinations_slug")),
    )
    op.create_index(
        "ix_destinations_catalog_filters",
        "destinations",
        ["is_active", "category", "region"],
        unique=False,
    )
    op.create_index(
        op.f("ix_destinations_operator_id"),
        "destinations",
        ["operator_id"],
        unique=False,
    )

    op.create_table(
        "booking_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("booking_reference", sa.String(length=32), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("destination_id", sa.Uuid(), nullable=False),
        sa.Column("operator_id", sa.Uuid(), nullable=True),
        sa.Column("travel_start_date", sa.Date(), nullable=False),
        sa.Column("travel_end_date", sa.Date(), nullable=False),
        sa.Column("party_size", sa.Integer(), nullable=False),
        sa.Column("customer_name", sa.String(length=150), nullable=False),
        sa.Column("customer_email", sa.String(length=320), nullable=True),
        sa.Column("customer_phone", sa.String(length=32), nullable=True),
        sa.Column(
            "customer_contact_preference", sa.String(length=16), nullable=False
        ),
        sa.Column("customer_consent", sa.Boolean(), nullable=False),
        sa.Column(
            "consent_recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("special_requests", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default="pending_availability",
            nullable=False,
        ),
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
            "customer_consent", name=op.f("ck_booking_requests_customer_consent_required")
        ),
        sa.CheckConstraint(
            "customer_contact_preference IN ('email', 'phone')",
            name=op.f("ck_booking_requests_valid_contact_preference"),
        ),
        sa.CheckConstraint(
            "party_size BETWEEN 1 AND 50",
            name=op.f("ck_booking_requests_valid_party_size"),
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'pending_availability', 'quoted', "
            "'pending_confirmation', 'confirmed', 'rejected', 'expired', 'cancelled')",
            name=op.f("ck_booking_requests_valid_status"),
        ),
        sa.CheckConstraint(
            "travel_end_date >= travel_start_date",
            name=op.f("ck_booking_requests_valid_dates"),
        ),
        sa.ForeignKeyConstraint(
            ["destination_id"],
            ["destinations.id"],
            name=op.f("fk_booking_requests_destination_id_destinations"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["operator_id"],
            ["operators.id"],
            name=op.f("fk_booking_requests_operator_id_operators"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_booking_requests")),
        sa.UniqueConstraint(
            "booking_reference", name=op.f("uq_booking_requests_booking_reference")
        ),
        sa.UniqueConstraint(
            "idempotency_key", name=op.f("uq_booking_requests_idempotency_key")
        ),
    )
    op.create_index(
        op.f("ix_booking_requests_destination_id"),
        "booking_requests",
        ["destination_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_booking_requests_operator_id"),
        "booking_requests",
        ["operator_id"],
        unique=False,
    )

    op.create_table(
        "booking_status_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("booking_request_id", sa.Uuid(), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("actor_type", sa.String(length=20), nullable=False),
        sa.Column("actor_reference", sa.String(length=120), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "actor_type IN ('customer', 'operator', 'system')",
            name=op.f("ck_booking_status_history_valid_actor_type"),
        ),
        sa.CheckConstraint(
            "from_status IS NULL OR from_status IN ('draft', 'pending_availability', "
            "'quoted', 'pending_confirmation', 'confirmed', 'rejected', 'expired', "
            "'cancelled')",
            name=op.f("ck_booking_status_history_valid_from_status"),
        ),
        sa.CheckConstraint(
            "to_status IN ('draft', 'pending_availability', 'quoted', "
            "'pending_confirmation', 'confirmed', 'rejected', 'expired', 'cancelled')",
            name=op.f("ck_booking_status_history_valid_to_status"),
        ),
        sa.ForeignKeyConstraint(
            ["booking_request_id"],
            ["booking_requests.id"],
            name=op.f(
                "fk_booking_status_history_booking_request_id_booking_requests"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_booking_status_history")),
    )
    op.create_index(
        "ix_booking_status_history_booking_occurred",
        "booking_status_history",
        ["booking_request_id", "occurred_at"],
        unique=False,
    )


def downgrade() -> None:
    """Drop the initial application schema."""

    op.drop_index(
        "ix_booking_status_history_booking_occurred",
        table_name="booking_status_history",
    )
    op.drop_table("booking_status_history")
    op.drop_index(
        op.f("ix_booking_requests_operator_id"), table_name="booking_requests"
    )
    op.drop_index(
        op.f("ix_booking_requests_destination_id"), table_name="booking_requests"
    )
    op.drop_table("booking_requests")
    op.drop_index(op.f("ix_destinations_operator_id"), table_name="destinations")
    op.drop_index("ix_destinations_catalog_filters", table_name="destinations")
    op.drop_table("destinations")
    op.drop_table("operators")
