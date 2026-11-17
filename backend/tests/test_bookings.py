"""Public booking request submission tests."""

from datetime import date, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.booking import BookingRequest, BookingStatusHistory
from app.models.destination import Destination


def valid_booking_payload(destination_id: UUID) -> dict[str, Any]:
    """Return valid future-dated booking input for endpoint tests."""

    start_date = date.today() + timedelta(days=30)
    return {
        "destination_id": str(destination_id),
        "travel_start_date": start_date.isoformat(),
        "travel_end_date": (start_date + timedelta(days=5)).isoformat(),
        "party_size": 2,
        "customer_name": "Amina Traveller",
        "customer_email": "amina@example.com",
        "customer_phone": "+255712345678",
        "customer_contact_preference": "email",
        "customer_language": "en",
        "customer_consent": True,
        "special_requests": "Interested in a nature-focused itinerary.",
    }


def test_create_booking_request_persists_pending_request_without_exposing_contact(
    client: TestClient,
    db_session: Session,
    seeded_destinations: list[Destination],
) -> None:
    """A valid submission should be pending, audited, and privacy-safe."""

    destination = seeded_destinations[0]
    response = client.post(
        "/api/v1/bookings",
        headers={"Idempotency-Key": "booking-create-0001"},
        json=valid_booking_payload(destination.id),
    )

    assert response.status_code == 201
    payload = response.json()
    assert set(payload) == {
        "booking_reference",
        "status",
        "destination_id",
        "travel_start_date",
        "travel_end_date",
        "party_size",
        "created_at",
            "notification",
    }
    assert payload["booking_reference"].startswith("SS-")
    assert payload["status"] == "pending_availability"
    assert payload["destination_id"] == str(destination.id)
    assert payload["notification"] == {
        "channel": "email",
        "state": "unavailable",
        "mode": "unconfigured",
    }
    assert "customer_email" not in payload
    assert "customer_phone" not in payload
    assert "customer_name" not in payload

    booking = db_session.scalar(select(BookingRequest))
    assert booking is not None
    assert booking.status == "pending_availability"
    assert booking.status != "confirmed"
    assert booking.customer_email == "amina@example.com"
    assert booking.customer_language == "en"
    assert len(booking.status_history) == 1
    assert booking.status_history[0].from_status is None
    assert booking.status_history[0].to_status == "pending_availability"


def test_identical_idempotent_replay_returns_original_booking(
    client: TestClient,
    db_session: Session,
    seeded_destinations: list[Destination],
) -> None:
    """Repeating the same key and body should not create another booking."""

    payload = valid_booking_payload(seeded_destinations[0].id)
    headers = {"Idempotency-Key": "booking-replay-0001"}

    first_response = client.post("/api/v1/bookings", headers=headers, json=payload)
    replay_response = client.post("/api/v1/bookings", headers=headers, json=payload)

    assert first_response.status_code == 201
    assert replay_response.status_code == 200
    assert (
        replay_response.json()["booking_reference"]
        == first_response.json()["booking_reference"]
    )
    assert db_session.scalar(select(func.count()).select_from(BookingRequest)) == 1
    assert (
        db_session.scalar(select(func.count()).select_from(BookingStatusHistory)) == 1
    )


def test_idempotency_key_reuse_with_different_input_is_rejected(
    client: TestClient,
    db_session: Session,
    seeded_destinations: list[Destination],
) -> None:
    """A key cannot silently alias two distinct booking requests."""

    first_payload = valid_booking_payload(seeded_destinations[0].id)
    conflicting_payload = {**first_payload, "party_size": 3}
    headers = {"Idempotency-Key": "booking-conflict-0001"}

    first_response = client.post(
        "/api/v1/bookings", headers=headers, json=first_payload
    )
    conflict_response = client.post(
        "/api/v1/bookings", headers=headers, json=conflicting_payload
    )

    assert first_response.status_code == 201
    assert conflict_response.status_code == 409
    assert conflict_response.json() == {
        "detail": "Idempotency key was already used for a different request"
    }
    assert db_session.scalar(select(func.count()).select_from(BookingRequest)) == 1


