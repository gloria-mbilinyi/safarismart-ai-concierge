"""Synthetic destination assignment and protected booking management tests."""

from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BookingQuote, BookingRequest, Destination, Operator
from app.models.enums import BookingStatus, DestinationCategory, StatusActorType
from app.models.operator_user import OperatorUser
from app.seed.destinations import seed_destinations
from app.services.booking_workflow import WorkflowActor, transition_booking
from app.services.demo_assignment import (
    DemoAssignmentError,
    assign_demo_destinations,
)


def booking_payload(destination_id: object) -> dict[str, Any]:
    """Return valid synthetic booking input for management tests."""

    start_date = date.today() + timedelta(days=45)
    return {
        "destination_id": str(destination_id),
        "travel_start_date": start_date.isoformat(),
        "travel_end_date": (start_date + timedelta(days=4)).isoformat(),
        "party_size": 3,
        "customer_name": "Synthetic Management Customer",
        "customer_email": "management@example.com",
        "customer_phone": "+255713456789",
        "customer_contact_preference": "email",
        "customer_consent": True,
        "special_requests": "Synthetic test request only.",
    }


@pytest.fixture
def assigned_destinations(
    db_session: Session,
    demo_operator_user: OperatorUser,
) -> list[Destination]:
    """Seed and safely assign the curated catalog to the demo operator."""

    seed_destinations(db_session)
    assign_demo_destinations(db_session, demo_operator_user.operator)
    return list(
        db_session.scalars(
            select(Destination)
            .where(Destination.operator_id == demo_operator_user.operator_id)
            .order_by(Destination.name)
        ).all()
    )


@pytest.fixture
def assigned_booking(
    auth_client: TestClient,
    db_session: Session,
    assigned_destinations: list[Destination],
) -> BookingRequest:
    """Submit one public request for a destination assigned to the demo operator."""

    response = auth_client.post(
        "/api/v1/bookings",
        headers={"Idempotency-Key": f"management-{uuid4().hex}"},
        json=booking_payload(assigned_destinations[0].id),
    )
    assert response.status_code == 201, response.text
    db_session.expire_all()
    booking = db_session.scalar(
        select(BookingRequest).where(
            BookingRequest.booking_reference == response.json()["booking_reference"]
        )
    )
    assert booking is not None
    return booking


def test_demo_destination_assignment_is_safe_and_repeatable(
    db_session: Session,
    demo_operator_user: OperatorUser,
) -> None:
    """Only unassigned seed records can be attached to a synthetic operator."""

    seed_destinations(db_session)

    assert assign_demo_destinations(db_session, demo_operator_user.operator) == 5
    assert assign_demo_destinations(db_session, demo_operator_user.operator) == 0

    real_operator = Operator(name="Unverified Real Operator", slug="unverified-real")
    db_session.add(real_operator)
    db_session.commit()
    with pytest.raises(DemoAssignmentError):
        assign_demo_destinations(db_session, real_operator)


def test_operator_can_list_and_view_only_assigned_booking_information(
    auth_client: TestClient,
    operator_headers: dict[str, str],
    assigned_booking: BookingRequest,
) -> None:
    """Queue rows omit PII while assigned detail exposes operational contact data."""

    list_response = auth_client.get(
        "/api/v1/operator/bookings",
        headers=operator_headers,
    )
    detail_response = auth_client.get(
        f"/api/v1/operator/bookings/{assigned_booking.booking_reference}",
        headers=operator_headers,
    )

    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1
    assert "customer_email" not in list_response.json()["items"][0]
    assert detail_response.status_code == 200
    assert detail_response.json()["customer_email"] == "management@example.com"
    assert detail_response.json()["customer_phone"] == "+255713456789"
    assert "real-world reservation has been made" in detail_response.json()[
        "reservation_disclaimer"
    ]


def test_operator_booking_endpoints_require_authentication(
    auth_client: TestClient,
    assigned_booking: BookingRequest,
) -> None:
    """Queue, detail, and actions are unavailable without bearer authentication."""

    assert auth_client.get("/api/v1/operator/bookings").status_code == 401
    assert auth_client.get(
        f"/api/v1/operator/bookings/{assigned_booking.booking_reference}"
    ).status_code == 401
    assert auth_client.post(
        f"/api/v1/operator/bookings/{assigned_booking.booking_reference}/reject",
        json={"reason": "Unauthorized attempt"},
    ).status_code == 401


