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


class NotificationChannel(StrEnum):
    """Customer-selected transactional notification channels."""

    EMAIL = "email"
    SMS = "sms"


class NotificationKind(StrEnum):
    """Supported booking notification events."""

    BOOKING_RECEIVED = "booking_received"
    STATUS_UPDATED = "status_updated"
    SYNTHETIC_QUOTE_AVAILABLE = "synthetic_quote_available"
    BOOKING_REJECTED = "booking_rejected"
    SYNTHETIC_BOOKING_CONFIRMED = "synthetic_booking_confirmed"


class NotificationLanguage(StrEnum):
    """Languages available for transactional notification templates."""

    ENGLISH = "en"
    SWAHILI = "sw"


# Backwards-compatible imports for existing SMS-specific modules and clients.
SMSNotificationKind = NotificationKind
SMSLanguage = NotificationLanguage


class NotificationStatus(StrEnum):
    """Outbox and provider delivery lifecycle states."""

    QUEUED = "queued"
    PROCESSING = "processing"
    ACCEPTED = "accepted"
    DELIVERED = "delivered"
    FAILED = "failed"
    UNKNOWN = "unknown"
