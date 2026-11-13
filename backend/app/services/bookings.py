"""Booking request submission service."""

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.booking import BookingRequest, BookingStatusHistory
from app.models.destination import Destination
from app.models.enums import BookingStatus, StatusActorType
from app.schemas.booking import BookingRequestCreate


class DestinationUnavailableError(Exception):
    """Raised when a requested public destination cannot accept submissions."""


class IdempotencyConflictError(Exception):
    """Raised when an idempotency key is reused for different input."""


def generate_booking_reference() -> str:
    """Generate a non-sequential public booking reference."""

    return f"SS-{uuid4().hex[:12].upper()}"


def get_booking_by_idempotency_key(
    session: Session, idempotency_key: str
) -> BookingRequest | None:
    """Find a previously submitted booking by its idempotency key."""

    return session.scalar(
        select(BookingRequest).where(
            BookingRequest.idempotency_key == idempotency_key
        )
    )


def booking_matches_submission(
    booking: BookingRequest, submission: BookingRequestCreate
) -> bool:
    """Check whether a replay carries the same normalized booking input."""

    return all(
        (
            booking.destination_id == submission.destination_id,
            booking.travel_start_date == submission.travel_start_date,
            booking.travel_end_date == submission.travel_end_date,
            booking.party_size == submission.party_size,
            booking.customer_name == submission.customer_name,
            booking.customer_email
            == (str(submission.customer_email) if submission.customer_email else None),
            booking.customer_phone == submission.customer_phone,
            booking.customer_contact_preference
            == submission.customer_contact_preference,
            booking.customer_consent is submission.customer_consent,
            booking.special_requests == submission.special_requests,
        )
    )


def resolve_existing_submission(
    booking: BookingRequest, submission: BookingRequestCreate
) -> tuple[BookingRequest, bool]:
    """Return an identical replay or reject conflicting idempotent input."""

    if not booking_matches_submission(booking, submission):
        raise IdempotencyConflictError
    return booking, False


def create_booking_request(
    session: Session,
    submission: BookingRequestCreate,
    idempotency_key: str,
) -> tuple[BookingRequest, bool]:
    """Persist one pending booking request and its initial audit event."""

    existing_booking = get_booking_by_idempotency_key(session, idempotency_key)
    if existing_booking is not None:
        return resolve_existing_submission(existing_booking, submission)

    destination = session.scalar(
        select(Destination).where(
            Destination.id == submission.destination_id,
            Destination.is_active.is_(True),
        )
    )
    if destination is None:
        raise DestinationUnavailableError

    booking = BookingRequest(
        booking_reference=generate_booking_reference(),
        idempotency_key=idempotency_key,
        destination_id=destination.id,
        operator_id=destination.operator_id,
        travel_start_date=submission.travel_start_date,
        travel_end_date=submission.travel_end_date,
        party_size=submission.party_size,
        customer_name=submission.customer_name,
        customer_email=(
            str(submission.customer_email) if submission.customer_email else None
        ),
        customer_phone=submission.customer_phone,
        customer_contact_preference=submission.customer_contact_preference,
        customer_consent=submission.customer_consent,
        special_requests=submission.special_requests,
        status=BookingStatus.PENDING_AVAILABILITY.value,
    )
    booking.status_history.append(
        BookingStatusHistory(
            from_status=None,
            to_status=BookingStatus.PENDING_AVAILABILITY.value,
            actor_type=StatusActorType.CUSTOMER.value,
            reason="Booking request submitted",
        )
    )
    session.add(booking)

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        concurrent_booking = get_booking_by_idempotency_key(session, idempotency_key)
        if concurrent_booking is not None:
            return resolve_existing_submission(concurrent_booking, submission)
        raise

    session.refresh(booking)
    return booking, True
