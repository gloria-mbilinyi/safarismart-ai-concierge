"""Regression coverage for supported and unsupported destination chat."""

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


@pytest.mark.parametrize(
    ("message", "location"),
    [
        ("Mwanza", "Mwanza"),
        ("I want to visit Mbeya", "Mbeya"),
        ("Tell me about Dodoma", "Dodoma"),
        ("What can I do in Mwanza?", "Mwanza"),
        ("Can I book Mbeya?", "Mbeya"),
    ],
)
def test_named_unsupported_location_gets_specific_catalog_fallback(
    client: TestClient,
    seeded_destinations: list[Destination],
    message: str,
    location: str,
) -> None:
    payload = chat(client, message)

    assert payload["intent"] == "unknown_location"
    assert f"don't have information about {location}" in payload["answer"]
    assert (
        "Serengeti, Ngorongoro, Mount Kilimanjaro, Zanzibar, and Tarangire"
        in payload["answer"]
    )
    assert "wildlife, beach, mountain" not in payload["answer"]
    assert payload["referenced_destinations"] == []
    assert payload["booking_destination_id"] is None


def test_named_unsupported_location_gets_swahili_fallback(
    client: TestClient,
    seeded_destinations: list[Destination],
) -> None:
    payload = chat(client, "Nataka kutembelea Mbeya", language="sw")

    assert payload["intent"] == "unknown_location"
    assert "sina taarifa kuhusu Mbeya" in payload["answer"]
    assert (
        "Serengeti, Ngorongoro, Mlima Kilimanjaro, Zanzibar, na Tarangire"
        in payload["answer"]
    )
    assert payload["referenced_destinations"] == []


def test_unsupported_location_overrides_previous_catalog_context(
    client: TestClient,
    seeded_destinations: list[Destination],
) -> None:
    payload = chat(
        client,
        "Mwanza",
        history=[{"role": "user", "content": "Tell me about Zanzibar"}],
    )

    assert payload["intent"] == "unknown_location"
    assert "about Mwanza" in payload["answer"]
    assert payload["referenced_destinations"] == []


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
def test_all_five_supported_destinations_keep_catalog_grounding(
    client: TestClient,
    seeded_destinations: list[Destination],
    message: str,
    slug: str,
) -> None:
    payload = chat(client, message)

    assert payload["intent"] == "destination_overview"
    assert [item["slug"] for item in payload["referenced_destinations"]] == [slug]
    assert payload["booking_destination_id"] is None


@pytest.mark.parametrize(("message", "language"), [("Hi", "en"), ("Habari", "sw")])
def test_greetings_are_natural_and_do_not_trigger_location_fallback(
    client: TestClient,
    seeded_destinations: list[Destination],
    message: str,
    language: str,
) -> None:
    payload = chat(client, message, language=language)

    assert payload["intent"] == "greeting"
    assert "Mwanza" not in payload["answer"]
    assert "Serengeti" in payload["answer"]


def test_generic_interest_question_still_returns_catalog_recommendations(
    client: TestClient,
    seeded_destinations: list[Destination],
) -> None:
    payload = chat(client, "I enjoy wildlife and nature")

    assert payload["intent"] == "recommendation"
    assert payload["referenced_destinations"]
