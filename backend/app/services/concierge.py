"""Catalog-grounded trip planning."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.concierge_provider import (
    ConciergeProviderError,
    DestinationRankingProvider,
)
from app.models.destination import Destination
from app.models.enums import DestinationCategory
from app.schemas.concierge import (
    ConciergeLanguage,
    ItineraryDay,
    PlanDestination,
    PlanningMode,
    TravelInterest,
    TripPlanRequest,
    TripPlanResponse,
)


class DestinationSelectionError(ValueError):
    """Raised when an explicit plan references unavailable catalog rows."""


INTEREST_CATEGORIES: dict[TravelInterest, set[str]] = {
    TravelInterest.WILDLIFE: {
        DestinationCategory.NATIONAL_PARK.value,
        DestinationCategory.CONSERVATION_AREA.value,
    },
    TravelInterest.BEACH: {DestinationCategory.BEACH.value},
    TravelInterest.MOUNTAIN: {DestinationCategory.MOUNTAIN.value},
    TravelInterest.CULTURE: {
        DestinationCategory.BEACH.value,
        DestinationCategory.CONSERVATION_AREA.value,
    },
    TravelInterest.NATURE: {category.value for category in DestinationCategory},
}


def _active_destinations(session: Session) -> list[Destination]:
    """Load only the active public records that may ground a response."""

    return list(
        session.scalars(
            select(Destination)
            .where(Destination.is_active.is_(True))
            .order_by(Destination.is_featured.desc(), Destination.name.asc())
        ).all()
    )


def _score_destinations(
    destinations: Sequence[Destination],
    interests: Sequence[TravelInterest],
    preferred_region: str | None,
) -> list[Destination]:
    """Rank deterministically by interest, region, featured flag, then name."""

    region = preferred_region.casefold() if preferred_region else None

    def score(destination: Destination) -> tuple[int, int, str]:
        interest_score = sum(
            3
            for interest in interests
            if destination.category in INTEREST_CATEGORIES[interest]
        )
        region_score = (
            4 if region is not None and destination.region.casefold() == region else 0
        )
        featured_score = 1 if destination.is_featured else 0
        return (interest_score + region_score, featured_score, destination.name)

    return sorted(destinations, key=score, reverse=True)


def _apply_optional_ranking(
    destinations: list[Destination],
    interests: list[TravelInterest],
    preferred_region: str | None,
    provider: DestinationRankingProvider | None,
) -> tuple[list[Destination], str]:
    """Apply only a validated slug ranking and fail safely to local ordering."""

    if provider is None or not destinations:
        return destinations, "rule_based_fallback"

    by_slug = {destination.slug: destination for destination in destinations}
    try:
        ranked_slugs = provider.rank_slugs(
            allowed_slugs=list(by_slug),
            interests=[interest.value for interest in interests],
            preferred_region=preferred_region,
        )
    except ConciergeProviderError:
        return destinations, "rule_based_fallback"

    if (
        not ranked_slugs
        or any(slug not in by_slug for slug in ranked_slugs)
        or len(ranked_slugs) != len(set(ranked_slugs))
    ):
        return destinations, "rule_based_fallback"

    ranked = [by_slug[slug] for slug in ranked_slugs]
    ranked_set = set(ranked_slugs)
    ranked.extend(
        destination
        for destination in destinations
        if destination.slug not in ranked_set
    )
    return ranked, "local_ollama"


def _match_reasons(
    destination: Destination,
    request: TripPlanRequest,
) -> list[str]:
    """Explain catalog matching without inventing availability or quality claims."""

    swahili = request.language == ConciergeLanguage.SWAHILI
    reasons: list[str] = []
    for interest in request.interests:
        if destination.category in INTEREST_CATEGORIES[interest]:
            reasons.append(
                f"Inalingana na hamu ya {interest.value}"
                if swahili
                else f"Matches your {interest.value} interest"
            )
    if (
        request.preferred_region
        and destination.region.casefold() == request.preferred_region.casefold()
    ):
        reasons.append(
            f"Iko katika eneo la {destination.region}"
            if swahili
            else f"Located in your preferred {destination.region} region"
        )
    return reasons[:3] or [
        "Ni sehemu ya orodha iliyohakikiwa ya SafariSmart"
        if swahili
        else "Included in SafariSmart's curated catalog"
    ]


def _plan_destination(
    destination: Destination,
    request: TripPlanRequest,
) -> PlanDestination:
    """Convert a database row to a public recommendation with explicit reasons."""

    return PlanDestination(
        id=destination.id,
        name=destination.name,
        slug=destination.slug,
        region=destination.region,
        category=destination.category,
        description=destination.description,
        match_reasons=_match_reasons(destination, request),
    )


DAY_FOCUSES: dict[str, dict[bool, tuple[str, ...]]] = {
    DestinationCategory.NATIONAL_PARK.value: {
        False: (
            "Get oriented to the park landscape and its ecosystem",
            "Focus on wildlife observation themes supported by the catalog",
            "Explore how the landscape shapes the destination's character",
            "Make space for responsible nature appreciation and reflection",
        ),
        True: (
            "Fahamu mandhari ya hifadhi na mfumo wake wa ikolojia",
            "Zingatia mada za kutazama wanyamapori zilizopo kwenye orodha",
            "Gundua jinsi mandhari inavyounda tabia ya eneo hili",
            "Tenga muda wa kuthamini mazingira kwa uwajibikaji",
        ),
    },
    DestinationCategory.CONSERVATION_AREA.value: {
        False: (
            "Get oriented to the conservation landscape",
            "Learn about the relationship between wildlife and communities",
            "Focus on the area's natural and cultural context",
            "Reflect on responsible travel in a shared landscape",
        ),
        True: (
            "Fahamu mandhari ya eneo la uhifadhi",
            "Jifunze uhusiano kati ya wanyamapori na jamii",
            "Zingatia mazingira ya asili na utamaduni wa eneo",
            "Tafakari kuhusu safari yenye uwajibikaji katika mandhari ya pamoja",
        ),
    },
    DestinationCategory.MOUNTAIN.value: {
        False: (
            "Understand the mountain environment and established route themes",
            "Consider the ecological zones described by the catalog",
            "Plan a pace suited to your ability without assuming a booked route",
            "Focus on preparation and responsible mountain travel",
        ),
        True: (
            "Fahamu mazingira ya mlima na mada za njia zinazotambulika",
            "Zingatia kanda za ikolojia zilizoelezwa kwenye orodha",
            "Panga mwendo unaofaa uwezo wako bila kudhani njia imehifadhiwa",
            "Zingatia maandalizi na safari ya mlima yenye uwajibikaji",
        ),
    },
    DestinationCategory.BEACH.value: {
        False: (
            "Get oriented to the coastal landscape and setting",
            "Explore the destination's Swahili cultural themes",
            "Focus on the beach and Indian Ocean environment",
            "Use the catalog's historic and local-tradition themes for discovery",
        ),
        True: (
            "Fahamu mandhari na mazingira ya pwani",
            "Gundua mada za utamaduni wa Kiswahili wa eneo hili",
            "Zingatia mazingira ya fukwe na Bahari ya Hindi",
            "Tumia mada za historia na mila katika orodha kwa ugunduzi",
        ),
    },
}


def _day_focus(destination: Destination, swahili: bool, visit_index: int) -> str:
    """Rotate grounded category themes without inventing timed activities."""

    focuses = DAY_FOCUSES[destination.category][swahili]
    return focuses[visit_index % len(focuses)]


def _planning_candidates(
    destinations: list[Destination],
    request: TripPlanRequest,
) -> list[Destination]:
    """Enforce the requested destination scope before any optional ranking."""

    if request.planning_mode == PlanningMode.EXPLORE_TANZANIA:
        return _score_destinations(
            destinations,
            request.interests,
            request.preferred_region,
        )

    by_id = {destination.id: destination for destination in destinations}
    if any(
        destination_id not in by_id
        for destination_id in request.destination_ids
    ):
        raise DestinationSelectionError(
            "One or more selected destinations are unavailable"
        )
    return [by_id[destination_id] for destination_id in request.destination_ids]


def _build_itinerary(
    selected: list[Destination],
    request: TripPlanRequest,
) -> list[ItineraryDay]:
    """Build day themes using only the already-authorized destination set."""

    swahili = request.language == ConciergeLanguage.SWAHILI
    visit_counts = {destination.id: 0 for destination in selected}
    itinerary: list[ItineraryDay] = []
    for day in range(1, request.days + 1):
        destination = selected[(day - 1) % len(selected)]
        visit_index = visit_counts[destination.id]
        visit_counts[destination.id] += 1
        itinerary.append(
            ItineraryDay(
                day=day,
                title=(
                    f"Siku ya {day}: {destination.name}"
                    if swahili
                    else f"Day {day}: {destination.name}"
                ),
                destination_id=destination.id,
                destination_name=destination.name,
                focus=_day_focus(destination, swahili, visit_index),
            )
        )
    return itinerary


def create_trip_plan(
    session: Session,
    request: TripPlanRequest,
    provider: DestinationRankingProvider | None = None,
) -> TripPlanResponse:
    """Create a high-level itinerary entirely from active destination records."""

    candidates = _planning_candidates(_active_destinations(session), request)
    ranked = candidates
    ranked, generation_mode = _apply_optional_ranking(
        ranked,
        request.interests,
        request.preferred_region,
        provider,
    )
    selected = (
        ranked[: min(4, request.days)]
        if request.planning_mode == PlanningMode.EXPLORE_TANZANIA
        else ranked
    )
    swahili = request.language == ConciergeLanguage.SWAHILI

    if not selected:
        return TripPlanResponse(
            generation_mode="rule_based_fallback",
            planning_mode=request.planning_mode,
            title="Hakuna maeneo yanayopatikana" if swahili else "No destinations available",
            summary=(
                "Orodha ya maeneo haijajazwa bado. Jaribu tena baada ya msimamizi kuweka data."
                if swahili
                else "The destination catalog has not been populated yet. Try again after demo data is loaded."
            ),
            destinations=[],
            itinerary=[],
            disclaimer=_disclaimer(swahili),
        )

    itinerary = _build_itinerary(selected, request)
    if request.planning_mode == PlanningMode.SINGLE_DESTINATION:
        title = (
            f"Wazo la siku {request.days}: {selected[0].name}"
            if swahili
            else f"{request.days}-day {selected[0].name} trip idea"
        )
    elif request.planning_mode == PlanningMode.MULTIPLE_DESTINATIONS:
        title = (
            f"Wazo la safari ya maeneo uliyochagua kwa siku {request.days}"
            if swahili
            else f"{request.days}-day selected-destinations trip idea"
        )
    else:
        title = (
            f"Wazo la safari ya siku {request.days} Tanzania"
            if swahili
            else f"{request.days}-day Tanzania trip idea"
        )
    if swahili:
        summary = (
            f"Pendekezo la kiwango cha {request.budget_style.value} kwa watu "
            f"{request.party_size}, likitumia maeneo yaliyopo kwenye orodha yetu."
        )
        if request.budget_tzs is not None:
            summary += (
                f" Bajeti ya jumla ya TZS {request.budget_tzs:,} ni muktadha wa "
                "kupanga tu; hatukadirii gharama."
            )
    else:
        summary = (
            f"A {request.budget_style.value}-style idea for {request.party_size} "
            "traveler(s), using destinations in our curated catalog."
        )
        if request.budget_tzs is not None:
            summary += (
                f" Your TZS {request.budget_tzs:,} total budget is planning "
                "context only; no costs are estimated."
            )
    return TripPlanResponse(
        generation_mode=generation_mode,
        planning_mode=request.planning_mode,
        title=title,
        summary=summary,
        destinations=[
            _plan_destination(destination, request) for destination in selected
        ],
        itinerary=itinerary,
        disclaimer=_disclaimer(swahili),
    )


def _disclaimer(swahili: bool) -> str:
    """Return the same prominent planning limitation in both supported languages."""

    if swahili:
        return (
            "Hili ni wazo la kupanga, si bei, upatikanaji au nafasi iliyothibitishwa. "
            "Tuma ombi la booking ili opereta wa majaribio akague."
        )
    return (
        "This is a planning idea, not a price, live availability, or a confirmed reservation. "
        "Submit a booking request for review by the synthetic demo operator."
    )
