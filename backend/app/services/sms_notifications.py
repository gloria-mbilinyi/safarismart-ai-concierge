"""Consent-aware, PII-minimized SMS notification composition and sending."""

from dataclasses import dataclass
from typing import Protocol

from app.integrations.africastalking_sms import PHONE_PATTERN, SMSResult
from app.models.booking import BookingRequest
from app.models.enums import BookingStatus, SMSLanguage, SMSNotificationKind


class SMSProvider(Protocol):
    """Narrow provider boundary used by the notification service."""

    def send(self, phone: str, message: str) -> SMSResult:
        """Submit one SMS to the configured provider."""


@dataclass(frozen=True, slots=True)
class PreparedSMS:
    """A validated message ready for provider submission."""

    kind: SMSNotificationKind
    language: SMSLanguage
    recipient: str
    body: str


STATUS_LABELS: dict[SMSLanguage, dict[BookingStatus, str]] = {
    SMSLanguage.ENGLISH: {
        BookingStatus.DRAFT: "draft",
        BookingStatus.PENDING_AVAILABILITY: "pending availability",
        BookingStatus.QUOTED: "demo quote available",
        BookingStatus.PENDING_CONFIRMATION: "pending confirmation",
        BookingStatus.CONFIRMED: "confirmed in the demo workflow",
        BookingStatus.REJECTED: "rejected",
        BookingStatus.EXPIRED: "expired",
        BookingStatus.CANCELLED: "cancelled",
    },
    SMSLanguage.SWAHILI: {
        BookingStatus.DRAFT: "rasimu",
        BookingStatus.PENDING_AVAILABILITY: "inasubiri upatikanaji",
        BookingStatus.QUOTED: "nukuu ya majaribio inapatikana",
        BookingStatus.PENDING_CONFIRMATION: "inasubiri uthibitisho",
        BookingStatus.CONFIRMED: "imethibitishwa kwenye mfumo wa majaribio",
        BookingStatus.REJECTED: "imekataliwa",
        BookingStatus.EXPIRED: "muda umeisha",
        BookingStatus.CANCELLED: "imeghairiwa",
    },
}


def notification_body(
    kind: SMSNotificationKind,
    language: SMSLanguage,
    booking_reference: str,
    booking_status: BookingStatus,
) -> str:
    """Render one fixed template without customer personal information."""

    if language is SMSLanguage.ENGLISH:
        templates = {
            SMSNotificationKind.BOOKING_RECEIVED: (
                "SafariSmart received booking request {reference}. It is pending "
                "availability and is not confirmed."
            ),
            SMSNotificationKind.STATUS_UPDATED: (
                "SafariSmart update for {reference}: status is {status}. Demo "
                "statuses do not prove a real reservation."
            ),
            SMSNotificationKind.SYNTHETIC_QUOTE_AVAILABLE: (
                "A synthetic SafariSmart quote is available for {reference}. "
                "It is not live availability or a real offer or reservation."
            ),
            SMSNotificationKind.BOOKING_REJECTED: (
                "SafariSmart booking request {reference} was rejected. No "
                "real-world reservation was made."
            ),
            SMSNotificationKind.SYNTHETIC_BOOKING_CONFIRMED: (
                "SafariSmart demo workflow {reference} is marked confirmed. "
                "This is synthetic and does not prove a real reservation."
            ),
        }
    else:
        templates = {
            SMSNotificationKind.BOOKING_RECEIVED: (
                "SafariSmart imepokea ombi {reference}. Linasubiri upatikanaji "
                "na halijathibitishwa."
            ),
            SMSNotificationKind.STATUS_UPDATED: (
                "Taarifa ya SafariSmart kwa {reference}: hali ni {status}. Hali "
                "za majaribio hazithibitishi nafasi halisi."
            ),
            SMSNotificationKind.SYNTHETIC_QUOTE_AVAILABLE: (
                "Nukuu ya majaribio ya SafariSmart inapatikana kwa {reference}. "
                "Si upatikanaji, ofa, au nafasi halisi."
            ),
            SMSNotificationKind.BOOKING_REJECTED: (
                "Ombi la SafariSmart {reference} limekataliwa. Hakuna nafasi "
                "halisi iliyowekwa."
            ),
            SMSNotificationKind.SYNTHETIC_BOOKING_CONFIRMED: (
                "Mfumo wa majaribio wa SafariSmart umeweka {reference} kama "
                "imethibitishwa. Hii si uthibitisho wa nafasi halisi."
            ),
        }

    return templates[kind].format(
        reference=booking_reference,
        status=STATUS_LABELS[language][booking_status],
    )


def prepare_booking_sms(
    booking: BookingRequest,
    kind: SMSNotificationKind,
    language: SMSLanguage = SMSLanguage.ENGLISH,
) -> PreparedSMS | None:
    """Prepare a message only when the customer permitted phone contact."""

    if not booking.customer_consent or booking.customer_contact_preference != "phone":
        return None
    if booking.customer_phone is None:
        return None
    if not PHONE_PATTERN.fullmatch(booking.customer_phone):
        raise ValueError("Invalid international SMS recipient")

    body = notification_body(
        kind,
        language,
        booking.booking_reference,
        BookingStatus(booking.status),
    )
    return PreparedSMS(
        kind=kind,
        language=language,
        recipient=booking.customer_phone,
        body=body,
    )


class SMSNotificationService:
    """Send fixed booking templates through a private provider boundary."""

    def __init__(self, provider: SMSProvider):
        self.provider = provider

    def send_booking_notification(
        self,
        booking: BookingRequest,
        kind: SMSNotificationKind,
        language: SMSLanguage = SMSLanguage.ENGLISH,
    ) -> SMSResult | None:
        """Submit a permitted notification or return without an external call."""

        prepared = prepare_booking_sms(booking, kind, language)
        if prepared is None:
            return None
        return self.send_prepared(prepared)

    def send_prepared(self, prepared: PreparedSMS) -> SMSResult:
        """Submit an already validated outbox message outside its transaction."""

        return self.provider.send(prepared.recipient, prepared.body)
