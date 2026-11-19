"""Verified, maintainable discovery data for Tanzania's 31 regions.

This module is deliberately separate from the database-backed destination catalog.
Recognition here never means that a region has inventory, an operator assignment,
or a booking route. Administrative names and statistical zones were checked against
Tanzania's 2022 census publications; attraction summaries use the source recorded on
each highlight.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date


NBS_REGION_SOURCE = (
    "https://www.nbs.go.tz/nbs/takwimu/Census2022/"
    "Administrative_units_Population_Distribution_Report_Tanzania_volume1a.pdf"
)
NBS_ZONE_SOURCE = (
    "https://www.nbs.go.tz/uploads/statistics/documents/"
    "en-1705490101-Tanzania_DHS-MIS_2022_Summary_Report_English_and_Swahili.pdf"
)
VERIFIED_ON = date(2026, 11, 19)


@dataclass(frozen=True, slots=True)
class TourismHighlight:
    """One attraction summary whose mutable details are intentionally excluded."""

    name: str
    summary_en: str
    summary_sw: str
    activities_en: tuple[str, ...]
    activities_sw: tuple[str, ...]
    interests: tuple[str, ...]
    source_url: str


@dataclass(frozen=True, slots=True)
class TanzaniaRegion:
    """Read-only regional discovery profile, never a bookable catalog record."""

    name: str
    slug: str
    zone_en: str
    zone_sw: str
    aliases: tuple[str, ...] = ()
    highlights: tuple[TourismHighlight, ...] = ()
    source_urls: tuple[str, ...] = (NBS_REGION_SOURCE, NBS_ZONE_SOURCE)
    verified_on: date = VERIFIED_ON

    @property
    def all_aliases(self) -> tuple[str, ...]:
        """Return the official name plus curated common names without duplicates."""

        return tuple(dict.fromkeys((self.name, *self.aliases)))


def _highlight(
    name: str,
    summary_en: str,
    summary_sw: str,
    activities_en: tuple[str, ...],
    activities_sw: tuple[str, ...],
    interests: tuple[str, ...],
    source_url: str,
) -> TourismHighlight:
    return TourismHighlight(
        name=name,
        summary_en=summary_en,
        summary_sw=summary_sw,
        activities_en=activities_en,
        activities_sw=activities_sw,
        interests=interests,
        source_url=source_url,
    )


SAANANE = _highlight(
    "Saanane Island National Park",
    "a protected island in Mwanza on Lake Victoria with walking trails, viewpoints, birdlife, and wildlife",
    "kisiwa kilichohifadhiwa jijini Mwanza katika Ziwa Victoria chenye njia za kutembea, sehemu za kutazama mandhari, ndege, na wanyamapori",
    ("walking trails", "birdwatching", "Lake Victoria viewpoints"),
    ("kutembea kwenye njia", "kutazama ndege", "kutazama mandhari ya Ziwa Victoria"),
    ("wildlife", "nature"),
    "https://www.tanzaniaparks.go.tz/nationalparks/saanane",
)
ARUSHA_PARK = _highlight(
    "Arusha National Park",
    "a northern park with Mount Meru, Ngurdoto Crater, Momella Lakes, forest, savannah, and birdlife",
    "hifadhi ya kaskazini yenye Mlima Meru, Kreta ya Ngurdoto, Maziwa ya Momella, misitu, savana, na ndege",
    ("wildlife viewing", "walking", "birdwatching"),
    ("kutazama wanyamapori", "kutembea", "kutazama ndege"),
    ("wildlife", "mountain", "nature"),
    "https://www.tanzaniaparks.go.tz/nationalparks/arusha",
)
KILIMANJARO_PARK = _highlight(
    "Kilimanjaro National Park",
    "the protected mountain landscape around Mount Kilimanjaro, with distinct ecological zones",
    "mandhari ya mlima iliyohifadhiwa inayozunguka Mlima Kilimanjaro, yenye kanda tofauti za ikolojia",
    ("mountain trekking themes", "ecological-zone learning", "nature appreciation"),
    ("mada za kupanda mlima", "kujifunza kanda za ikolojia", "kuthamini mazingira"),
    ("mountain", "nature"),
    "https://www.tanzaniaparks.go.tz/nationalparks/kilimanjaro",
)
DAR_MARINE = _highlight(
    "Dar es Salaam Marine Reserves",
    "a protected marine system including islands such as Bongoyo and Mbudya, with reefs, fish, and birdlife",
    "mfumo wa maeneo tengefu ya bahari unaojumuisha visiwa kama Bongoyo na Mbudya, pamoja na miamba ya matumbawe, samaki, na ndege",
    ("marine-nature learning", "birdwatching", "reef appreciation"),
    ("kujifunza mazingira ya bahari", "kutazama ndege", "kuthamini miamba ya matumbawe"),
    ("beach", "nature"),
    "https://www.marineparks.go.tz/index.php/pages/marine-reserves",
)
KONDOA = _highlight(
    "Kondoa Rock-Art Sites",
    "a UNESCO World Heritage property in Dodoma Region with rock paintings across natural shelters",
    "eneo la Urithi wa Dunia la UNESCO katika Mkoa wa Dodoma lenye michoro ya miambani katika makazi ya asili",
    ("heritage learning", "rock-art interpretation", "landscape appreciation"),
    ("kujifunza urithi", "kutafsiri sanaa ya miambani", "kuthamini mandhari"),
    ("culture", "nature"),
    "https://whc.unesco.org/en/list/1183/",
)
MBEYA_NATURE = _highlight(
    "Lake Ngozi and Mount Rungwe",
    "verified Mbeya Region nature sites including Lake Ngozi crater lake and Mount Rungwe",
    "maeneo ya asili yaliyothibitishwa katika Mkoa wa Mbeya, yakiwemo Ziwa la Kreta Ngozi na Mlima Rungwe",
    ("hiking themes", "crater-lake scenery", "highland nature"),
    ("mada za matembezi", "mandhari ya ziwa la kreta", "mazingira ya nyanda za juu"),
    ("mountain", "nature"),
    "https://mbeya.go.tz/storage/app/uploads/public/5df/885/0ff/5df8850ff1e51431088709.pdf",
)
MIKUMI = _highlight(
    "Mikumi National Park",
    "a national park known for the Mkata Floodplain, wildlife, birdlife, and savannah landscapes",
    "hifadhi ya taifa inayojulikana kwa Tambarare za Mkata, wanyamapori, ndege, na mandhari ya savana",
    ("wildlife viewing", "birdwatching", "savannah learning"),
    ("kutazama wanyamapori", "kutazama ndege", "kujifunza savana"),
    ("wildlife", "nature"),
    "https://www.tanzaniaparks.go.tz/nationalparks/mikumi",
)
TANGA_MARINE = _highlight(
    "Tanga Coelacanth Marine Park",
    "one of the marine parks managed by Tanzania's Marine Parks and Reserves Unit",
    "mojawapo ya hifadhi za bahari zinazosimamiwa na Kitengo cha Hifadhi za Bahari na Maeneo Tengefu Tanzania",
    ("marine-conservation learning", "coastal nature", "responsible marine discovery"),
    ("kujifunza uhifadhi wa bahari", "mazingira ya pwani", "kugundua bahari kwa uwajibikaji"),
    ("beach", "nature"),
    "https://www.marineparks.go.tz/pages/marine-history",
)
RUAHA = _highlight(
    "Ruaha National Park",
    "a large park with river, hill, baobab, wildlife, and birdlife landscapes",
    "hifadhi kubwa yenye mandhari ya mto, vilima, mibuyu, wanyamapori, na ndege",
    ("wildlife viewing", "birdwatching", "landscape appreciation"),
    ("kutazama wanyamapori", "kutazama ndege", "kuthamini mandhari"),
    ("wildlife", "nature"),
    "https://www.tanzaniaparks.go.tz/nationalparks/ruaha",
)
GOMBE = _highlight(
    "Gombe National Park",
    "a protected landscape on Lake Tanganyika known for chimpanzees and long-running research",
    "mandhari iliyohifadhiwa katika Ziwa Tanganyika inayojulikana kwa sokwe na utafiti wa muda mrefu",
    ("chimpanzee-trekking themes", "birdwatching", "Lake Tanganyika scenery"),
    ("mada za kufuatilia sokwe", "kutazama ndege", "mandhari ya Ziwa Tanganyika"),
    ("wildlife", "nature"),
    "https://www.tanzaniaparks.go.tz/nationalparks/gombe",
)
STONE_TOWN = _highlight(
    "Stone Town of Zanzibar",
    "a UNESCO-listed historic Swahili coastal trading town on Unguja",
    "mji wa kihistoria wa biashara wa pwani ya Waswahili katika Unguja ulioorodheshwa na UNESCO",
    ("heritage learning", "historic townscape appreciation", "Swahili cultural context"),
    ("kujifunza urithi", "kuthamini mandhari ya mji wa kihistoria", "muktadha wa utamaduni wa Kiswahili"),
    ("culture", "beach"),
    "https://whc.unesco.org/en/list/173",
)


def _region(
    name: str,
    slug: str,
    zone_en: str,
    zone_sw: str,
    *,
    aliases: tuple[str, ...] = (),
    highlights: tuple[TourismHighlight, ...] = (),
) -> TanzaniaRegion:
    extra_sources = tuple(item.source_url for item in highlights)
    return TanzaniaRegion(
        name=name,
        slug=slug,
        zone_en=zone_en,
        zone_sw=zone_sw,
        aliases=aliases,
        highlights=highlights,
        source_urls=tuple(dict.fromkeys((NBS_REGION_SOURCE, NBS_ZONE_SOURCE, *extra_sources))),
    )


TANZANIA_REGIONS: tuple[TanzaniaRegion, ...] = (
    _region("Arusha", "arusha", "Northern Zone", "Kanda ya Kaskazini", aliases=("Arusha City",), highlights=(ARUSHA_PARK,)),
    _region("Dar es Salaam", "dar-es-salaam", "Eastern Zone", "Kanda ya Mashariki", aliases=("Dar", "Dar es Salam", "Dar City"), highlights=(DAR_MARINE,)),
    _region("Dodoma", "dodoma", "Central Zone", "Kanda ya Kati", aliases=("Dodoma City",), highlights=(KONDOA,)),
    _region("Geita", "geita", "Lake Zone", "Kanda ya Ziwa"),
    _region("Iringa", "iringa", "Southern Highlands Zone", "Kanda ya Nyanda za Juu Kusini", aliases=("Iringa City",), highlights=(RUAHA,)),
    _region("Kagera", "kagera", "Lake Zone", "Kanda ya Ziwa", aliases=("Bukoba",)),
    _region("Katavi", "katavi", "Southwest Highlands Zone", "Kanda ya Nyanda za Juu Kusini Magharibi", aliases=("Mpanda",)),
    _region("Kigoma", "kigoma", "Western Zone", "Kanda ya Magharibi", aliases=("Kigoma Ujiji", "Kigoma-Ujiji"), highlights=(GOMBE,)),
    _region("Kilimanjaro", "kilimanjaro", "Northern Zone", "Kanda ya Kaskazini", aliases=("Moshi", "Moshi Town"), highlights=(KILIMANJARO_PARK,)),
    _region("Lindi", "lindi", "Southern Zone", "Kanda ya Kusini"),
    _region("Manyara", "manyara", "Central Zone", "Kanda ya Kati", aliases=("Babati",)),
    _region("Mara", "mara", "Lake Zone", "Kanda ya Ziwa", aliases=("Musoma",)),
    _region("Mbeya", "mbeya", "Southwest Highlands Zone", "Kanda ya Nyanda za Juu Kusini Magharibi", aliases=("Mbeya City",), highlights=(MBEYA_NATURE,)),
    _region("Morogoro", "morogoro", "Eastern Zone", "Kanda ya Mashariki", aliases=("Morogoro Town",), highlights=(MIKUMI,)),
    _region("Mtwara", "mtwara", "Southern Zone", "Kanda ya Kusini"),
    _region("Mwanza", "mwanza", "Lake Zone", "Kanda ya Ziwa", aliases=("Mwanza City",), highlights=(SAANANE,)),
    _region("Njombe", "njombe", "Southern Highlands Zone", "Kanda ya Nyanda za Juu Kusini"),
    _region("Pwani", "pwani", "Eastern Zone", "Kanda ya Mashariki", aliases=("Coast Region", "Coast")),
    _region("Rukwa", "rukwa", "Southwest Highlands Zone", "Kanda ya Nyanda za Juu Kusini Magharibi", aliases=("Sumbawanga",)),
    _region("Ruvuma", "ruvuma", "Southern Highlands Zone", "Kanda ya Nyanda za Juu Kusini", aliases=("Songea",)),
    _region("Shinyanga", "shinyanga", "Lake Zone", "Kanda ya Ziwa"),
    _region("Simiyu", "simiyu", "Lake Zone", "Kanda ya Ziwa", aliases=("Bariadi",)),
    _region("Singida", "singida", "Central Zone", "Kanda ya Kati"),
    _region("Songwe", "songwe", "Southwest Highlands Zone", "Kanda ya Nyanda za Juu Kusini Magharibi", aliases=("Vwawa",)),
    _region("Tabora", "tabora", "Western Zone", "Kanda ya Magharibi"),
    _region("Tanga", "tanga", "Eastern Zone", "Kanda ya Mashariki", aliases=("Tanga City",), highlights=(TANGA_MARINE,)),
    _region("Kaskazini Pemba", "kaskazini-pemba", "Zanzibar", "Zanzibar", aliases=("North Pemba", "Pemba North", "Wete")),
    _region("Kusini Pemba", "kusini-pemba", "Zanzibar", "Zanzibar", aliases=("South Pemba", "Pemba South", "Chake Chake")),
    _region("Kaskazini Unguja", "kaskazini-unguja", "Zanzibar", "Zanzibar", aliases=("North Unguja", "Unguja North")),
    _region("Kusini Unguja", "kusini-unguja", "Zanzibar", "Zanzibar", aliases=("South Unguja", "Unguja South")),
    _region("Mjini Magharibi", "mjini-magharibi", "Zanzibar", "Zanzibar", aliases=("Urban West", "Zanzibar City", "Stone Town"), highlights=(STONE_TOWN,)),
)


def normalize_place_text(value: str) -> str:
    """Normalize punctuation and accents while retaining word boundaries."""

    decomposed = unicodedata.normalize("NFKD", value.casefold())
    ascii_text = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", ascii_text).strip()


def _edit_distance(first: str, second: str) -> int:
    """Return a small Levenshtein distance without adding a runtime dependency."""

    if first == second:
        return 0
    if abs(len(first) - len(second)) > 1:
        return 2
    previous = list(range(len(second) + 1))
    for row, left in enumerate(first, start=1):
        current = [row]
        for column, right in enumerate(second, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[column] + 1,
                    previous[column - 1] + (left != right),
                )
            )
        previous = current
    return previous[-1]


def find_region_mentions(message: str) -> list[TanzaniaRegion]:
    """Resolve exact aliases first, then conservative one-character misspellings."""

    normalized = normalize_place_text(message)
    exact: list[tuple[int, TanzaniaRegion]] = []
    for region in TANZANIA_REGIONS:
        positions = [
            match.start()
            for alias in region.all_aliases
            for normalized_alias in [normalize_place_text(alias)]
            for match in [re.search(rf"\b{re.escape(normalized_alias)}\b", normalized)]
            if match is not None
        ]
        if positions:
            exact.append((min(positions), region))
    if exact:
        return [region for _, region in sorted(exact, key=lambda item: item[0])]

    # Fuzzy matching is restricted to single-word official names in short travel
    # questions. This accepts e.g. "Mwanzaa" without turning prose into places.
    words = normalized.split()
    place_cues = {"visit", "visiting", "to", "about", "kutembelea", "kwenda", "kuhusu"}
    if len(words) > 3 and not place_cues.intersection(words):
        return []
    candidates: list[tuple[int, TanzaniaRegion]] = []
    for position, word in enumerate(words):
        if len(word) < 5:
            continue
        for region in TANZANIA_REGIONS:
            official = normalize_place_text(region.name)
            if " " not in official and _edit_distance(word, official) == 1:
                candidates.append((position, region))
    return [region for _, region in sorted(candidates, key=lambda item: item[0])]


REGIONS_BY_SLUG = {region.slug: region for region in TANZANIA_REGIONS}
