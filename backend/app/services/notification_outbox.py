"""Transactional SMS outbox scheduling, claiming, retries, and delivery updates."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import re
from uuid import UUID, uuid4

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, joinedload, sessionmaker

from app.integrations.africastalking_sms import SMSDeliveryError
from app.models.booking import BookingRequest
from app.models.enums import (
    BookingStatus,
    NotificationStatus,
    SMSLanguage,
    SMSNotificationKind,
)
from app.models.notification import BookingNotification
from app.services.sms_notifications import (
    SMSNotificationService,
    prepare_booking_sms,
)


CLAIM_LEASE = timedelta(minutes=5)
ERROR_CODE_PATTERN = re.compile(r"[^a-z0-9_]+")


class NotificationNotFoundError(Exception):
    """Raised when no notification matches a provider delivery identifier."""


@dataclass(frozen=True, slots=True)
class NotificationClaim:
    """Opaque ownership proof for one claimed outbox row."""

    notification_id: UUID
    token: str


@dataclass(frozen=True, slots=True)
class NotificationProcessResult:
    """PII-free result returned by one worker iteration."""

    notification_id: UUID
    status: NotificationStatus
    attempt_count: int


def notification_kind_for_status(status: BookingStatus) -> SMSNotificationKind:
    """Select the safest specific template for a workflow transition."""

    return {
        BookingStatus.QUOTED: SMSNotificationKind.SYNTHETIC_QUOTE_AVAILABLE,
        BookingStatus.REJECTED: SMSNotificationKind.BOOKING_REJECTED,
        BookingStatus.CONFIRMED: SMSNotificationKind.SYNTHETIC_BOOKING_CONFIRMED,
    }.get(status, SMSNotificationKind.STATUS_UPDATED)


def notification_idempotency_key(
    booking: BookingRequest,
    kind: SMSNotificationKind,
    language: SMSLanguage,
) -> str:
    """Build a deterministic key for one booking event and language."""

    return (
        f"sms:{booking.booking_reference}:{kind.value}:"
        f"{booking.status}:{language.value}"
    )


def schedule_booking_notification(
    session: Session,
    booking: BookingRequest,
    kind: SMSNotificationKind,
    language: SMSLanguage = SMSLanguage.ENGLISH,
    *,
    max_attempts: int = 3,
    now: datetime | None = None,
) -> tuple[BookingNotification | None, bool]:
    """Add one permitted event to the current transaction without sending it."""

    if prepare_booking_sms(booking, kind, language) is None:
        return None, False
    if not 1 <= max_attempts <= 10:
        raise ValueError("max_attempts must be between 1 and 10")

    key = notification_idempotency_key(booking, kind, language)
    for pending in session.new:
        if (
            isinstance(pending, BookingNotification)
            and pending.idempotency_key == key
        ):
            return pending, False

    existing = session.scalar(
        select(BookingNotification).where(
            BookingNotification.idempotency_key == key
        )
    )
    if existing is not None:
        return existing, False

    notification = BookingNotification(
        booking_request=booking,
        kind=kind.value,
        language=language.value,
        idempotency_key=key,
        max_attempts=max_attempts,
        next_attempt_at=now or datetime.now(UTC),
    )
    session.add(notification)
    return notification, True


def claim_next_notification(
    session: Session,
    *,
    now: datetime | None = None,
) -> NotificationClaim | None:
    """Atomically lease one due event, using SKIP LOCKED on PostgreSQL."""

    claimed_at = now or datetime.now(UTC)
    due_queued = and_(
        BookingNotification.status == NotificationStatus.QUEUED.value,
        BookingNotification.next_attempt_at <= claimed_at,
    )
    expired_claim = and_(
        BookingNotification.status == NotificationStatus.PROCESSING.value,
        BookingNotification.claim_expires_at <= claimed_at,
    )
    statement = (
        select(BookingNotification)
        .where(
            or_(due_queued, expired_claim),
            BookingNotification.attempt_count < BookingNotification.max_attempts,
        )
        .order_by(
            BookingNotification.next_attempt_at.asc(),
            BookingNotification.created_at.asc(),
        )
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    notification = session.scalar(statement)
    if notification is None:
        return None

    token = uuid4().hex
    notification.status = NotificationStatus.PROCESSING.value
    notification.claim_token = token
    notification.claimed_at = claimed_at
    notification.claim_expires_at = claimed_at + CLAIM_LEASE
    notification.attempt_count += 1
    session.commit()
    return NotificationClaim(notification.id, token)


def _load_claimed_notification(
    session: Session,
    claim: NotificationClaim,
) -> BookingNotification | None:
    """Reload a claim only while its ownership token is current."""

    return session.scalar(
        select(BookingNotification)
        .options(joinedload(BookingNotification.booking_request))
        .where(
            BookingNotification.id == claim.notification_id,
            BookingNotification.claim_token == claim.token,
            BookingNotification.status == NotificationStatus.PROCESSING.value,
        )
    )


def _safe_error_code(code: str) -> str:
    """Persist only a controlled diagnostic token, never provider text or PII."""

    normalized = ERROR_CODE_PATTERN.sub("_", code.strip().lower()).strip("_")
    return (normalized or "provider_error")[:64]


def _finish_failure(
    session_factory: sessionmaker[Session],
    claim: NotificationClaim,
    *,
    code: str,
    retryable: bool,
    now: datetime,
) -> NotificationProcessResult:
    """Requeue a transient failure or terminally fail the event."""

    with session_factory() as session:
        notification = _load_claimed_notification(session, claim)
        if notification is None:
            return NotificationProcessResult(
                claim.notification_id,
                NotificationStatus.UNKNOWN,
                0,
            )

        notification.last_error_code = _safe_error_code(code)
        notification.claim_token = None
        notification.claimed_at = None
        notification.claim_expires_at = None
        if retryable and notification.attempt_count < notification.max_attempts:
            delay_seconds = min(60 * (2 ** (notification.attempt_count - 1)), 3600)
            notification.status = NotificationStatus.QUEUED.value
            notification.next_attempt_at = now + timedelta(seconds=delay_seconds)
            final_status = NotificationStatus.QUEUED
        else:
            notification.status = NotificationStatus.FAILED.value
            notification.failed_at = now
            final_status = NotificationStatus.FAILED
        attempt_count = notification.attempt_count
        session.commit()
        return NotificationProcessResult(
            notification.id,
            final_status,
            attempt_count,
        )


def process_next_notification(
    session_factory: sessionmaker[Session],
    service: SMSNotificationService,
    *,
    now: datetime | None = None,
) -> NotificationProcessResult | None:
    """Claim, close the transaction, call SMS, then persist the safe outcome."""

    processed_at = now or datetime.now(UTC)
    with session_factory() as session:
        claim = claim_next_notification(session, now=processed_at)
    if claim is None:
        return None

    with session_factory() as session:
        notification = _load_claimed_notification(session, claim)
        if notification is None:
            return NotificationProcessResult(
                claim.notification_id,
                NotificationStatus.UNKNOWN,
                0,
            )
        prepared = prepare_booking_sms(
            notification.booking_request,
            SMSNotificationKind(notification.kind),
            SMSLanguage(notification.language),
        )

    if prepared is None:
        return _finish_failure(
            session_factory,
            claim,
            code="recipient_not_permitted",
            retryable=False,
            now=processed_at,
        )

    try:
        provider_result = service.send_prepared(prepared)
    except SMSDeliveryError as error:
        return _finish_failure(
            session_factory,
            claim,
            code=error.code,
            retryable=error.retryable,
            now=processed_at,
        )
    except Exception:
        return _finish_failure(
            session_factory,
            claim,
            code="unexpected_provider_error",
            retryable=True,
            now=processed_at,
        )

    with session_factory() as session:
        notification = _load_claimed_notification(session, claim)
        if notification is None:
            return NotificationProcessResult(
                claim.notification_id,
                NotificationStatus.UNKNOWN,
                0,
            )
        notification.status = NotificationStatus.ACCEPTED.value
        notification.provider_message_id = provider_result.message_id
        notification.accepted_at = processed_at
        notification.last_error_code = None
        notification.claim_token = None
        notification.claimed_at = None
        notification.claim_expires_at = None
        attempt_count = notification.attempt_count
        session.commit()
        return NotificationProcessResult(
            notification.id,
            NotificationStatus.ACCEPTED,
            attempt_count,
        )


def record_sms_delivery_status(
    session: Session,
    provider_message_id: str,
    provider_status: str,
    *,
    now: datetime | None = None,
) -> BookingNotification:
    """Record a provider delivery update without treating acceptance as delivery."""

    notification = session.scalar(
        select(BookingNotification)
        .where(BookingNotification.provider_message_id == provider_message_id)
        .order_by(BookingNotification.created_at.desc())
        .limit(1)
    )
    if notification is None:
        raise NotificationNotFoundError

    recorded_at = now or datetime.now(UTC)
    normalized = provider_status.strip().lower()
    if normalized in {"success", "delivered"}:
        notification.status = NotificationStatus.DELIVERED.value
        notification.delivered_at = recorded_at
        notification.last_error_code = None
    elif normalized in {"failed", "rejected", "undeliverable"}:
        notification.status = NotificationStatus.FAILED.value
        notification.failed_at = recorded_at
        notification.last_error_code = "provider_delivery_failed"
    else:
        notification.status = NotificationStatus.UNKNOWN.value
        notification.last_error_code = "provider_delivery_unknown"
    session.commit()
    session.refresh(notification)
    return notification
