"""Tourism destination persistence model."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    false,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import DestinationCategory
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.booking import BookingRequest
    from app.models.operator import Operator


DESTINATION_CATEGORIES = ", ".join(
    f"'{category.value}'" for category in DestinationCategory
)


class Destination(TimestampMixin, Base):
    """A curated tourism destination; it does not imply live availability."""

    __tablename__ = "destinations"
    __table_args__ = (
        CheckConstraint(
            f"category IN ({DESTINATION_CATEGORIES})",
            name="valid_category",
        ),
        UniqueConstraint("name", "country", name="uq_destinations_name_country"),
        Index("ix_destinations_catalog_filters", "is_active", "category", "region"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    operator_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("operators.id", ondelete="SET NULL"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    country: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="Tanzania",
        server_default="Tanzania",
    )
    region: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    is_featured: Mapped[bool] = mapped_column(
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

    operator: Mapped[Operator | None] = relationship(back_populates="destinations")
    booking_requests: Mapped[list[BookingRequest]] = relationship(
        back_populates="destination"
    )
