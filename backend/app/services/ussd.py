"""Deterministic, read-only tourism menus for Africa's Talking USSD callbacks.

Africa's Talking sends cumulative responses separated with ``*``. Every screen
is reconstructed from that text, so no phone numbers or session IDs are stored.
"""

from collections.abc import Sequence
from typing import Protocol


MAX_USSD_INPUT_LENGTH = 120
MAX_DESTINATIONS = 5


class PublicDestination(Protocol):
    """Only public catalog fields are needed; never expose customer records."""

    name: str
    region: str


def _menu_name(name: str) -> str:
    """Shorten long, familiar destination suffixes for small phone screens."""

    return (
        name.replace(" National Park", "")
        .replace(" Conservation Area", "")
        .replace("Mount ", "Mt ")[:28]
    )


def render_ussd(text: str, destinations: Sequence[PublicDestination] = ()) -> str:
    """Render one valid CON/END screen; no side effects or booking lookups."""

    if not text:
        return (
            "CON Welcome to SafariSmart\n"
            "Choose language / Chagua lugha\n"
            "1. English\n"
            "2. Kiswahili"
        )

    if (
        len(text) > MAX_USSD_INPUT_LENGTH
        or any(not segment.isascii() or not segment.isdigit() for segment in text.split("*"))
        or len(text.split("*")) > 3
    ):
        return "END Invalid selection. Dial again to restart."

    parts = text.split("*")
    if parts[0] not in {"1", "2"}:
        return "END Invalid language. Dial again to restart."

    sw = parts[0] == "2"
    if len(parts) == 1:
        if sw:
            return (
                "CON SafariSmart\n"
                "1. Maeneo ya utalii\n"
                "2. Taarifa za booking\n"
                "3. Msaada"
            )
        return (
            "CON SafariSmart\n"
            "1. Explore destinations\n"
            "2. Booking information\n"
            "3. Help"
        )

    category = parts[1]
    if category == "1":
        catalog = list(destinations[:MAX_DESTINATIONS])
        if not catalog:
            return (
                "END Hakuna maeneo ya utalii yaliyopo kwa sasa."
                if sw
                else "END No destinations available yet."
            )
        if len(parts) == 2:
            header = "CON Chagua eneo la utalii" if sw else "CON Choose a destination"
            options = [f"{index}. {_menu_name(item.name)}" for index, item in enumerate(catalog, 1)]
            return "\n".join([header, *options])

        selected = int(parts[2])
        if selected < 1 or selected > len(catalog):
            return "END Chaguo si sahihi. Piga tena." if sw else "END Invalid selection. Dial again."
        destination = catalog[selected - 1]
        return (
            f"END {destination.name}\nMkoa: {destination.region}\n"
            "Taarifa tu; hakuna booking iliyofanyika."
            if sw
            else f"END {destination.name}\nRegion: {destination.region}\n"
            "Information only; no booking was made."
        )

    if len(parts) != 2:
        return "END Chaguo si sahihi. Piga tena." if sw else "END Invalid selection. Dial again."

    if category == "2":
        return (
            "END Booking huchunguzwa na waendeshaji. "
            "Hatutoi hali ya booking kwa USSD bila uthibitisho."
            if sw
            else "END Bookings are operator-reviewed. "
            "Booking status is not available by USSD without verification."
        )
    if category == "3":
        return (
            "END SafariSmart hukusaidia kuchunguza maeneo ya utalii. "
            "Hakuna malipo au booking kupitia USSD hii."
            if sw
            else "END Explore destinations with SafariSmart. "
            "This USSD menu does not take payments or make bookings."
        )
    return "END Chaguo si sahihi. Piga tena." if sw else "END Invalid selection. Dial again."
