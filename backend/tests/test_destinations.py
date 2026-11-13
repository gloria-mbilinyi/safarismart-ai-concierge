"""Destination seed and public catalog endpoint tests."""

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.destination import Destination
from app.seed.destinations import seed_destinations


EXPECTED_DESTINATIONS = {
    "Serengeti National Park",
    "Ngorongoro Conservation Area",
    "Mount Kilimanjaro",
    "Zanzibar",
    "Tarangire National Park",
}


def test_destination_seed_is_repeatable(db_session: Session) -> None:
    """Running the destination seed repeatedly must not create duplicates."""

    first_created = seed_destinations(db_session)
    second_created = seed_destinations(db_session)
    destination_count = db_session.scalar(select(func.count()).select_from(Destination))

    assert first_created == 5
    assert second_created == 0
    assert destination_count == 5


def test_list_destinations_returns_curated_catalog(
    client: TestClient,
    seeded_destinations: list[Destination],
) -> None:
    """The public list should return all curated destinations without claims."""

    response = client.get("/api/v1/destinations")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 5
    assert {item["name"] for item in payload["items"]} == EXPECTED_DESTINATIONS
    assert all("price" not in item for item in payload["items"])
    assert all("availability" not in item for item in payload["items"])
    assert all("operator" not in item for item in payload["items"])


def test_list_destinations_supports_search_and_filters(
    client: TestClient,
    seeded_destinations: list[Destination],
) -> None:
    """Search, category, region, and pagination filters should compose."""

    search_response = client.get("/api/v1/destinations", params={"q": "zanzibar"})
    parks_response = client.get(
        "/api/v1/destinations",
        params={"category": "national_park", "limit": 1, "offset": 1},
    )
    region_response = client.get(
        "/api/v1/destinations",
        params={"region": "ARUSHA", "featured": True},
    )

    assert search_response.status_code == 200
    assert [item["name"] for item in search_response.json()["items"]] == ["Zanzibar"]
    assert parks_response.status_code == 200
    assert parks_response.json()["total"] == 2
    assert len(parks_response.json()["items"]) == 1
    assert region_response.status_code == 200
    assert [item["name"] for item in region_response.json()["items"]] == [
        "Ngorongoro Conservation Area"
    ]


def test_get_destination_returns_public_detail(
    client: TestClient,
    seeded_destinations: list[Destination],
) -> None:
    """An active destination should be addressable by UUID."""

    destination = next(
        item for item in seeded_destinations if item.name == "Mount Kilimanjaro"
    )

    response = client.get(f"/api/v1/destinations/{destination.id}")

    assert response.status_code == 200
    assert response.json()["slug"] == "mount-kilimanjaro"
    assert response.json()["category"] == "mountain"


def test_get_destination_hides_missing_and_inactive_records(
    client: TestClient,
    db_session: Session,
    seeded_destinations: list[Destination],
) -> None:
    """Missing and inactive destinations should both use the public 404 response."""

    inactive_destination = seeded_destinations[0]
    inactive_destination.is_active = False
    db_session.commit()

    inactive_response = client.get(
        f"/api/v1/destinations/{inactive_destination.id}"
    )
    missing_response = client.get(f"/api/v1/destinations/{uuid4()}")

    assert inactive_response.status_code == 404
    assert inactive_response.json() == {"detail": "Destination not found"}
    assert missing_response.status_code == 404
    assert missing_response.json() == {"detail": "Destination not found"}


def test_destination_filters_validate_query_parameters(
    client: TestClient,
    seeded_destinations: list[Destination],
) -> None:
    """Invalid pagination and categories should return validation errors."""

    invalid_limit = client.get("/api/v1/destinations", params={"limit": 101})
    invalid_category = client.get(
        "/api/v1/destinations", params={"category": "invented"}
    )

    assert invalid_limit.status_code == 422
    assert invalid_category.status_code == 422
