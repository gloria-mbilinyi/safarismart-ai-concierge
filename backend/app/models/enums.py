"""Domain values persisted by database models."""

from enum import StrEnum


class BookingStatus(StrEnum):
    """Allowed booking request states."""

    DRAFT = "draft"
    PENDING_AVAILABILITY = "pending_availability"
    QUOTED = "quoted"
    PENDING_CONFIRMATION = "pending_confirmation"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class DestinationCategory(StrEnum):
    """Supported high-level destination categories."""

    BEACH = "beach"
    CONSERVATION_AREA = "conservation_area"
    MOUNTAIN = "mountain"
    NATIONAL_PARK = "national_park"


class StatusActorType(StrEnum):
    """Actor categories recorded in booking audit history."""

    CUSTOMER = "customer"
    OPERATOR = "operator"
    SYSTEM = "system"
