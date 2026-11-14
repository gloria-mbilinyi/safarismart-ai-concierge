"""Authenticated operator user persistence model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Uuid,
    func,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.operator import Operator


class OperatorUser(TimestampMixin, Base):
    """A password-authenticated identity belonging to one operator organization."""

    __tablename__ = "operator_users"
    __table_args__ = (
        CheckConstraint("email = lower(email)", name="normalized_email"),
        CheckConstraint("token_version >= 1", name="valid_token_version"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    operator_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("operators.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )
    token_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    operator: Mapped[Operator] = relationship(back_populates="users")
