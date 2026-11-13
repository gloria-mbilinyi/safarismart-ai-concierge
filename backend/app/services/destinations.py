"""Destination catalog query service."""

from uuid import UUID

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.models.destination import Destination
from app.models.enums import DestinationCategory


def escape_search_term(value: str) -> str:
    """Escape SQL LIKE wildcard characters supplied as literal search text."""

    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def build_destination_filters(
    *,
    query: str | None,
    region: str | None,
    category: DestinationCategory | None,
    featured: bool | None,
) -> list[object]:
    """Build the shared catalog filters for list and count queries."""

    filters: list[object] = [Destination.is_active.is_(True)]

    if query and (normalized_query := query.strip()):
        search_pattern = f"%{escape_search_term(normalized_query)}%"
        filters.append(
            or_(
                Destination.name.ilike(search_pattern, escape="\\"),
                Destination.region.ilike(search_pattern, escape="\\"),
                Destination.description.ilike(search_pattern, escape="\\"),
            )
        )
    if region and (normalized_region := region.strip()):
        filters.append(func.lower(Destination.region) == normalized_region.lower())
    if category is not None:
        filters.append(Destination.category == category.value)
    if featured is not None:
        filters.append(Destination.is_featured.is_(featured))

    return filters


def list_destinations(
    session: Session,
    *,
    query: str | None = None,
    region: str | None = None,
    category: DestinationCategory | None = None,
    featured: bool | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Destination], int]:
    """Return an ordered destination page and its total filtered count."""

    filters = build_destination_filters(
        query=query,
        region=region,
        category=category,
        featured=featured,
    )
    statement: Select[tuple[Destination]] = (
        select(Destination)
        .where(*filters)
        .order_by(Destination.is_featured.desc(), Destination.name.asc())
        .limit(limit)
        .offset(offset)
    )
    count_statement = select(func.count()).select_from(Destination).where(*filters)

    items = list(session.scalars(statement).all())
    total = session.scalar(count_statement) or 0
    return items, total


def get_destination(session: Session, destination_id: UUID) -> Destination | None:
    """Return one active public destination by identifier."""

    statement = select(Destination).where(
        Destination.id == destination_id,
        Destination.is_active.is_(True),
    )
    return session.scalar(statement)
