"""Customer booking access privacy-boundary tests."""

from datetime import date, timedelta
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.models.destination import Destination


def submission_payload(destination_id: UUID) -> dict[str, object]:
    """Return a valid public submission containing private customer data."""

    start_date = date.today() + timedelta(days=30)
    return {
        "destination_id": str(destination_id),
        "travel_start_date": start_date.isoformat(),
        "travel_end_date": (start_date + timedelta(days=3)).isoformat(),
        "party_size": 2,
        "customer_name": "Private Customer",
        "customer_email": "private.customer@example.com",
        "customer_phone": "+255715123456",
        "customer_contact_preference": "email",
        "customer_consent": True,
        "special_requests": "Private request details.",
    }


def test_reference_and_contact_data_do_not_grant_customer_access(
    client: TestClient,
    seeded_destinations: list[Destination],
) -> None:
    """Public identifiers must not expose or advance an existing booking."""

    create_response = client.post(
        "/api/v1/bookings",
        headers={"Idempotency-Key": f"customer-access-{uuid4().hex}"},
        json=submission_payload(seeded_destinations[0].id),
    )
    assert create_response.status_code == 201
    booking_reference = create_response.json()["booking_reference"]
    assert "customer_email" not in create_response.json()
    assert "customer_phone" not in create_response.json()

    detail_response = client.get(f"/api/v1/bookings/{booking_reference}")
    acceptance_response = client.post(
        f"/api/v1/bookings/{booking_reference}/accept",
        json={
            "email": "private.customer@example.com",
            "phone": "+255715123456",
        },
    )
    query_response = client.get(
        "/api/v1/bookings",
        params={
            "booking_reference": booking_reference,
            "email": "private.customer@example.com",
        },
    )

    assert detail_response.status_code == 404
    assert acceptance_response.status_code == 404
    assert query_response.status_code == 405
    combined_response = (
        detail_response.text + acceptance_response.text + query_response.text
    )
    assert "private.customer@example.com" not in combined_response
    assert "+255715123456" not in combined_response
    assert "Private request details" not in combined_response
