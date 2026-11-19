"""Acceptance coverage for natural regional concierge conversations."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.models.destination import Destination


def chat(
    client: TestClient,
    message: str,
    *,
    history: list[dict[str, str]] | None = None,
    language: str = "en",
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/concierge/chat",
        json={
            "message": message,
            "language": language,
            "history": history or [],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_greeting_receives_a_natural_tanzania_welcome(
    client: TestClient,
    seeded_destinations: list[Destination],
) -> None:
    payload = chat(client, "Hi")

    assert payload["intent"] == "greeting"
    assert payload["answer"].startswith("Hi, welcome to SafariSmart!")
    assert "31 Tanzanian regions" in payload["answer"]
    assert "Tell me a destination or travel interest" not in payload["answer"]


@pytest.mark.parametrize("message", ["Mwanza", "I want to visit Mwanza"])
def test_mwanza_is_recognized_as_regional_discovery(
    client: TestClient,
    seeded_destinations: list[Destination],
    message: str,
) -> None:
    payload = chat(client, message)

    assert payload["intent"] == "region_overview"
    assert "Mwanza is a Tanzanian region" in payload["answer"]
    assert "Saanane Island National Park" in payload["answer"]
    assert "regional discovery guidance" in payload["answer"]
    assert payload["referenced_destinations"] == []
    assert payload["booking_destination_id"] is None


def test_mwanza_activity_question_returns_verified_themes(
    client: TestClient,
    seeded_destinations: list[Destination],
) -> None:
    payload = chat(client, "What can I do in Mwanza?")

    assert payload["intent"] == "activities"
    assert "Saanane Island National Park" in payload["answer"]
    assert "walking trails" in payload["answer"]
    assert "Lake Victoria viewpoints" in payload["answer"]
    assert "live schedules" in payload["answer"]


def test_swahili_mbeya_question_uses_regional_knowledge(
    client: TestClient,
    seeded_destinations: list[Destination],
) -> None:
    payload = chat(client, "Nataka kutembelea Mbeya", language="sw")

    assert payload["intent"] == "region_overview"
    assert "Mbeya ni mkoa wa Tanzania" in payload["answer"]
    assert "Ziwa la Kreta Ngozi" in payload["answer"]
    assert "mazingira" in payload["answer"]
    assert payload["referenced_destinations"] == []


def test_kilimanjaro_remains_the_existing_bookable_destination(
    client: TestClient,
    seeded_destinations: list[Destination],
) -> None:
    payload = chat(client, "Kilimanjaro")

    assert payload["intent"] == "destination_overview"
    assert "Mount Kilimanjaro is in Kilimanjaro" in payload["answer"]
    assert [item["slug"] for item in payload["referenced_destinations"]] == [
        "mount-kilimanjaro"
    ]


def test_explicit_new_region_replaces_previous_context(
    client: TestClient,
    seeded_destinations: list[Destination],
) -> None:
    payload = chat(
        client,
        "I want to visit Arusha",
        history=[{"role": "user", "content": "Tell me about Mwanza"}],
    )

    assert payload["intent"] == "region_overview"
    assert "Arusha is a Tanzanian region" in payload["answer"]
    assert "Arusha National Park" in payload["answer"]
    assert "Saanane" not in payload["answer"]


def test_regional_pronoun_follow_up_retains_recent_user_context(
    client: TestClient,
    seeded_destinations: list[Destination],
) -> None:
    payload = chat(
        client,
        "What can I do there?",
        history=[
            {"role": "user", "content": "Tell me about Mwanza"},
            {"role": "assistant", "content": "Mwanza is in the Lake Zone."},
        ],
    )

    assert payload["intent"] == "activities"
    assert "In Mwanza" in payload["answer"]
    assert "Saanane Island National Park" in payload["answer"]


def test_unknown_new_place_does_not_reuse_previous_region(
    client: TestClient,
    seeded_destinations: list[Destination],
) -> None:
    payload = chat(
        client,
        "Tell me about Atlantis",
        history=[{"role": "user", "content": "Tell me about Mwanza"}],
    )

    assert payload["intent"] == "unknown_location"
    assert "could not confidently match" in payload["answer"]
    assert "Saanane" not in payload["answer"]
    assert payload["referenced_destinations"] == []


def test_live_mwanza_hotel_price_is_refused_without_guessing(
    client: TestClient,
    seeded_destinations: list[Destination],
) -> None:
    payload = chat(client, "How much is a hotel in Mwanza?")

    assert payload["intent"] == "unsupported_fact"
    assert "verified live hotel-pricing" in payload["answer"]
    assert "cannot quote a current rate" in payload["answer"]
    assert not any(character.isdigit() for character in payload["answer"])


def test_region_booking_guidance_never_creates_booking_authority(
    client: TestClient,
    seeded_destinations: list[Destination],
) -> None:
    payload = chat(client, "Can I book Mwanza?")

    assert payload["intent"] == "booking_guidance"
    assert "not a bookable catalog record" in payload["answer"]
    assert "pending availability" in payload["answer"]
    assert "real reservation" in payload["answer"]
    assert payload["booking_destination_id"] is None


@pytest.mark.parametrize(
    ("message", "slug"),
    [
        ("Serengeti", "serengeti-national-park"),
        ("Ngorongoro", "ngorongoro-conservation-area"),
        ("Kilimanjaro", "mount-kilimanjaro"),
        ("Zanzibar", "zanzibar"),
        ("Tarangire", "tarangire-national-park"),
    ],
)
def test_all_five_featured_destinations_keep_catalog_grounding(
    client: TestClient,
    seeded_destinations: list[Destination],
    message: str,
    slug: str,
) -> None:
    payload = chat(client, message)

    assert payload["intent"] == "destination_overview"
    assert [item["slug"] for item in payload["referenced_destinations"]] == [slug]
