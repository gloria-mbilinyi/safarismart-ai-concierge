"""Add operator authentication identities.

Revision ID: 20261114_0002
Revises: 20261113_0001
Create Date: 2026-11-14
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261114_0002"
down_revision: str | None = "20261113_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create operator identities and mark synthetic operator organizations."""

    op.add_column(
        "operators",
        sa.Column("is_demo", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.create_table(
        "operator_users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("operator_id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("full_name", sa.String(length=150), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("token_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
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
            "email = lower(email)",
            name=op.f("ck_operator_users_normalized_email"),
        ),
        sa.CheckConstraint(
            "token_version >= 1",
            name=op.f("ck_operator_users_valid_token_version"),
        ),
        sa.ForeignKeyConstraint(
            ["operator_id"],
            ["operators.id"],
            name=op.f("fk_operator_users_operator_id_operators"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_operator_users")),
        sa.UniqueConstraint("email", name=op.f("uq_operator_users_email")),
    )
    op.create_index(
        op.f("ix_operator_users_operator_id"),
        "operator_users",
        ["operator_id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove operator identities and the synthetic-data marker."""

    op.drop_index(op.f("ix_operator_users_operator_id"), table_name="operator_users")
    op.drop_table("operator_users")
    op.drop_column("operators", "is_demo")
