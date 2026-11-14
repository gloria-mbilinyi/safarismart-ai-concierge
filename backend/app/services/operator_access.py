"""Organization-scoped protected resource lookup."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.booking import BookingRequest


class OperatorResourceNotFoundError(Exception):
    """Raised for both missing and cross-organization protected resources."""


def get_operator_booking(
    session: Session,
    *,
    booking_reference: str,
    operator_id: UUID,
) -> BookingRequest:
    """Load a booking only when it belongs to the authenticated organization."""

    booking = session.execute(
        select(BookingRequest)
        .options(
            joinedload(BookingRequest.destination),
            joinedload(BookingRequest.quote),
            joinedload(BookingRequest.status_history),
        )
        .where(
            BookingRequest.booking_reference == booking_reference,
            BookingRequest.operator_id == operator_id,
        )
    ).unique().scalar_one_or_none()
    if booking is None:
        raise OperatorResourceNotFoundError
    return booking
