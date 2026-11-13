"""Database model and constraint tests."""

from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import BookingRequest, BookingStatusHistory, Destination, Operator
from app.models.enums import BookingStatus, DestinationCategory, StatusActorType


def create_destination(session: Session) -> Destination:
    """Persist the minimum operator and destination graph used by tests."""

    operator = Operator(name="Test Safaris", slug="test-safaris")
    destination = Destination(
        operator=operator,
        name="Test Reserve",
        slug="test-reserve",
        country="Tanzania",
        region="Arusha",
        category=DestinationCategory.NATIONAL_PARK.value,
        description="A destination used only by the isolated test database.",
    )
    session.add(destination)
    session.commit()
    return destination


def test_database_persists_booking_relationships(db_session: Session) -> None:
    """Models should persist their relationships and database timestamps."""

    destination = create_destination(db_session)
    booking = BookingRequest(
        booking_reference="SS-TEST-0001",
        idempotency_key="database-test-0001",
        destination=destination,
        operator=destination.operator,
        travel_start_date=date(2027, 1, 10),
        travel_end_date=date(2027, 1, 15),
        party_size=2,
        customer_name="Database Test Traveller",
        customer_email="traveller@example.com",
        customer_contact_preference="email",
        customer_consent=True,
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
    db_session.add(booking)
    db_session.commit()
    db_session.refresh(booking)

    assert booking.id is not None
    assert booking.created_at is not None
    assert booking.destination.name == "Test Reserve"
    assert booking.operator is not None
    assert booking.status_history[0].to_status == "pending_availability"


def test_booking_reference_must_be_unique(db_session: Session) -> None:
    """Database constraints should reject duplicate public references."""

    destination = create_destination(db_session)
    common_fields = {
        "booking_reference": "SS-TEST-UNIQUE",
        "destination_id": destination.id,
        "travel_start_date": date(2027, 2, 1),
        "travel_end_date": date(2027, 2, 2),
        "party_size": 1,
        "customer_name": "Test Traveller",
        "customer_email": "traveller@example.com",
        "customer_contact_preference": "email",
        "customer_consent": True,
    }
    db_session.add_all(
        [
            BookingRequest(idempotency_key="unique-key-1", **common_fields),
            BookingRequest(idempotency_key="unique-key-2", **common_fields),
        ]
    )

    with pytest.raises(IntegrityError):
        db_session.commit()


@pytest.mark.parametrize(
    ("party_size", "customer_consent"),
    [(0, True), (51, True), (2, False)],
)
def test_booking_database_constraints_reject_invalid_requests(
    db_session: Session,
    party_size: int,
    customer_consent: bool,
) -> None:
    """Critical booking invariants should also be protected by the database."""

    destination = create_destination(db_session)
    booking = BookingRequest(
        booking_reference=f"SS-INVALID-{party_size}-{customer_consent}",
        idempotency_key=f"invalid-{party_size}-{customer_consent}",
        destination_id=destination.id,
        travel_start_date=date(2027, 3, 1),
        travel_end_date=date(2027, 3, 3),
        party_size=party_size,
        customer_name="Invalid Test Traveller",
        customer_phone="+255700000000",
        customer_contact_preference="phone",
        customer_consent=customer_consent,
    )
    db_session.add(booking)

    with pytest.raises(IntegrityError):
        db_session.commit()
