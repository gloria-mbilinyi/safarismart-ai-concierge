"""Transactional booking notification outbox model."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import NotificationStatus, SMSLanguage, SMSNotificationKind
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.booking import BookingRequest


NOTIFICATION_STATUSES = ", ".join(
    f"'{status.value}'" for status in NotificationStatus
)
NOTIFICATION_KINDS = ", ".join(f"'{kind.value}'" for kind in SMSNotificationKind)
SMS_LANGUAGES = ", ".join(f"'{language.value}'" for language in SMSLanguage)


class BookingNotification(TimestampMixin, Base):
    """A booking-scoped SMS event that can be claimed by one worker at a time."""

    __tablename__ = "booking_notifications"
    __table_args__ = (
        CheckConstraint("channel = 'sms'", name="sms_channel_only"),
        CheckConstraint(
            f"kind IN ({NOTIFICATION_KINDS})",
            name="valid_kind",
        ),
        CheckConstraint(
            f"language IN ({SMS_LANGUAGES})",
            name="valid_language",
        ),
        CheckConstraint(
            f"status IN ({NOTIFICATION_STATUSES})",
            name="valid_status",
        ),
        CheckConstraint(
            "attempt_count >= 0 AND attempt_count <= max_attempts",
            name="valid_attempt_count",
        ),
        CheckConstraint(
            "max_attempts BETWEEN 1 AND 10",
            name="valid_max_attempts",
        ),
        Index(
            "ix_booking_notifications_outbox",
            "status",
            "next_attempt_at",
            "claim_expires_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    booking_request_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("booking_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    channel: Mapped[str] = mapped_column(
        String(16), nullable=False, default="sms", server_default="sms"
    )
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    language: Mapped[str] = mapped_column(
        String(8),
        nullable=False,
        default=SMSLanguage.ENGLISH.value,
        server_default=SMSLanguage.ENGLISH.value,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=NotificationStatus.QUEUED.value,
        server_default=NotificationStatus.QUEUED.value,
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(200), nullable=False, unique=True
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    max_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=3, server_default="3"
    )
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    claim_token: Mapped[str | None] = mapped_column(String(64))
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    claim_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider_message_id: Mapped[str | None] = mapped_column(String(160), index=True)
    last_error_code: Mapped[str | None] = mapped_column(String(64))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    booking_request: Mapped[BookingRequest] = relationship(
        back_populates="notifications"
    )
