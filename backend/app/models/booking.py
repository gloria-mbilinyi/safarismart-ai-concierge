"""Booking request and status audit persistence models."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import BookingStatus, StatusActorType
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.destination import Destination
    from app.models.operator import Operator
    from app.models.quote import BookingQuote


BOOKING_STATUSES = ", ".join(f"'{status.value}'" for status in BookingStatus)
STATUS_ACTOR_TYPES = ", ".join(f"'{actor.value}'" for actor in StatusActorType)


class BookingRequest(TimestampMixin, Base):
    """A traveller's request for an operator-reviewed booking."""

    __tablename__ = "booking_requests"
    __table_args__ = (
        CheckConstraint("travel_end_date >= travel_start_date", name="valid_dates"),
        CheckConstraint("party_size BETWEEN 1 AND 50", name="valid_party_size"),
        CheckConstraint("customer_consent", name="customer_consent_required"),
        CheckConstraint(
            "customer_contact_preference IN ('email', 'phone')",
            name="valid_contact_preference",
        ),
        CheckConstraint(f"status IN ({BOOKING_STATUSES})", name="valid_status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    booking_reference: Mapped[str] = mapped_column(
        String(32), nullable=False, unique=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    destination_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("destinations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    operator_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("operators.id", ondelete="SET NULL"),
        index=True,
    )
    travel_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    travel_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    party_size: Mapped[int] = mapped_column(Integer, nullable=False)
    customer_name: Mapped[str] = mapped_column(String(150), nullable=False)
    customer_email: Mapped[str | None] = mapped_column(String(320))
    customer_phone: Mapped[str | None] = mapped_column(String(32))
    customer_contact_preference: Mapped[str] = mapped_column(String(16), nullable=False)
    customer_consent: Mapped[bool] = mapped_column(Boolean, nullable=False)
    consent_recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    special_requests: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=BookingStatus.PENDING_AVAILABILITY.value,
        server_default=BookingStatus.PENDING_AVAILABILITY.value,
    )

    destination: Mapped[Destination] = relationship(back_populates="booking_requests")
    operator: Mapped[Operator | None] = relationship(back_populates="booking_requests")
    status_history: Mapped[list[BookingStatusHistory]] = relationship(
        back_populates="booking_request",
        cascade="all, delete-orphan",
        order_by="BookingStatusHistory.occurred_at",
    )
    quote: Mapped[BookingQuote | None] = relationship(
        back_populates="booking_request",
        cascade="all, delete-orphan",
        uselist=False,
    )


class BookingStatusHistory(Base):
    """Immutable audit record for a booking state transition."""

    __tablename__ = "booking_status_history"
    __table_args__ = (
        CheckConstraint(
            f"from_status IS NULL OR from_status IN ({BOOKING_STATUSES})",
            name="valid_from_status",
        ),
        CheckConstraint(f"to_status IN ({BOOKING_STATUSES})", name="valid_to_status"),
        CheckConstraint(
            f"actor_type IN ({STATUS_ACTOR_TYPES})",
            name="valid_actor_type",
        ),
        Index(
            "ix_booking_status_history_booking_occurred",
            "booking_request_id",
            "occurred_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    booking_request_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("booking_requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    from_status: Mapped[str | None] = mapped_column(String(32))
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_reference: Mapped[str | None] = mapped_column(String(120))
    reason: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )

    booking_request: Mapped[BookingRequest] = relationship(
        back_populates="status_history"
    )
