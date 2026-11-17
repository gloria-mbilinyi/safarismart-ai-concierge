"""Question-specific, catalog-grounded multi-turn concierge responses."""

from __future__ import annotations

import re
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.concierge_provider import (
    ConciergeProviderError,
    ConversationalAnswerProvider,
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


def _context_destination(
    request: ConciergeChatRequest,
    destinations: Sequence[Destination],
) -> Destination | None:
    """Use only known names in recent user turns; ignore assistant instructions."""

    for message in reversed(request.history):
        if message.role != ChatRole.USER:
            continue
        mentioned = _mentioned_destinations(message.content, destinations)
        if mentioned:
            return mentioned[-1]
    return None


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


def _booking_answer(destination: Destination | None, swahili: bool) -> str:
    """Explain the request workflow without implying a reservation."""

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


def _budget_answer(destination: Destination | None, swahili: bool) -> str:
    """Keep budget advice useful while refusing unverified price claims."""

    label = destination.name if destination is not None else "safari yako"
    if swahili:
        return (
            f"SafariSmart haina bei zilizothibitishwa za {label}. Unaweza kuweka "
            "bajeti ya TZS kama muktadha katika mpangaji, lakini mfumo hautakadiria "
            "gharama. Ombi la booking linaweza kukaguliwa na opereta wa majaribio; "
            "nukuu yoyote ya demo si bei ya moja kwa moja."
        )
    label = destination.name if destination is not None else "your trip"
    return (
        f"SafariSmart does not hold verified prices for {label}. You can enter a TZS "
        "budget as planning context, but the planner will not estimate costs. A booking "
        "request can be reviewed by the synthetic operator; any demo quote is not a live price."
    )


def _unsupported_answer(
    destination: Destination | None,
    swahili: bool,
) -> str:
    """Acknowledge catalog gaps instead of filling them with model guesses."""

    label = destination.name if destination is not None else "eneo hilo"
    if swahili:
        return (
            f"Orodha ya SafariSmart haina taarifa hiyo iliyothibitishwa kwa {label}, "
            "kwa hiyo sitabuni jibu. Ninaweza kusaidia kwa maelezo ya eneo, mada za "
            "safari, mpango wa siku, bajeti kama muktadha, au hatua za ombi la booking."
        )
    label = destination.name if destination is not None else "that destination"
    return (
        f"SafariSmart's catalog does not contain that verified information for {label}, "
        "so I will not guess. I can help with catalog descriptions, travel themes, a "
        "day outline, budget as context, or the booking-request steps."
    )


def _suggestions(
    intent: ChatIntent,
    destination: Destination | None,
    swahili: bool,
) -> list[str]:
    """Return short, relevant prompts that do not carry sensitive data."""

    if destination is not None:
        if swahili:
            options = [
                "Naweza kufanya nini huko?",
                "Je, siku tano zinafaa?",
                "Ninawezaje kutuma ombi la booking?",
            ]
        else:
            options = [
                "What can I do there?",
                "Can I visit for five days?",
                "How do I submit a booking request?",
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
    if intent == ChatIntent.BOOKING_GUIDANCE:
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

    if provider is None or intent not in MODEL_ELIGIBLE_INTENTS:
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
    explicit = _mentioned_destinations(request.message, catalog)
    context = _context_destination(request, catalog)
    resolved = explicit[0] if explicit else context
    interests = infer_interests(request.message)
    intent = classify_intent(
        request.message,
        explicit_destination_count=len(explicit),
        has_destination_context=resolved is not None,
        interests=interests,
    )

    references: list[Destination] = []
    booking_destination: Destination | None = None
    if intent == ChatIntent.RECOMMENDATION:
        references = _rank_recommendations(catalog, interests)[:3]
        answer = _recommendation_answer(references, interests, swahili)
    elif intent == ChatIntent.COMPARISON:
        references = list(explicit)
        if context is not None and context not in references:
            references.insert(0, context)
        references = references[:2]
        answer = _comparison_answer(references, swahili)
    elif intent == ChatIntent.ACTIVITIES:
        references = [resolved] if resolved is not None else []
        answer = (
            _activities_answer(resolved, swahili)
            if resolved is not None
            else (
                "Unamaanisha eneo gani katika orodha yetu?"
                if swahili
                else "Which catalog destination do you mean?"
            )
        )
    elif intent == ChatIntent.TRIP_DURATION:
        references = [resolved] if resolved is not None else []
        answer = (
            _duration_answer(
                resolved,
                extract_requested_days(request.message),
                swahili,
            )
            if resolved is not None
            else (
                "Taja eneo kwanza, kisha nitasaidia kupanga siku 1 hadi 14."
                if swahili
                else "Name a destination first, then I can help outline 1 to 14 days."
            )
        )
    elif intent == ChatIntent.BUDGET:
        references = [resolved] if resolved is not None else []
        answer = _budget_answer(resolved, swahili)
    elif intent == ChatIntent.BOOKING_GUIDANCE:
        references = [resolved] if resolved is not None else []
        booking_destination = resolved
        answer = _booking_answer(resolved, swahili)
    elif intent == ChatIntent.UNSUPPORTED_FACT:
        references = [resolved] if resolved is not None else []
        answer = _unsupported_answer(resolved, swahili)
    elif resolved is not None:
        references = [resolved]
        answer = _overview_answer(resolved, swahili)
    else:
        answer = (
            "Niambie eneo au aina ya safari unayopenda—wanyamapori, pwani, mlima, utamaduni, au mazingira."
            if swahili
            else "Tell me a destination or travel interest—wildlife, beach, mountain, culture, or nature."
        )

    reason = (
        "Limetajwa katika mazungumzo haya"
        if swahili
        else "Discussed in this conversation"
    )
    answer, generation_mode = _provider_answer(
        provider,
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
