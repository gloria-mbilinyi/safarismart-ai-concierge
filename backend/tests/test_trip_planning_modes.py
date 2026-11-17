"""Regression coverage for explicit destination-scoped trip planning."""

from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient

from app.integrations.concierge_provider import ConciergeProviderError
from app.models.destination import Destination


class FailingRankingProvider:
    """Fail every optional ranking request."""

    mode = "local_ollama"

    def rank_slugs(self, **_: Any) -> list[str]:
        raise ConciergeProviderError("provider unavailable")


class UnsafeRankingProvider:
    """Attempt to introduce a destination outside the filtered candidate set."""

    mode = "local_ollama"

    def rank_slugs(self, **_: Any) -> list[str]:
        return ["ngorongoro-conservation-area"]


def destination_by_slug(
    destinations: list[Destination], slug: str
) -> Destination:
    """Return one deterministic seeded catalog row."""

    return next(destination for destination in destinations if destination.slug == slug)


def plan(
    client: TestClient,
    *,
    mode: str,
    ids: list[str],
    days: int = 5,
    language: str = "en",
) -> dict[str, Any]:
    """Submit one explicit planner request and return its JSON payload."""

    response = client.post(
        "/api/v1/concierge/plan",
        json={
            "days": days,
            "party_size": 2,
            "interests": ["nature"],
            "planning_mode": mode,
            "destination_ids": ids,
            "language": language,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_zanzibar_only_plan_never_includes_ngorongoro(
    client: TestClient,
    seeded_destinations: list[Destination],
) -> None:
    """Every day must retain the traveller's one explicit destination."""

    zanzibar = destination_by_slug(seeded_destinations, "zanzibar")
    payload = plan(
        client,
        mode="single_destination",
        ids=[str(zanzibar.id)],
    )

    assert payload["planning_mode"] == "single_destination"
    assert [item["name"] for item in payload["destinations"]] == ["Zanzibar"]
    assert {day["destination_name"] for day in payload["itinerary"]} == {
        "Zanzibar"
    }
    assert "Ngorongoro" not in str(payload)
    assert len({day["focus"] for day in payload["itinerary"]}) > 1


def test_serengeti_only_plan_never_includes_zanzibar(
    client: TestClient,
    seeded_destinations: list[Destination],
) -> None:
    """Single-park planning cannot leak a beach recommendation."""

    serengeti = destination_by_slug(seeded_destinations, "serengeti-national-park")
    payload = plan(
        client,
        mode="single_destination",
        ids=[str(serengeti.id)],
        days=3,
    )

    assert {day["destination_name"] for day in payload["itinerary"]} == {
        "Serengeti National Park"
    }
    assert "Zanzibar" not in str(payload)


def test_multiple_destination_plan_uses_only_explicit_selections(
    client: TestClient,
    seeded_destinations: list[Destination],
) -> None:
    """No unselected catalog row may enter destinations or itinerary days."""

    zanzibar = destination_by_slug(seeded_destinations, "zanzibar")
    kilimanjaro = destination_by_slug(seeded_destinations, "mount-kilimanjaro")
    payload = plan(
        client,
        mode="multiple_destinations",
        ids=[str(zanzibar.id), str(kilimanjaro.id)],
        days=4,
    )

    selected_names = {"Zanzibar", "Mount Kilimanjaro"}
    assert {item["name"] for item in payload["destinations"]} == selected_names
    assert {day["destination_name"] for day in payload["itinerary"]} == selected_names


def test_explore_tanzania_can_recommend_multiple_destinations(
    client: TestClient,
    seeded_destinations: list[Destination],
) -> None:
    """Explore mode remains the only mode that broadens the route."""

    payload = plan(client, mode="explore_tanzania", ids=[], days=5)

    assert payload["planning_mode"] == "explore_tanzania"
    assert len(payload["destinations"]) > 1


def test_explicit_plans_support_swahili_and_survive_provider_failure(
    client: TestClient,
    seeded_destinations: list[Destination],
) -> None:
    """Filtering is enforced before a failing optional provider is invoked."""

    zanzibar = destination_by_slug(seeded_destinations, "zanzibar")
    client.app.state.concierge_provider = FailingRankingProvider()
    payload = plan(
        client,
        mode="single_destination",
        ids=[str(zanzibar.id)],
        days=3,
        language="sw",
    )

    assert payload["generation_mode"] == "rule_based_fallback"
    assert payload["title"].startswith("Wazo la siku 3")
    assert {day["destination_name"] for day in payload["itinerary"]} == {
        "Zanzibar"
    }


def test_provider_cannot_reintroduce_an_unselected_destination(
    client: TestClient,
    seeded_destinations: list[Destination],
) -> None:
    """Unknown-to-scope provider output falls back to the filtered set."""

    zanzibar = destination_by_slug(seeded_destinations, "zanzibar")
    client.app.state.concierge_provider = UnsafeRankingProvider()
    payload = plan(
        client,
        mode="single_destination",
        ids=[str(zanzibar.id)],
        days=2,
    )

    assert payload["generation_mode"] == "rule_based_fallback"
    assert {day["destination_name"] for day in payload["itinerary"]} == {
        "Zanzibar"
    }
    assert "Ngorongoro" not in str(payload)


def test_invalid_or_incoherent_destination_selections_are_rejected(
    client: TestClient,
    seeded_destinations: list[Destination],
) -> None:
    """Missing, unknown, and mode-incompatible selections fail safely."""

    zanzibar = destination_by_slug(seeded_destinations, "zanzibar")
    no_single_destination = client.post(
        "/api/v1/concierge/plan",
        json={
            "days": 3,
            "interests": ["beach"],
            "planning_mode": "single_destination",
            "destination_ids": [],
        },
    )
    unknown_destination = client.post(
        "/api/v1/concierge/plan",
        json={
            "days": 3,
            "interests": ["beach"],
            "planning_mode": "single_destination",
            "destination_ids": [str(uuid4())],
        },
    )
    explore_with_selection = client.post(
        "/api/v1/concierge/plan",
        json={
            "days": 3,
            "interests": ["beach"],
            "planning_mode": "explore_tanzania",
            "destination_ids": [str(zanzibar.id)],
        },
    )

    assert no_single_destination.status_code == 422
    assert unknown_destination.status_code == 422
    assert unknown_destination.json()["detail"] == (
        "One or more selected destinations are unavailable"
    )
    assert explore_with_selection.status_code == 422
