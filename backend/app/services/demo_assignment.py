"""Safe synthetic destination assignment for the local demo workflow."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.destination import Destination
from app.models.operator import Operator
from app.seed.destinations import CURATED_DESTINATIONS


class DemoAssignmentError(Exception):
    """Raised when synthetic data assignment would affect a real operator."""


def assign_demo_destinations(session: Session, operator: Operator) -> int:
    """Assign only unassigned curated records to an explicitly synthetic operator."""

    if not operator.is_demo:
        raise DemoAssignmentError(
            "Demo destinations can be assigned only to a synthetic operator"
        )

    seed_slugs = [str(item["slug"]) for item in CURATED_DESTINATIONS]
    destinations = list(
        session.scalars(
            select(Destination).where(
                Destination.slug.in_(seed_slugs),
                Destination.operator_id.is_(None),
            )
        ).all()
    )
    for destination in destinations:
        destination.operator_id = operator.id
    session.commit()
    return len(destinations)