def test_booking_rejects_missing_or_inactive_destination(
    client: TestClient,
    db_session: Session,
    seeded_destinations: list[Destination],
) -> None:
    """Submissions must reference an active catalog destination."""

    inactive_destination = seeded_destinations[0]
    inactive_destination.is_active = False
    db_session.commit()

    inactive_response = client.post(
        "/api/v1/bookings",
        headers={"Idempotency-Key": "inactive-destination"},
        json=valid_booking_payload(inactive_destination.id),
    )
    missing_response = client.post(
        "/api/v1/bookings",
        headers={"Idempotency-Key": "missing-destination"},
        json=valid_booking_payload(uuid4()),
    )

    assert inactive_response.status_code == 404
    assert inactive_response.json() == {"detail": "Destination not found"}
    assert missing_response.status_code == 404
    assert missing_response.json() == {"detail": "Destination not found"}
    assert db_session.scalar(select(func.count()).select_from(BookingRequest)) == 0


@pytest.mark.parametrize(
    "payload_update",
    [
        {
            "travel_start_date": (date.today() - timedelta(days=1)).isoformat(),
        },
        {
            "travel_start_date": (date.today() + timedelta(days=10)).isoformat(),
            "travel_end_date": (date.today() + timedelta(days=9)).isoformat(),
        },
        {"party_size": 0},
        {"party_size": 51},
        {"customer_consent": False},
        {"customer_email": None, "customer_contact_preference": "email"},
        {"customer_email": "not-an-email"},
        {"customer_phone": "0712345678", "customer_contact_preference": "phone"},
        {"customer_language": "fr"},
    ],
)
def test_booking_validation_rejects_invalid_input(
    client: TestClient,
    db_session: Session,
    seeded_destinations: list[Destination],
    payload_update: dict[str, Any],
) -> None:
    """Invalid dates, party sizes, contact details, and consent should fail."""

    payload = {**valid_booking_payload(seeded_destinations[0].id), **payload_update}

    response = client.post(
        "/api/v1/bookings",
        headers={"Idempotency-Key": "validation-test-0001"},
        json=payload,
    )

    assert response.status_code == 422
    assert db_session.scalar(select(func.count()).select_from(BookingRequest)) == 0


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Idempotency-Key": "short"},
        {"Idempotency-Key": "contains spaces"},
    ],
)
def test_booking_requires_valid_idempotency_key(
    client: TestClient,
    db_session: Session,
    seeded_destinations: list[Destination],
    headers: dict[str, str],
) -> None:
    """Missing or malformed idempotency headers should fail validation."""

    response = client.post(
        "/api/v1/bookings",
        headers=headers,
        json=valid_booking_payload(seeded_destinations[0].id),
    )

    assert response.status_code == 422
    assert db_session.scalar(select(func.count()).select_from(BookingRequest)) == 0


def test_booking_detail_is_not_publicly_exposed(client: TestClient) -> None:
    """No unauthenticated booking detail route should exist in this phase."""

    response = client.get("/api/v1/bookings/SS-NOT-PUBLIC")

    assert response.status_code == 404


def test_public_booking_submission_is_rate_limited_per_client(
    client: TestClient,
    db_session: Session,
    seeded_destinations: list[Destination],
) -> None:
    """The single-instance MVP should bound anonymous booking bursts."""

    payload = valid_booking_payload(seeded_destinations[0].id)
    responses = [
        client.post(
            "/api/v1/bookings",
            headers={"Idempotency-Key": f"rate-limit-{index:04d}"},
            json=payload,
        )
        for index in range(6)
    ]

    assert [response.status_code for response in responses[:5]] == [201] * 5
    assert responses[5].status_code == 429
    assert responses[5].headers["Retry-After"] == "60"
    assert db_session.scalar(select(func.count()).select_from(BookingRequest)) == 5
