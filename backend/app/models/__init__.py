"""SQLAlchemy models exposed for metadata registration."""

from app.db.base import Base
from app.models.booking import BookingRequest, BookingStatusHistory
from app.models.destination import Destination
from app.models.operator import Operator

__all__ = [
    "Base",
    "BookingRequest",
    "BookingStatusHistory",
    "Destination",
    "Operator",
]
