"""Bounded bilingual intent recognition for Tanzania travel chat."""

from __future__ import annotations

import re

from app.schemas.concierge import ChatIntent, TravelInterest


INJECTION_MARKERS = (
    "ignore previous",
    "ignore all",
    "system prompt",
    "developer message",
    "reveal prompt",
    "show your instructions",
    "act as system",
    "bypass",
    "jailbreak",
)

GREETING_CUES = {
    "hello",
    "hi",
    "hey",
    "jambo",
    "habari",
    "mambo",
    "shikamoo",
    "good morning",
    "good afternoon",
    "good evening",
}

INTEREST_KEYWORDS: dict[TravelInterest, tuple[str, ...]] = {
    TravelInterest.WILDLIFE: (
        "wildlife",
        "safari",
        "animals",
        "migration",
        "wanyama",
        "wanyamapori",
        "pori",
    ),
    TravelInterest.BEACH: (
        "beach",
        "beaches",
        "ocean",
        "island",
        "coast",
        "pwani",
        "bahari",
        "fukwe",
    ),
    TravelInterest.MOUNTAIN: (
        "mountain",
        "climb",
        "trek",
        "kilimanjaro",
        "mlima",
        "kupanda",
    ),
    TravelInterest.CULTURE: (
        "culture",
        "history",
        "community",
        "heritage",
        "utamaduni",
        "historia",
        "jamii",
    ),
    TravelInterest.NATURE: (
        "nature",
        "landscape",
        "ecosystem",
        "mazingira",
        "mandhari",
        "ikolojia",
    ),
}

COMPARISON_CUES = (
    "compare",
    "comparison",
    "versus",
    " vs ",
    "difference",
    "which is better",
    "linganisha",
    "tofauti",
)
ACTIVITY_CUES = (
    "what can i do",
    "things to do",
    "activities",
    "activity",
    "experience there",
    "enjoy there",
    "nifanye nini",
    "naweza kufanya nini",
    "shughuli",
    "kufurahia",
)
DURATION_CUES = (
    "how many days",
    "how long",
    "days",
    "day trip",
    "itinerary",
    "siku",
    "muda gani",
    "ratiba",
)
BUDGET_CUES = (
    "budget",
    "cost",
    "price",
    "afford",
    "cheap",
    "expensive",
    "tzs",
    "bajeti",
    "gharama",
    "bei",
    "nafuu",
)
BOOKING_CUES = (
    "book",
    "booking",
    "reserve",
    "reservation",
    "request a trip",
    "kuweka nafasi",
    "kuhifadhi",
    "ombi la safari",
)
RECOMMENDATION_CUES = (
    "recommend",
    "suggest",
    "where should",
    "which destination",
    "where can",
    "looking for",
    "pendekeza",
    "niende wapi",
    "eneo gani",
)
OVERVIEW_CUES = (
    "tell me about",
    "what is",
    "want to visit",
    "interested in visiting",
    "more about",
    "niambie kuhusu",
    "nataka kutembelea",
    "nataka kwenda",
    "maelezo kuhusu",
)
UNSUPPORTED_FACT_CUES = (
    "weather",
    "forecast",
    "visa",
    "vaccine",
    "vaccination",
    "hotel",
    "accommodation",
    "lodge",
    "flight",
    "transport",
    "travel time",
    "drive time",
    "opening hours",
    "crime",
    "medical",
    "hali ya hewa",
    "utabiri",
    "chanjo",
    "malazi",
    "hoteli",
    "usafiri",
    "muda wa safari",
    "saa za kufungua",
)

NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "moja": 1,
    "mbili": 2,
    "tatu": 3,
    "nne": 4,
    "tano": 5,
    "sita": 6,
    "saba": 7,
    "nane": 8,
    "tisa": 9,
    "kumi": 10,
}


def contains_any(message: str, cues: tuple[str, ...]) -> bool:
    """Match a small transparent phrase set against normalized text."""

    return any(cue in message for cue in cues)


def has_prompt_injection(message: str) -> bool:
    """Detect common attempts to replace the concierge's safety boundary."""

    normalized = message.casefold()
    return contains_any(normalized, INJECTION_MARKERS)


def is_greeting(message: str) -> bool:
    """Recognize a greeting-only turn without swallowing a travel question."""

    normalized = re.sub(r"[^a-z\s]", " ", message.casefold())
    normalized = re.sub(r"\s+", " ", normalized).strip()
    polite_suffixes = ("there", "safarismart", "please", "tafadhali")
    if normalized in GREETING_CUES:
        return True
    return any(
        normalized == f"{greeting} {suffix}"
        for greeting in GREETING_CUES
        for suffix in polite_suffixes
    )


def infer_interests(message: str) -> list[TravelInterest]:
    """Return only supported interest labels found through known keywords."""

    normalized = message.casefold()
    return [
        interest
        for interest, keywords in INTEREST_KEYWORDS.items()
        if contains_any(normalized, keywords)
    ]


def extract_requested_days(message: str) -> int | None:
    """Extract a bounded natural-language day count without executing text."""

    normalized = message.casefold()
    numeric = re.search(r"\b(\d{1,2})\s*(?:day|days|siku)\b", normalized)
    if numeric:
        return int(numeric.group(1))
    for word, value in NUMBER_WORDS.items():
        if re.search(rf"\b{re.escape(word)}\s+(?:day|days|siku)\b", normalized):
            return value
    return None


def classify_intent(
    message: str,
    *,
    explicit_destination_count: int,
    has_destination_context: bool,
    interests: list[TravelInterest],
    unknown_location: bool = False,
) -> ChatIntent:
    """Choose one supported intent in deterministic priority order."""

    normalized = message.casefold()
    if is_greeting(normalized):
        return ChatIntent.GREETING
    if unknown_location:
        return ChatIntent.UNKNOWN_LOCATION
    if contains_any(normalized, COMPARISON_CUES):
        return ChatIntent.COMPARISON
    if contains_any(normalized, BOOKING_CUES):
        return ChatIntent.BOOKING_GUIDANCE
    if contains_any(normalized, ACTIVITY_CUES):
        return ChatIntent.ACTIVITIES
    if contains_any(normalized, DURATION_CUES) or extract_requested_days(normalized):
        return ChatIntent.TRIP_DURATION
    if contains_any(normalized, UNSUPPORTED_FACT_CUES):
        return ChatIntent.UNSUPPORTED_FACT
    if contains_any(normalized, BUDGET_CUES):
        return ChatIntent.BUDGET
    if contains_any(normalized, RECOMMENDATION_CUES):
        return ChatIntent.RECOMMENDATION
    if explicit_destination_count or has_destination_context:
        return ChatIntent.DESTINATION_OVERVIEW
    if interests:
        return ChatIntent.RECOMMENDATION
    if contains_any(normalized, OVERVIEW_CUES):
        return ChatIntent.UNKNOWN_LOCATION
    return ChatIntent.CLARIFICATION
