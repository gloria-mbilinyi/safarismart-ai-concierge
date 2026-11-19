"""Question-specific, catalog-grounded multi-turn concierge responses."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.concierge_provider import (
    ConciergeProviderError,
    ConversationalAnswerProvider,
)
from app.knowledge.tanzania_regions import (
    TanzaniaRegion,
    find_region_mentions,
    normalize_place_text,
)
from app.models.destination import Destination
from app.models.enums import DestinationCategory
from app.schemas.concierge import (
    ChatIntent,
    ChatRole,
    ConciergeChatRequest,
    ConciergeChatResponse,
    ConciergeLanguage,
    PlanDestination,
    TravelInterest,
)
from app.services.chat_intents import (
    OVERVIEW_CUES,
    classify_intent,
    extract_requested_days,
    has_prompt_injection,
    infer_interests,
)
from app.services.concierge import INTEREST_CATEGORIES


CATEGORY_LABELS = {
    DestinationCategory.BEACH.value: ("coastal destination", "eneo la pwani"),
    DestinationCategory.NATIONAL_PARK.value: ("national park", "hifadhi ya taifa"),
    DestinationCategory.CONSERVATION_AREA.value: (
        "conservation area",
        "eneo la uhifadhi",
    ),
    DestinationCategory.MOUNTAIN.value: ("mountain destination", "eneo la mlima"),
}

SWAHILI_INTEREST_LABELS = {
    "wildlife": "wanyamapori",
    "beach": "pwani",
    "mountain": "milima",
    "culture": "utamaduni",
    "nature": "mazingira",
}

ACTIVITY_THEMES = {
    DestinationCategory.BEACH.value: {
        False: (
            "coastal-landscape discovery",
            "Swahili cultural context",
            "beach and ocean-environment appreciation",
        ),
        True: (
            "kugundua mandhari ya pwani",
            "kujifunza muktadha wa utamaduni wa Kiswahili",
            "kuthamini mazingira ya fukwe na bahari",
        ),
    },
    DestinationCategory.NATIONAL_PARK.value: {
        False: (
            "wildlife-observation themes",
            "landscape and ecosystem learning",
            "responsible nature appreciation",
        ),
        True: (
            "mada za kutazama wanyamapori",
            "kujifunza mandhari na mfumo wa ikolojia",
            "kuthamini mazingira kwa uwajibikaji",
        ),
    },
    DestinationCategory.CONSERVATION_AREA.value: {
        False: (
            "conservation-landscape discovery",
            "wildlife and community context",
            "responsible shared-landscape learning",
        ),
        True: (
            "kugundua mandhari ya uhifadhi",
            "muktadha wa wanyamapori na jamii",
            "kujifunza kwa uwajibikaji katika mandhari ya pamoja",
        ),
    },
    DestinationCategory.MOUNTAIN.value: {
        False: (
            "mountain-environment discovery",
            "ecological-zone learning",
            "ability-aware route preparation",
        ),
        True: (
            "kugundua mazingira ya mlima",
            "kujifunza kanda za ikolojia",
            "maandalizi ya njia yanayozingatia uwezo",
        ),
    },
}

SWAHILI_CATALOG_SUMMARIES = {
    "serengeti-national-park": (
        "hifadhi yenye savana pana, wanyamapori mbalimbali, na mfumo wa "
        "ikolojia wa uhamaji wa msimu"
    ),
    "ngorongoro-conservation-area": (
        "mandhari ya uhifadhi yenye Kreta ya Ngorongoro, wanyamapori, "
        "na jamii za wafugaji"
    ),
    "mount-kilimanjaro": (
        "mlima mrefu zaidi Afrika wenye njia zinazotambulika na kanda "
        "tofauti za ikolojia"
    ),
    "zanzibar": (
        "visiwa vya Bahari ya Hindi vinavyojulikana kwa fukwe, utamaduni "
        "wa Kiswahili, Stone Town ya kihistoria, na mila za viungo"
    ),
    "tarangire-national-park": (
        "hifadhi yenye mandhari za mibuyu, makundi ya tembo, na mfumo wa "
        "ikolojia wa Mto Tarangire"
    ),
}

MODEL_ELIGIBLE_INTENTS = {
    ChatIntent.RECOMMENDATION,
    ChatIntent.DESTINATION_OVERVIEW,
    ChatIntent.ACTIVITIES,
    ChatIntent.TRIP_DURATION,
    ChatIntent.COMPARISON,
}

UNSAFE_MODEL_CLAIMS = (
    "booking is confirmed",
    "reservation is confirmed",
    "booked for you",
    "guaranteed availability",
    "available now",
    "live availability",
    "official partner",
    "partnered with",
    "payment completed",
)

UNVERIFIED_ENTITY_TERMS = (
    " hotel",
    " resort",
    " lodge",
    " airline",
    " tour company",
    " tour operator",
)

CONTEXT_PLACE_WORDS = {
    "there",
    "it",
    "that place",
    "the region",
    "huko",
    "hapo",
    "pale",
    "eneo hilo",
    "mkoa huo",
}
NON_PLACE_SHORT_TURNS = {
    "help",
    "please",
    "thanks",
    "thank you",
    "safari",
    "travel",
    "trip",
    "wildlife",
    "beach",
    "mountain",
    "culture",
    "nature",
    "booking",
    "budget",
}


@dataclass(frozen=True, slots=True)
class ResolvedPlace:
    """A catalog destination or a non-bookable regional discovery profile."""

    destination: Destination | None = None
    region: TanzaniaRegion | None = None

    @property
    def name(self) -> str:
        if self.destination is not None:
            return self.destination.name
        if self.region is not None:
            return self.region.name
        raise ValueError("A resolved place must have a destination or region")

    @property
    def is_bookable_catalog_destination(self) -> bool:
        return self.destination is not None


def _active_destinations(session: Session) -> list[Destination]:
    """Load only public records that may ground a chat response."""

    return list(
        session.scalars(
            select(Destination)
            .where(Destination.is_active.is_(True))
            .order_by(Destination.is_featured.desc(), Destination.name.asc())
        ).all()
    )


def _aliases(destination: Destination) -> set[str]:
    """Build conservative aliases from one trusted catalog name and slug."""

    name = destination.name.casefold()
    aliases = {name, destination.slug.replace("-", " ").casefold()}
    for suffix in (" national park", " conservation area"):
        if name.endswith(suffix):
            aliases.add(name.removesuffix(suffix))
    if name.startswith("mount "):
        aliases.add(name.removeprefix("mount "))
    return {alias for alias in aliases if len(alias) >= 4}


def _mentioned_destinations(
    message: str,
    destinations: Sequence[Destination],
) -> list[Destination]:
    """Resolve explicit known destination names in the order they appear."""

    normalized = message.casefold()
    matches: list[tuple[int, Destination]] = []
    for destination in destinations:
        positions = [
            match.start()
            for alias in _aliases(destination)
            for match in [re.search(rf"\b{re.escape(alias)}\b", normalized)]
            if match is not None
        ]
        if positions:
            matches.append((min(positions), destination))
    return [destination for _, destination in sorted(matches, key=lambda item: item[0])]


def _alias_position(message: str, aliases: Sequence[str]) -> int | None:
    """Return the earliest normalized alias position in a message."""

    normalized = normalize_place_text(message)
    positions = [
        match.start()
        for alias in aliases
        for normalized_alias in [normalize_place_text(alias)]
        for match in [re.search(rf"\b{re.escape(normalized_alias)}\b", normalized)]
        if match is not None
    ]
    return min(positions) if positions else None


def _explicit_places(
    message: str,
    destinations: Sequence[Destination],
) -> list[ResolvedPlace]:
    """Resolve catalog and regional names while preserving their text order."""

    matches: list[tuple[int, int, ResolvedPlace]] = []
    mentioned_destinations = _mentioned_destinations(message, destinations)
    for destination in mentioned_destinations:
        position = _alias_position(message, tuple(_aliases(destination)))
        if position is not None:
            matches.append((position, 0, ResolvedPlace(destination=destination)))

    for region in find_region_mentions(message):
        # The catalog's Mount Kilimanjaro row is the user-facing bookable place;
        # a bare "Kilimanjaro" must retain that established behavior.
        if region.slug == "kilimanjaro" and any(
            destination.slug == "mount-kilimanjaro"
            for destination in mentioned_destinations
        ):
            continue
        position = _alias_position(message, region.all_aliases)
        matches.append(
            (
                position if position is not None else 0,
                1,
                ResolvedPlace(region=region),
            )
        )

    ordered = sorted(matches, key=lambda item: (item[0], item[1]))
    return [place for _, _, place in ordered]


def _context_place(
    request: ConciergeChatRequest,
    destinations: Sequence[Destination],
) -> ResolvedPlace | None:
    """Use only known places in recent user turns; ignore assistant instructions."""

    for message in reversed(request.history):
        if message.role != ChatRole.USER:
            continue
        mentioned = _explicit_places(message.content, destinations)
        if mentioned:
            return mentioned[-1]
    return None


def _looks_like_unknown_location(message: str) -> bool:
    """Detect a new, unrecognized place query without overriding pronoun context."""

    normalized = normalize_place_text(message)
    if any(re.search(rf"\b{re.escape(word)}\b", normalized) for word in CONTEXT_PLACE_WORDS):
        return False
    if any(
        cue in normalized
        for cue in ("dont recognize", "do not recognize", "unknown place", "usilotambua")
    ):
        return True
    if any(cue in normalized for cue in OVERVIEW_CUES):
        generic_follow_ups = {
            "tell me more",
            "more about it",
            "niambie zaidi",
            "maelezo zaidi",
        }
        return normalized not in generic_follow_ups
    words = normalized.split()
    return (
        1 <= len(words) <= 2
        and len(normalized) >= 4
        and normalized not in NON_PLACE_SHORT_TURNS
    )


def _reference(
    destination: Destination,
    *,
    swahili: bool,
    reason: str,
) -> PlanDestination:
    """Serialize only fields loaded from an active catalog row."""

    return PlanDestination(
        id=destination.id,
        name=destination.name,
        slug=destination.slug,
        region=destination.region,
        category=destination.category,
        description=destination.description,
        match_reasons=[reason],
    )


def _rank_recommendations(
    destinations: Sequence[Destination],
    interests: Sequence[TravelInterest],
) -> list[Destination]:
    """Rank by supported interests, then featured state and stable name."""

    def score(destination: Destination) -> tuple[int, int, str]:
        interest_score = sum(
            3
            for interest in interests
            if destination.category in INTEREST_CATEGORIES[interest]
        )
        return (interest_score, 1 if destination.is_featured else 0, destination.name)

    return sorted(destinations, key=score, reverse=True)


def _overview_answer(destination: Destination, swahili: bool) -> str:
    """Introduce one destination with only catalog-backed facts."""

    if swahili:
        summary = SWAHILI_CATALOG_SUMMARIES.get(
            destination.slug,
            f"eneo lililo katika orodha yetu ya {destination.region}",
        )
        return (
            f"{destination.name} iko {destination.region}, Tanzania. Ni {summary}. "
            "Naweza kusaidia kupanga siku zako kwa mada hizi, lakini SafariSmart "
            "haina bei au upatikanaji wa moja kwa moja."
        )
    return (
        f"{destination.name} is in {destination.region}, Tanzania. "
        f"{destination.description} I can help turn those verified catalog themes "
        "into a high-level plan, but SafariSmart does not hold live prices or availability."
    )


def _greeting_answer(swahili: bool) -> str:
    """Welcome a traveller without forcing them through a keyword menu."""

    if swahili:
        return (
            "Habari, karibu SafariSmart! Naweza kukusaidia kugundua mikoa yote 31 "
            "ya Tanzania, vivutio vilivyothibitishwa, au maeneo matano yaliyo kwenye "
            "orodha ya maombi ya booking. Ungependa kutembelea sehemu gani?"
        )
    return (
        "Hi, welcome to SafariSmart! I can help you explore all 31 Tanzanian "
        "regions, source-checked attractions, or the five featured destinations "
        "that accept booking requests. Where would you like to go?"
    )


def _region_overview_answer(region: TanzaniaRegion, swahili: bool) -> str:
    """Introduce a region while keeping discovery separate from booking inventory."""

    if swahili:
        opening = (
            f"{region.name} ni mkoa wa Tanzania katika {region.zone_sw} kwa "
            "mgawanyo wa takwimu wa NBS."
        )
        if not region.highlights:
            return (
                f"{opening} SafariSmart inautambua mkoa huu, lakini bado haina "
                "maelezo ya kivutio yaliyothibitishwa kwa vyanzo. Sitabuni mapendekezo; "
                "niambie kama unapenda mazingira, utamaduni, pwani, mlima, au wanyamapori. "
                "Utambuzi wa mkoa haumaanishi kuwa unaweza kuwekewa booking."
            )
        highlight = region.highlights[0]
        interests = ", ".join(
            SWAHILI_INTEREST_LABELS.get(interest, interest)
            for interest in highlight.interests
        )
        return (
            f"{opening} Sehemu moja iliyothibitishwa ya kuanzia ni {highlight.name}, "
            f"{highlight.summary_sw}. Inafaa kuchunguza mada za {interests}. "
            "Haya ni maelezo ya kugundua eneo, si upatikanaji au booking ya moja kwa moja. "
            "Ungependa kujua shughuli, muda wa safari, au mada gani zaidi?"
        )

    opening = (
        f"{region.name} is a Tanzanian region in the {region.zone_en} in NBS "
        "statistical reporting."
    )
    if not region.highlights:
        return (
            f"{opening} SafariSmart recognizes the region, but its guide does not "
            "yet contain a source-checked attraction profile, so I will not invent "
            "recommendations. Tell me whether you prefer nature, culture, coast, "
            "mountains, or wildlife. Region recognition does not mean it is bookable."
        )
    highlight = region.highlights[0]
    interests = ", ".join(highlight.interests)
    return (
        f"{opening} One verified place to start is {highlight.name}, {highlight.summary_en}. "
        f"It suits {interests} interests. This is regional discovery guidance, not "
        "live availability or a booking listing. Would you like activities, trip-length "
        "ideas, or a particular travel theme?"
    )


def _activities_answer(destination: Destination, swahili: bool) -> str:
    """Describe supported themes without claiming bookable activities."""

    themes = ACTIVITY_THEMES[destination.category][swahili]
    if swahili:
        return (
            f"Kwa {destination.name}, mada salama kutoka kwenye orodha ni "
            f"{', '.join(themes[:-1])}, na {themes[-1]}. Maelezo ya eneo yanasema: "
            f"{SWAHILI_CATALOG_SUMMARIES.get(destination.slug, destination.description)}. "
            "Hatuna ratiba za ziara, saa za kufungua, au upatikanaji wa shughuli, "
            "kwa hiyo hayo yanahitaji kuthibitishwa kando."
        )
    return (
        f"For {destination.name}, useful catalog-grounded themes are "
        f"{', '.join(themes[:-1])}, and {themes[-1]}. The catalog context is: "
        f"{destination.description} SafariSmart does not currently verify tour schedules, "
        "opening hours, or live activity availability."
    )


def _region_activities_answer(region: TanzaniaRegion, swahili: bool) -> str:
    """Offer only activities supported by cited highlights for one region."""

    if not region.highlights:
        if swahili:
            return (
                f"Bado sina shughuli zilizothibitishwa kwa vyanzo katika {region.name}, "
                "kwa hiyo sitabuni orodha. Niambie aina ya safari unayotaka, au uliza "
                "kuhusu mojawapo ya maeneo matano yaliyo kwenye orodha ya SafariSmart."
            )
        return (
            f"I do not yet have source-checked activity detail for {region.name}, so "
            "I will not make up a list. Tell me your travel interest, or ask about one "
            "of SafariSmart's five featured catalog destinations."
        )

    highlight = region.highlights[0]
    activities = highlight.activities_sw if swahili else highlight.activities_en
    if swahili:
        return (
            f"Katika {region.name}, {highlight.name} imethibitishwa kama sehemu ya "
            f"kuanzia. Mada zinazofaa ni {', '.join(activities[:-1])}, na {activities[-1]}. "
            "SafariSmart haina ratiba, ada, saa za kufungua, au upatikanaji wa moja "
            "kwa moja; thibitisha hayo na msimamizi rasmi kabla ya kusafiri."
        )
    return (
        f"In {region.name}, {highlight.name} is a verified starting point. Useful "
        f"themes include {', '.join(activities[:-1])}, and {activities[-1]}. "
        "SafariSmart does not hold live schedules, fees, opening hours, or activity "
        "availability; verify those with the official site before travel."
    )


def _duration_answer(
    destination: Destination,
    days: int | None,
    swahili: bool,
) -> str:
    """Offer a destination-specific day outline within planner limits."""

    if days is None:
        return (
            f"Ungependa kutumia siku ngapi {destination.name}? Mpangaji wetu "
            "anakubali siku 1 hadi 14."
            if swahili
            else f"How many days would you like in {destination.name}? The planner supports 1 to 14 days."
        )
    if not 1 <= days <= 14:
        return (
            "Mpangaji wa SafariSmart anakubali siku 1 hadi 14. Chagua muda ndani ya kiwango hicho."
            if swahili
            else "SafariSmart's planner supports 1 to 14 days. Choose a duration within that range."
        )
    themes = ACTIVITY_THEMES[destination.category][swahili]
    outline = [
        (
            f"Siku ya {day}: {themes[(day - 1) % len(themes)]}"
            if swahili
            else f"Day {day}: {themes[(day - 1) % len(themes)]}"
        )
        for day in range(1, min(days, 5) + 1)
    ]
    remainder = ""
    if days > 5:
        remainder = (
            f" Siku ya 6–{days} zinaweza kuendeleza mada hizi kwa mwendo unaofaa."
            if swahili
            else f" Days 6–{days} can revisit these themes at a suitable pace."
        )
    if swahili:
        return (
            f"Siku {days} zinaweza kuwa muda mzuri wa kupanga {destination.name}. "
            f"Muhtasari wa juu ni: {'; '.join(outline)}.{remainder} Huu si ratiba "
            "yenye muda maalum, bei, au nafasi iliyothibitishwa."
        )
    return (
        f"{days} days can work as a high-level planning window for {destination.name}. "
        f"A grounded outline is: {'; '.join(outline)}.{remainder} This is not a timed "
        "schedule, price, or confirmed reservation."
    )


def _region_duration_answer(
    region: TanzaniaRegion,
    days: int | None,
    swahili: bool,
) -> str:
    """Give a cautious regional planning frame without inventing an itinerary."""

    if days is None:
        return (
            f"Ungependa kutumia siku ngapi {region.name}? Naweza kupanga mada za siku 1 hadi 14."
            if swahili
            else f"How many days would you like in {region.name}? I can outline themes for 1 to 14 days."
        )
    if not 1 <= days <= 14:
        return (
            "Chagua muda wa siku 1 hadi 14."
            if swahili
            else "Choose a duration from 1 to 14 days."
        )
    if not region.highlights:
        return (
            f"Naweza kuweka {days} kama muda wa safari ya {region.name}, lakini sina "
            "shughuli za kutosha zilizothibitishwa kuunda muhtasari wa siku."
            if swahili
            else f"I can use {days} days as the planning window for {region.name}, but "
            "I do not yet have enough source-checked activities to invent a day outline."
        )
    highlight = region.highlights[0]
    activities = highlight.activities_sw if swahili else highlight.activities_en
    outline = [
        (
            f"Siku ya {day}: {activities[(day - 1) % len(activities)]}"
            if swahili
            else f"Day {day}: {activities[(day - 1) % len(activities)]}"
        )
        for day in range(1, min(days, 5) + 1)
    ]
    if swahili:
        return (
            f"Kwa siku {days} katika {region.name}, muhtasari wa kuanzia ni "
            f"{'; '.join(outline)}. Haya ni mawazo ya mada kutoka {highlight.name}, "
            "si ratiba, bei, upatikanaji, au booking iliyothibitishwa."
        )
    return (
        f"For {days} days in {region.name}, a grounded starting outline is "
        f"{'; '.join(outline)}. These are themes from {highlight.name}, not a timed "
        "schedule, price, live availability, or confirmed booking."
    )


def _comparison_answer(destinations: list[Destination], swahili: bool) -> str:
    """Compare only category, region, and description facts in the catalog."""

    if len(destinations) < 2:
        return (
            "Taja maeneo mawili katika orodha yetu ili niyalinganishe."
            if swahili
            else "Name two destinations from the catalog and I can compare their verified themes."
        )
    first, second = destinations[:2]
    if swahili:
        first_label = CATEGORY_LABELS[first.category][1]
        second_label = CATEGORY_LABELS[second.category][1]
        return (
            f"{first.name} ni {first_label} katika {first.region}; "
            f"{SWAHILI_CATALOG_SUMMARIES.get(first.slug, first.description)}. "
            f"{second.name} ni {second_label} katika {second.region}; "
            f"{SWAHILI_CATALOG_SUMMARIES.get(second.slug, second.description)}. "
            "Chaguo linategemea kama unapendelea mada ya kwanza au ya pili; "
            "hii si kulinganisha bei au upatikanaji."
        )
    first_label = CATEGORY_LABELS[first.category][0]
    second_label = CATEGORY_LABELS[second.category][0]
    return (
        f"{first.name} is a {first_label} in {first.region}: {first.description} "
        f"{second.name} is a {second_label} in {second.region}: {second.description} "
        "The useful distinction is their catalog setting and themes, not price or availability."
    )


def _place_comparison_answer(places: list[ResolvedPlace], swahili: bool) -> str:
    """Compare region discovery profiles when the request is not catalog-only."""

    if len(places) < 2:
        return (
            "Taja maeneo mawili ya Tanzania ili niyalinganishe."
            if swahili
            else "Name two Tanzanian places and I can compare their source-checked themes."
        )
    first, second = places[:2]

    def summary(place: ResolvedPlace) -> str:
        if place.destination is not None:
            destination = place.destination
            if swahili:
                return (
                    f"{destination.name} ni {CATEGORY_LABELS[destination.category][1]} "
                    f"katika {destination.region}"
                )
            return (
                f"{destination.name} is a {CATEGORY_LABELS[destination.category][0]} "
                f"in {destination.region}"
            )
        region = place.region
        if region is None:
            raise ValueError("Comparison place is unresolved")
        highlight = region.highlights[0].name if region.highlights else None
        if swahili:
            detail = f"; kivutio kilichothibitishwa ni {highlight}" if highlight else ""
            return f"{region.name} ni mkoa katika {region.zone_sw}{detail}"
        detail = f"; a verified highlight is {highlight}" if highlight else ""
        return f"{region.name} is a region in the {region.zone_en}{detail}"

    if swahili:
        return (
            f"{summary(first)}. {summary(second)}. Huu ni ulinganisho wa mada za "
            "utalii zilizothibitishwa, si bei, upatikanaji, au ushirika wa booking."
        )
    return (
        f"{summary(first)}. {summary(second)}. This compares source-checked travel "
        "themes, not prices, live availability, or booking partnerships."
    )


def _recommendation_answer(
    destinations: list[Destination],
    interests: list[TravelInterest],
    swahili: bool,
) -> str:
    """Explain why each deterministic recommendation matches the question."""

    if not destinations:
        return (
            "Orodha ya maeneo haijajazwa bado."
            if swahili
            else "The destination catalog has not been populated yet."
        )
    interest_text = ", ".join(interest.value for interest in interests)
    entries = [
        f"{destination.name} ({destination.region}, {CATEGORY_LABELS[destination.category][1 if swahili else 0]})"
        for destination in destinations
    ]
    if swahili:
        basis = f" kwa hamu ya {interest_text}" if interest_text else ""
        return (
            f"Kulingana na orodha yetu{basis}, maeneo yanayolingana ni "
            f"{'; '.join(entries)}. Chagua eneo moja ili nikueleze kwa kina, "
            "au tumia hali ya Explore Tanzania kutengeneza mpango."
        )
    basis = f" for {interest_text}" if interest_text else ""
    return (
        f"Based on the active catalog{basis}, useful matches are {'; '.join(entries)}. "
        "Choose one for a focused explanation, or use Explore Tanzania to build a broader plan."
    )


def _booking_answer(place: ResolvedPlace | None, swahili: bool) -> str:
    """Explain the request workflow without implying a reservation."""

    if place is not None and place.region is not None:
        if swahili:
            return (
                f"{place.name} inaelezewa katika mwongozo wa mikoa, lakini si "
                "eneo la booking katika orodha. Maombi yanaweza kutumwa tu kwa maeneo "
                "matano maalumu ya SafariSmart, na hata hapo ombi huanza kama pending "
                "availability—si malipo, nafasi, au reservation halisi."
            )
        return (
            f"{place.name} is covered by the regional discovery guide, but it is not a "
            "bookable catalog record. Booking requests can be submitted only for "
            "SafariSmart's five featured destinations, and even those start as pending "
            "availability—not payment, live inventory, or a real reservation."
        )

    destination = place.destination if place is not None else None
    if swahili:
        label = destination.name if destination is not None else "eneo ulilochagua"
        return (
            f"Naweza kukuongoza kutuma ombi la booking kwa {label}. Chagua tarehe, "
            "idadi ya wasafiri, njia ya mawasiliano, na utoe ridhaa. Ombi huanza "
            "katika hali ya pending availability ili opereta wa majaribio alikague. "
            "Hii haitengenezi malipo, nafasi iliyothibitishwa, au reservation halisi."
        )
    label = destination.name if destination is not None else "your chosen destination"
    return (
        f"I can guide you to submit a booking request for {label}. You choose dates, "
        "party size, contact preference, and consent. The request starts as pending "
        "availability for synthetic operator review; it does not create payment, live "
        "availability, or a confirmed reservation."
    )


def _budget_answer(place: ResolvedPlace | None, swahili: bool) -> str:
    """Keep budget advice useful while refusing unverified price claims."""

    label = place.name if place is not None else "safari yako"
    if swahili:
        return (
            f"SafariSmart haina bei zilizothibitishwa za {label}. Unaweza kuweka "
            "bajeti ya TZS kama muktadha katika mpangaji, lakini mfumo hautakadiria "
            "gharama. Ombi la booking linaweza kukaguliwa na opereta wa majaribio; "
            "nukuu yoyote ya demo si bei ya moja kwa moja."
        )
    label = place.name if place is not None else "your trip"
    return (
        f"SafariSmart does not hold verified prices for {label}. You can enter a TZS "
        "budget as planning context, but the planner will not estimate costs. A booking "
        "request can be reviewed by the synthetic operator; any demo quote is not a live price."
    )


def _unsupported_answer(
    place: ResolvedPlace | None,
    message: str,
    swahili: bool,
) -> str:
    """Acknowledge mutable-data gaps instead of filling them with guesses."""

    label = place.name if place is not None else "eneo hilo"
    normalized = message.casefold()
    hotel_question = any(
        cue in normalized for cue in ("hotel", "accommodation", "lodge", "hoteli", "malazi")
    )
    if swahili:
        if hotel_question:
            return (
                f"SafariSmart haina chanzo cha moja kwa moja cha bei au upatikanaji wa "
                f"hoteli katika {label}, kwa hiyo siwezi kutoa bei ya sasa. Bei hubadilika; "
                "thibitisha na mtoa huduma kabla ya kulipa. Naweza bado kusaidia kwa "
                "maelezo ya eneo na shughuli zilizothibitishwa."
            )
        return (
            f"SafariSmart haina taarifa hiyo ya sasa iliyothibitishwa kwa {label}, "
            "kwa hiyo sitabuni jibu. Ninaweza kusaidia kwa maelezo ya eneo, mada za "
            "safari, mpango wa siku, bajeti kama muktadha, au hatua za ombi la booking."
        )
    label = place.name if place is not None else "that destination"
    if hotel_question:
        return (
            f"SafariSmart does not have a verified live hotel-pricing or availability "
            f"feed for {label}, so I cannot quote a current rate. Prices change; verify "
            "directly with a provider before paying. I can still help with source-checked "
            "regional context and activities."
        )
    return (
        f"SafariSmart does not contain that verified live information for {label}, "
        "so I will not guess. I can help with catalog descriptions, travel themes, a "
        "day outline, budget as context, or the booking-request steps."
    )


def _unknown_location_answer(swahili: bool) -> str:
    """Be honest about an unresolved place and offer a concrete recovery path."""

    if swahili:
        return (
            "Sijatambua eneo hilo kwa uhakika katika mwongozo wa mikoa 31 ya Tanzania "
            "au orodha ya maeneo matano ya booking. Sitabuni maelezo. Tafadhali andika "
            "jina la mkoa au jiji—kwa mfano Mwanza, Mbeya, Arusha, au Dar es Salaam."
        )
    return (
        "I could not confidently match that place to SafariSmart's guide to Tanzania's "
        "31 regions or its five featured booking destinations, so I will not invent "
        "details. Try the region or city name—for example Mwanza, Mbeya, Arusha, or Dar es Salaam."
    )


def _clarification_answer(swahili: bool) -> str:
    """Invite a natural next turn without repeating the old keyword-menu response."""

    if swahili:
        return (
            "Naweza kusaidia kugundua mkoa wowote wa Tanzania au kueleza maeneo matano "
            "ya booking. Unaweza kuuliza “Niambie kuhusu Mwanza” au kutaja aina ya safari unayotaka."
        )
    return (
        "I can help explore any Tanzanian region or explain the five featured booking "
        "destinations. Try “Tell me about Mwanza,” or describe the kind of trip you have in mind."
    )


def _suggestions(
    intent: ChatIntent,
    place: ResolvedPlace | None,
    swahili: bool,
) -> list[str]:
    """Return short, relevant prompts that do not carry sensitive data."""

    if place is not None:
        if swahili:
            options = [
                "Naweza kufanya nini huko?",
                "Je, siku tano zinafaa?",
                (
                    "Ninawezaje kutuma ombi la booking?"
                    if place.is_bookable_catalog_destination
                    else "Ni maeneo gani yanapokea maombi ya booking?"
                ),
            ]
        else:
            options = [
                "What can I do there?",
                "Can I visit for five days?",
                (
                    "How do I submit a booking request?"
                    if place.is_bookable_catalog_destination
                    else "Which places accept booking requests?"
                ),
            ]
    elif swahili:
        options = [
            "Niambie kuhusu Zanzibar",
            "Pendekeza eneo la wanyamapori",
            "Linganisha pwani na mlima",
        ]
    else:
        options = [
            "Tell me about Zanzibar",
            "Recommend a wildlife destination",
            "Compare a beach and mountain trip",
        ]
    if intent in {ChatIntent.BOOKING_GUIDANCE, ChatIntent.GREETING}:
        return options[:2]
    return options


def _provider_answer(
    provider: ConversationalAnswerProvider | None,
    *,
    request: ConciergeChatRequest,
    intent: ChatIntent,
    safe_draft: str,
    references: list[Destination],
    catalog: list[Destination],
) -> tuple[str, str]:
    """Accept optional prose only when it preserves the grounded boundary."""

    if (
        provider is None
        or intent not in MODEL_ELIGIBLE_INTENTS
        or (intent != ChatIntent.RECOMMENDATION and not references)
    ):
        return safe_draft, "rule_based_fallback"
    answer_method = getattr(provider, "answer_question", None)
    if not callable(answer_method):
        return safe_draft, "rule_based_fallback"

    trusted_facts = [
        {
            "name": destination.name,
            "region": destination.region,
            "category": destination.category,
            "description": destination.description,
        }
        for destination in references
    ]
    try:
        candidate = answer_method(
            user_message=request.message,
            language=request.language.value,
            intent=intent.value,
            trusted_facts=trusted_facts,
            safe_draft=safe_draft,
            known_destination_names=[destination.name for destination in catalog],
        )
    except (ConciergeProviderError, TimeoutError, OSError, TypeError, ValueError):
        return safe_draft, "rule_based_fallback"

    if not isinstance(candidate, str):
        return safe_draft, "rule_based_fallback"
    candidate = candidate.strip()
    normalized = candidate.casefold()
    if not 20 <= len(candidate) <= 1600:
        return safe_draft, "rule_based_fallback"
    if any(claim in normalized for claim in UNSAFE_MODEL_CLAIMS):
        return safe_draft, "rule_based_fallback"
    if any(term in normalized for term in UNVERIFIED_ENTITY_TERMS):
        return safe_draft, "rule_based_fallback"
    candidate_numbers = set(re.findall(r"\b\d[\d,.]*\b", candidate))
    draft_numbers = set(re.findall(r"\b\d[\d,.]*\b", safe_draft))
    if not candidate_numbers <= draft_numbers:
        return safe_draft, "rule_based_fallback"
    allowed_ids = {destination.id for destination in references}
    if any(
        any(
            re.search(rf"\b{re.escape(alias)}\b", normalized)
            for alias in _aliases(destination)
        )
        and destination.id not in allowed_ids
        for destination in catalog
    ):
        return safe_draft, "rule_based_fallback"
    if references and not any(
        re.search(rf"\b{re.escape(alias)}\b", normalized)
        for destination in references
        for alias in _aliases(destination)
    ):
        return safe_draft, "rule_based_fallback"
    return candidate, "local_ollama"


def chat_about_destinations(
    session: Session,
    request: ConciergeChatRequest,
    provider: ConversationalAnswerProvider | None = None,
) -> ConciergeChatResponse:
    """Answer the actual question using bounded context and trusted catalog rows."""

    swahili = request.language == ConciergeLanguage.SWAHILI
    if has_prompt_injection(request.message):
        return ConciergeChatResponse(
            generation_mode="rule_based_fallback",
            intent=ChatIntent.CLARIFICATION,
            answer=(
                "Naweza kusaidia tu kwa taarifa salama za maeneo katika orodha ya SafariSmart."
                if swahili
                else "I can help only with safe destination information in SafariSmart's catalog."
            ),
            referenced_destinations=[],
            safety_notice=(
                "Maelekezo yasiyohusiana na upangaji salama wa safari yamepuuzwa."
                if swahili
                else "Instructions unrelated to safe trip planning were ignored."
            ),
            follow_up_suggestions=_suggestions(
                ChatIntent.CLARIFICATION, None, swahili
            ),
        )

    catalog = _active_destinations(session)
    explicit_places = _explicit_places(request.message, catalog)
    unknown_location = not explicit_places and _looks_like_unknown_location(
        request.message
    )
    # A new unknown place question must not inherit the preceding destination.
    context = None if unknown_location else _context_place(request, catalog)
    resolved = explicit_places[-1] if explicit_places else context
    interests = infer_interests(request.message)
    intent = classify_intent(
        request.message,
        explicit_destination_count=len(explicit_places),
        has_destination_context=resolved is not None,
        interests=interests,
        unknown_location=unknown_location,
    )
    if intent == ChatIntent.DESTINATION_OVERVIEW and resolved is not None and resolved.region:
        intent = ChatIntent.REGION_OVERVIEW

    references: list[Destination] = []
    booking_destination: Destination | None = None
    uses_regional_knowledge = False
    if intent == ChatIntent.GREETING:
        answer = _greeting_answer(swahili)
    elif intent == ChatIntent.RECOMMENDATION:
        references = _rank_recommendations(catalog, interests)[:3]
        answer = _recommendation_answer(references, interests, swahili)
    elif intent == ChatIntent.COMPARISON:
        comparison_places = list(explicit_places)
        if len(comparison_places) < 2 and context is not None and all(
            place.name != context.name for place in comparison_places
        ):
            comparison_places.insert(0, context)
        comparison_places = comparison_places[:2]
        references = [
            place.destination
            for place in comparison_places
            if place.destination is not None
        ]
        uses_regional_knowledge = any(
            place.region is not None for place in comparison_places
        )
        answer = (
            _place_comparison_answer(comparison_places, swahili)
            if uses_regional_knowledge
            else _comparison_answer(references, swahili)
        )
    elif intent == ChatIntent.ACTIVITIES:
        if resolved is not None and resolved.destination is not None:
            references = [resolved.destination]
            answer = _activities_answer(resolved.destination, swahili)
        elif resolved is not None and resolved.region is not None:
            uses_regional_knowledge = True
            answer = _region_activities_answer(resolved.region, swahili)
        else:
            answer = (
                "Unamaanisha mkoa au eneo gani la Tanzania?"
                if swahili
                else "Which Tanzanian region or destination do you mean?"
            )
    elif intent == ChatIntent.TRIP_DURATION:
        days = extract_requested_days(request.message)
        if resolved is not None and resolved.destination is not None:
            references = [resolved.destination]
            answer = _duration_answer(resolved.destination, days, swahili)
        elif resolved is not None and resolved.region is not None:
            uses_regional_knowledge = True
            answer = _region_duration_answer(resolved.region, days, swahili)
        else:
            answer = (
                "Taja eneo kwanza, kisha nitasaidia kupanga siku 1 hadi 14."
                if swahili
                else "Name a place first, then I can help outline 1 to 14 days."
            )
    elif intent == ChatIntent.BUDGET:
        if resolved is not None and resolved.destination is not None:
            references = [resolved.destination]
        uses_regional_knowledge = resolved is not None and resolved.region is not None
        answer = _budget_answer(resolved, swahili)
    elif intent == ChatIntent.BOOKING_GUIDANCE:
        if resolved is not None and resolved.destination is not None:
            references = [resolved.destination]
            booking_destination = resolved.destination
        uses_regional_knowledge = resolved is not None and resolved.region is not None
        answer = _booking_answer(resolved, swahili)
    elif intent == ChatIntent.UNSUPPORTED_FACT:
        if resolved is not None and resolved.destination is not None:
            references = [resolved.destination]
        uses_regional_knowledge = resolved is not None and resolved.region is not None
        answer = _unsupported_answer(resolved, request.message, swahili)
    elif intent == ChatIntent.UNKNOWN_LOCATION:
        answer = _unknown_location_answer(swahili)
    elif resolved is not None and resolved.destination is not None:
        references = [resolved.destination]
        answer = _overview_answer(resolved.destination, swahili)
    elif resolved is not None and resolved.region is not None:
        uses_regional_knowledge = True
        answer = _region_overview_answer(resolved.region, swahili)
    else:
        answer = _clarification_answer(swahili)

    reason = (
        "Limetajwa katika mazungumzo haya"
        if swahili
        else "Discussed in this conversation"
    )
    answer, generation_mode = _provider_answer(
        None if uses_regional_knowledge else provider,
        request=request,
        intent=intent,
        safe_draft=answer,
        references=references,
        catalog=catalog,
    )
    return ConciergeChatResponse(
        generation_mode=generation_mode,
        intent=intent,
        answer=answer,
        referenced_destinations=[
            _reference(destination, swahili=swahili, reason=reason)
            for destination in references
        ],
        follow_up_suggestions=_suggestions(intent, resolved, swahili),
        booking_destination_id=(
            booking_destination.id if booking_destination is not None else None
        ),
    )
