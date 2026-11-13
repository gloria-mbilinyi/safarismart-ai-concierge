"""Curated destination catalog seed data."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import Database
from app.models.destination import Destination
from app.models.enums import DestinationCategory


CURATED_DESTINATIONS: tuple[dict[str, object], ...] = (
    {
        "name": "Serengeti National Park",
        "slug": "serengeti-national-park",
        "country": "Tanzania",
        "region": "Mara",
        "category": DestinationCategory.NATIONAL_PARK.value,
        "description": (
            "A northern Tanzania national park known for expansive savannahs, "
            "diverse wildlife, and the seasonal Great Migration ecosystem."
        ),
        "is_featured": True,
    },
    {
        "name": "Ngorongoro Conservation Area",
        "slug": "ngorongoro-conservation-area",
        "country": "Tanzania",
        "region": "Arusha",
        "category": DestinationCategory.CONSERVATION_AREA.value,
        "description": (
            "A multiple-use conservation landscape centered on the Ngorongoro "
            "Crater and shared by wildlife and pastoral communities."
        ),
        "is_featured": True,
    },
    {
        "name": "Mount Kilimanjaro",
        "slug": "mount-kilimanjaro",
        "country": "Tanzania",
        "region": "Kilimanjaro",
        "category": DestinationCategory.MOUNTAIN.value,
        "description": (
            "Africa's highest mountain, offering several established trekking "
            "routes through distinct ecological zones."
        ),
        "is_featured": True,
    },
    {
        "name": "Zanzibar",
        "slug": "zanzibar",
        "country": "Tanzania",
        "region": "Zanzibar",
        "category": DestinationCategory.BEACH.value,
        "description": (
            "An Indian Ocean archipelago known for beaches, Swahili culture, "
            "historic Stone Town, and spice-growing traditions."
        ),
        "is_featured": True,
    },
    {
        "name": "Tarangire National Park",
        "slug": "tarangire-national-park",
        "country": "Tanzania",
        "region": "Manyara",
        "category": DestinationCategory.NATIONAL_PARK.value,
        "description": (
            "A northern Tanzania park noted for baobab-dotted landscapes, "
            "elephant populations, and the Tarangire River ecosystem."
        ),
        "is_featured": True,
    },
)


def seed_destinations(session: Session) -> int:
    """Insert missing curated destinations and return the number created."""

    seed_slugs = [str(item["slug"]) for item in CURATED_DESTINATIONS]
    existing_slugs = set(
        session.scalars(
            select(Destination.slug).where(Destination.slug.in_(seed_slugs))
        ).all()
    )
    missing_destinations = [
        Destination(**item)
        for item in CURATED_DESTINATIONS
        if item["slug"] not in existing_slugs
    ]
    session.add_all(missing_destinations)
    session.commit()
    return len(missing_destinations)


def main() -> None:
    """Seed the configured database from the command line."""

    database = Database(get_settings().database_url)
    try:
        with database.session_factory() as session:
            created_count = seed_destinations(session)
    finally:
        database.dispose()

    print(f"Created {created_count} destination(s).")


if __name__ == "__main__":
    main()
