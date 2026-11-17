"""Validated public schemas for grounded trip planning and concierge chat."""

from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.enums import DestinationCategory


class ConciergeLanguage(StrEnum):
    """Languages supported by the deterministic concierge responses."""

    ENGLISH = "en"
    SWAHILI = "sw"


class TravelInterest(StrEnum):
    """Broad interests mapped to the curated destination catalog."""

    WILDLIFE = "wildlife"
    BEACH = "beach"
    MOUNTAIN = "mountain"
    CULTURE = "culture"
    NATURE = "nature"


class BudgetStyle(StrEnum):
    """Non-monetary preference; it never represents a live price quote."""

    VALUE = "value"
    COMFORT = "comfort"
    PREMIUM = "premium"


class TripPlanRequest(BaseModel):
    """Structured planning inputs that avoid open-ended prompt execution."""

    days: int = Field(ge=1, le=14)
    party_size: int = Field(default=1, ge=1, le=20)
    interests: list[TravelInterest] = Field(min_length=1, max_length=5)
    budget_style: BudgetStyle = BudgetStyle.COMFORT
    preferred_region: str | None = Field(default=None, min_length=2, max_length=120)
    language: ConciergeLanguage = ConciergeLanguage.ENGLISH

    @field_validator("interests")
    @classmethod
    def unique_interests(
        cls, value: list[TravelInterest]
    ) -> list[TravelInterest]:
        """Prevent duplicate values from distorting recommendation scores."""

        return list(dict.fromkeys(value))

    @field_validator("preferred_region")
    @classmethod
    def normalize_region(cls, value: str | None) -> str | None:
        """Normalize optional human-entered region text."""

        return value.strip() if value is not None else None


class PlanDestination(BaseModel):
    """A recommendation grounded in one active catalog row."""

    id: UUID
    name: str
    slug: str
    region: str
    category: DestinationCategory
    description: str
    match_reasons: list[str]


class ItineraryDay(BaseModel):
    """A high-level day theme, not a reservation or timed itinerary."""

    day: int
    title: str
    destination_id: UUID
    destination_name: str
    focus: str


class TripPlanResponse(BaseModel):
    """A transparent, catalog-grounded planning suggestion."""

    generation_mode: Literal["rule_based_fallback", "local_ollama"]
    title: str
    summary: str
    destinations: list[PlanDestination]
    itinerary: list[ItineraryDay]
    disclaimer: str


class ConciergeChatRequest(BaseModel):
    """A small public chat request bounded for safe catalog discovery."""

    message: str = Field(min_length=2, max_length=500)
    language: ConciergeLanguage = ConciergeLanguage.ENGLISH

    @field_validator("message")
    @classmethod
    def normalize_message(cls, value: str) -> str:
        """Remove surrounding whitespace before matching catalog content."""

        normalized = value.strip()
        if len(normalized) < 2:
            raise ValueError("Message must contain at least two characters")
        return normalized


class ConciergeChatResponse(BaseModel):
    """A bounded answer whose references point to public catalog records."""

    generation_mode: Literal["rule_based_fallback", "local_ollama"]
    answer: str
    referenced_destinations: list[PlanDestination]
    safety_notice: str | None = None
