"""Tour operator persistence model."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, String, Text, Uuid, false, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.booking import BookingRequest
    from app.models.destination import Destination
    from app.models.operator_user import OperatorUser


class Operator(TimestampMixin, Base):
    """An operator that can manage destination inventory and booking decisions."""

    __tablename__ = "operators"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    contact_email: Mapped[str | None] = mapped_column(String(320))
    is_demo: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )

    destinations: Mapped[list[Destination]] = relationship(back_populates="operator")
    booking_requests: Mapped[list[BookingRequest]] = relationship(
        back_populates="operator"
    )
    users: Mapped[list[OperatorUser]] = relationship(
        back_populates="operator",
        cascade="all, delete-orphan",
    )