def test_cross_organization_booking_is_hidden(
    auth_client: TestClient,
    db_session: Session,
    operator_headers: dict[str, str],
) -> None:
    """An authenticated operator receives 404 for another organization's booking."""

    other_operator = Operator(
        name="Other Synthetic Organization",
        slug=f"other-org-{uuid4().hex[:8]}",
        is_demo=True,
    )
    destination = Destination(
        operator=other_operator,
        name=f"Other Synthetic Destination {uuid4().hex[:8]}",
        slug=f"other-destination-{uuid4().hex[:8]}",
        country="Tanzania",
        region="Synthetic Region",
        category=DestinationCategory.NATIONAL_PARK.value,
        description="Synthetic cross-organization test destination.",
    )
    start_date = date.today() + timedelta(days=60)
    booking = BookingRequest(
        booking_reference=f"SS-OTHER-{uuid4().hex[:8].upper()}",
        idempotency_key=f"other-{uuid4().hex}",
        destination=destination,
        operator=other_operator,
        travel_start_date=start_date,
        travel_end_date=start_date + timedelta(days=2),
        party_size=2,
        customer_name="Other Organization Customer",
        customer_email="other@example.test",
        customer_contact_preference="email",
        customer_consent=True,
    )
    db_session.add(booking)
    db_session.commit()

    response = auth_client.get(
        f"/api/v1/operator/bookings/{booking.booking_reference}",
        headers=operator_headers,
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Booking not found"}


def test_demo_operator_can_quote_pending_booking(
    auth_client: TestClient,
    db_session: Session,
    operator_headers: dict[str, str],
    assigned_booking: BookingRequest,
) -> None:
    """A synthetic quote should persist and move pending availability to quoted."""

    expires_at = datetime.now(UTC) + timedelta(days=10)
    quote_payload = {
        "amount_minor": 250000,
        "currency": "tzs",
        "expires_at": expires_at.isoformat(),
        "terms": "Synthetic demonstration terms only.",
    }

    response = auth_client.post(
        f"/api/v1/operator/bookings/{assigned_booking.booking_reference}/quote",
        headers=operator_headers,
        json=quote_payload,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "quoted"
    assert payload["quote"]["currency"] == "TZS"
    assert payload["quote"]["is_demo"] is True
    assert "not live availability" in payload["quote"]["disclaimer"]
    db_session.expire_all()
    quote = db_session.scalar(select(BookingQuote))
    assert quote is not None
    assert quote.booking_request_id == assigned_booking.id

    duplicate_response = auth_client.post(
        f"/api/v1/operator/bookings/{assigned_booking.booking_reference}/quote",
        headers=operator_headers,
        json=quote_payload,
    )
    assert duplicate_response.status_code == 409


def test_operator_can_reject_pending_booking_with_audit_reason(
    auth_client: TestClient,
    db_session: Session,
    operator_headers: dict[str, str],
    assigned_booking: BookingRequest,
) -> None:
    """Rejection should follow the workflow and preserve the operator reason."""

    response = auth_client.post(
        f"/api/v1/operator/bookings/{assigned_booking.booking_reference}/reject",
        headers=operator_headers,
        json={"reason": "Synthetic capacity is unavailable for this test."},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
    assert response.json()["status_history"][-1]["reason"] == (
        "Synthetic capacity is unavailable for this test."
    )
    db_session.expire_all()
    rejected = db_session.get(BookingRequest, assigned_booking.id)
    assert rejected is not None
    assert rejected.status == "rejected"


def test_operator_cannot_confirm_directly_from_pending_availability(
    auth_client: TestClient,
    operator_headers: dict[str, str],
    assigned_booking: BookingRequest,
) -> None:
    """Confirmation must never skip quote and customer acceptance states."""

    response = auth_client.post(
        f"/api/v1/operator/bookings/{assigned_booking.booking_reference}/confirm",
        headers=operator_headers,
        json={"reason": "Attempted direct confirmation"},
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Booking cannot perform that transition from its current status"
    }


def test_operator_can_confirm_only_after_customer_acceptance_state(
    auth_client: TestClient,
    db_session: Session,
    operator_headers: dict[str, str],
    assigned_booking: BookingRequest,
) -> None:
    """The endpoint confirms only a quote already accepted through a trusted path."""

    quote_response = auth_client.post(
        f"/api/v1/operator/bookings/{assigned_booking.booking_reference}/quote",
        headers=operator_headers,
        json={
            "amount_minor": 300000,
            "currency": "TZS",
            "expires_at": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
        },
    )
    assert quote_response.status_code == 200

    db_session.expire_all()
    booking = db_session.get(BookingRequest, assigned_booking.id)
    assert booking is not None
    transition_booking(
        db_session,
        booking,
        BookingStatus.PENDING_CONFIRMATION,
        WorkflowActor(
            actor_type=StatusActorType.CUSTOMER,
            principal_id="verified-customer-test-context",
            authorized_booking_id=booking.id,
        ),
        reason="Simulated verified customer acceptance in isolated test",
    )

    response = auth_client.post(
        f"/api/v1/operator/bookings/{assigned_booking.booking_reference}/confirm",
        headers=operator_headers,
        json={"reason": "Synthetic operator confirmation for demonstration"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "confirmed"
    assert "do not prove" in response.json()["reservation_disclaimer"]
