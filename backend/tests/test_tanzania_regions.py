"""Integrity tests for the source-attributed Tanzania regional guide."""

from app.knowledge.tanzania_regions import (
    NBS_REGION_SOURCE,
    REGIONS_BY_SLUG,
    TANZANIA_REGIONS,
    find_region_mentions,
)


def test_knowledge_layer_contains_every_official_tanzania_region_once() -> None:
    """The 26 mainland and five Zanzibar regions remain unique and attributable."""

    assert len(TANZANIA_REGIONS) == 31
    assert len(REGIONS_BY_SLUG) == 31
    assert len({region.name for region in TANZANIA_REGIONS}) == 31
    assert all(NBS_REGION_SOURCE in region.source_urls for region in TANZANIA_REGIONS)
    assert all(region.verified_on.isoformat() == "2026-11-19" for region in TANZANIA_REGIONS)


def test_required_regions_and_verified_highlights_are_present() -> None:
    """High-priority conversational regions carry cited discovery facts."""

    required = {
        "mwanza",
        "arusha",
        "kilimanjaro",
        "dar-es-salaam",
        "dodoma",
        "mbeya",
        "morogoro",
        "tanga",
        "iringa",
        "kigoma",
        "mjini-magharibi",
    }

    assert required <= REGIONS_BY_SLUG.keys()
    assert all(REGIONS_BY_SLUG[slug].highlights for slug in required)
    assert "Saanane Island National Park" in {
        highlight.name for highlight in REGIONS_BY_SLUG["mwanza"].highlights
    }


def test_region_resolution_supports_aliases_and_conservative_spelling() -> None:
    """City aliases and a single-character typo resolve without broad fuzzy guessing."""

    assert find_region_mentions("I want to visit Dar es Salam")[0].slug == "dar-es-salaam"
    assert find_region_mentions("Tell me about Moshi")[0].slug == "kilimanjaro"
    assert find_region_mentions("mwanzaa")[0].slug == "mwanza"
    assert find_region_mentions("I enjoy wildlife and nature") == []
