"""End-to-end public API integration coverage."""

from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.booking import BookingRequest, BookingStatusHistory
from app.models.destination import Destination


def test_catalog_to_booking_submission_journey(
    client: TestClient,
    db_session: Session,
    seeded_destinations: list[Destination],
) -> None:
    """A traveller can discover and submit once without public booking access."""

    health_response = client.get("/api/health")
    catalog_response = client.get(
        "/api/v1/destinations",
        params={"q": "Serengeti", "category": "national_park"},
    )

    assert health_response.status_code == 200
    assert catalog_response.status_code == 200
    assert catalog_response.json()["total"] == 1
    destination_id = catalog_response.json()["items"][0]["id"]

    start_date = date.today() + timedelta(days=90)
    booking_payload = {
        "destination_id": destination_id,
        "travel_start_date": start_date.isoformat(),
        "travel_end_date": (start_date + timedelta(days=6)).isoformat(),
        "party_size": 4,
        "customer_name": "Integration Traveller",
        "customer_phone": "+255754123456",
        "customer_contact_preference": "phone",
        "customer_consent": True,
    }
    headers = {"Idempotency-Key": "integration-journey-0001"}

    booking_response = client.post(
        "/api/v1/bookings", headers=headers, json=booking_payload
    )
    replay_response = client.post(
        "/api/v1/bookings", headers=headers, json=booking_payload
    )

    assert booking_response.status_code == 201
    assert booking_response.json()["status"] == "pending_availability"
    assert replay_response.status_code == 200
    assert (
        replay_response.json()["booking_reference"]
        == booking_response.json()["booking_reference"]
    )
    assert client.get(
        f"/api/v1/bookings/{booking_response.json()['booking_reference']}"
    ).status_code == 404
    assert db_session.scalar(select(func.count()).select_from(BookingRequest)) == 1
    assert (
        db_session.scalar(select(func.count()).select_from(BookingStatusHistory)) == 1
    )
