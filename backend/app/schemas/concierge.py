"""Validated public schemas for grounded trip planning and concierge chat."""

from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.enums import DestinationCategory


class ConciergeLanguage(StrEnum):
    """Languages supported by the deterministic concierge responses."""

    ENGLISH = "en"
    SWAHILI = "sw"


class ChatRole(StrEnum):
    """Conversation roles accepted as bounded, untrusted context."""

    USER = "user"
    ASSISTANT = "assistant"


class ChatIntent(StrEnum):
    """Transparent intent labels used by the deterministic concierge."""

    RECOMMENDATION = "recommendation"
    DESTINATION_OVERVIEW = "destination_overview"
    ACTIVITIES = "activities"
    TRIP_DURATION = "trip_duration"
    COMPARISON = "comparison"
    BUDGET = "budget"
    BOOKING_GUIDANCE = "booking_guidance"
    UNSUPPORTED_FACT = "unsupported_fact"
    CLARIFICATION = "clarification"


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


class PlanningMode(StrEnum):
    """How destination scope is chosen for one itinerary."""

    SINGLE_DESTINATION = "single_destination"
    MULTIPLE_DESTINATIONS = "multiple_destinations"
    EXPLORE_TANZANIA = "explore_tanzania"


class TripPlanRequest(BaseModel):
    """Structured planning inputs that avoid open-ended prompt execution."""

    days: int = Field(ge=1, le=14)
    party_size: int = Field(default=1, ge=1, le=20)
    interests: list[TravelInterest] = Field(min_length=1, max_length=5)
    budget_style: BudgetStyle = BudgetStyle.COMFORT
    budget_tzs: int | None = Field(default=None, ge=100_000, le=100_000_000)
    planning_mode: PlanningMode = PlanningMode.EXPLORE_TANZANIA
    destination_ids: list[UUID] = Field(default_factory=list, max_length=5)
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

    @model_validator(mode="after")
    def validate_destination_scope(self) -> "TripPlanRequest":
        """Require a coherent destination set for the selected planning mode."""

        self.destination_ids = list(dict.fromkeys(self.destination_ids))
        count = len(self.destination_ids)
        if self.planning_mode == PlanningMode.SINGLE_DESTINATION and count != 1:
            raise ValueError("Single-destination planning requires one destination")
        if self.planning_mode == PlanningMode.MULTIPLE_DESTINATIONS:
            if count < 2:
                raise ValueError(
                    "Multiple-destination planning requires at least two destinations"
                )
            if count > self.days:
                raise ValueError(
                    "Selected destinations cannot exceed the number of trip days"
                )
        if self.planning_mode == PlanningMode.EXPLORE_TANZANIA and count:
            raise ValueError(
                "Explore Tanzania chooses destinations from interests; "
                "destination_ids must be empty"
            )
        return self


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
    planning_mode: PlanningMode
    title: str
    summary: str
    destinations: list[PlanDestination]
    itinerary: list[ItineraryDay]
    disclaimer: str


class ChatHistoryMessage(BaseModel):
    """One recent display turn; it never carries authority or trusted facts."""

    role: ChatRole
    content: str = Field(min_length=1, max_length=1200)

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        """Normalize bounded context while preserving human-readable text."""

        normalized = value.strip()
        if not normalized:
            raise ValueError("Conversation messages cannot be blank")
        return normalized


class ConciergeChatRequest(BaseModel):
    """A small public chat request bounded for safe catalog discovery."""

    message: str = Field(min_length=2, max_length=500)
    language: ConciergeLanguage = ConciergeLanguage.ENGLISH
    history: list[ChatHistoryMessage] = Field(default_factory=list, max_length=8)

    @field_validator("message")
    @classmethod
    def normalize_message(cls, value: str) -> str:
        """Remove surrounding whitespace before matching catalog content."""

        normalized = value.strip()
        if len(normalized) < 2:
            raise ValueError("Message must contain at least two characters")
        return normalized

    @model_validator(mode="after")
    def bound_total_context(self) -> "ConciergeChatRequest":
        """Prevent individually valid messages from creating unbounded prompts."""

        if sum(len(item.content) for item in self.history) > 6000:
            raise ValueError("Conversation history is too large")
        return self


class ConciergeChatResponse(BaseModel):
    """A bounded answer whose references point to public catalog records."""

    generation_mode: Literal["rule_based_fallback", "local_ollama"]
    intent: ChatIntent
    answer: str = Field(min_length=1, max_length=1600)
    referenced_destinations: list[PlanDestination]
    safety_notice: str | None = None
    follow_up_suggestions: list[str] = Field(default_factory=list, max_length=3)
    booking_destination_id: UUID | None = None
