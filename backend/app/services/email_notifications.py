"""Consent-aware, bilingual transactional email composition and sending."""

from dataclasses import dataclass
from html import escape

from pydantic import EmailStr, TypeAdapter, ValidationError

from app.integrations.notification_provider import ProviderAcceptance
from app.integrations.resend_email import ResendEmailProvider
from app.models.booking import BookingRequest
from app.models.enums import (
    BookingStatus,
    NotificationKind,
    NotificationLanguage,
)
from app.services.sms_notifications import STATUS_LABELS


EMAIL_ADAPTER = TypeAdapter(EmailStr)


@dataclass(frozen=True, slots=True)
class PreparedEmail:
    """A validated fixed-template email ready for provider submission."""

    kind: NotificationKind
    language: NotificationLanguage
    recipient: str
    subject: str
    text: str
    html: str
    idempotency_key: str


def email_content(
    kind: NotificationKind,
    language: NotificationLanguage,
    booking_reference: str,
    booking_status: BookingStatus,
) -> tuple[str, str]:
    """Return a fixed subject and plain-text body without customer profile data."""

    status = STATUS_LABELS[language][booking_status]
    if language is NotificationLanguage.SWAHILI:
        subjects = {
            NotificationKind.BOOKING_RECEIVED: "SafariSmart imepokea ombi lako la safari",
            NotificationKind.STATUS_UPDATED: "Taarifa ya ombi lako la SafariSmart",
            NotificationKind.SYNTHETIC_QUOTE_AVAILABLE: "Nukuu ya majaribio ya SafariSmart inapatikana",
            NotificationKind.BOOKING_REJECTED: "Taarifa ya ombi lako la SafariSmart",
            NotificationKind.SYNTHETIC_BOOKING_CONFIRMED: "Taarifa ya mfumo wa majaribio wa SafariSmart",
        }
        messages = {
            NotificationKind.BOOKING_RECEIVED: (
                "Ombi lako la safari limewasilishwa kwa mafanikio!\n\n"
                "Asante kwa kuchagua SafariSmart AI Concierge.\n\n"
                "Ombi lako limepokelewa na linasubiri mapitio ya mhudumu.\n\n"
                "Nambari ya ombi: {reference}\n"
                "Hali: {status}\n\n"
                "Hili ni ombi la safari, si nafasi iliyothibitishwa."
            ),
            NotificationKind.STATUS_UPDATED: (
                "Taarifa ya SafariSmart kwa {reference}: hali ni {status}. "
                "Hali za mfumo wa majaribio hazithibitishi nafasi halisi."
            ),
            NotificationKind.SYNTHETIC_QUOTE_AVAILABLE: (
                "Nukuu ya majaribio inapatikana kwa {reference}. Si bei, "
                "upatikanaji, ofa, au nafasi halisi."
            ),
            NotificationKind.BOOKING_REJECTED: (
                "Ombi la SafariSmart {reference} limekataliwa. Hakuna nafasi "
                "halisi iliyowekwa."
            ),
            NotificationKind.SYNTHETIC_BOOKING_CONFIRMED: (
                "Mfumo wa majaribio umeweka {reference} kama imethibitishwa. "
                "Hii si uthibitisho wa nafasi halisi."
            ),
        }
    else:
        subjects = {
            NotificationKind.BOOKING_RECEIVED: "SafariSmart received your travel request",
            NotificationKind.STATUS_UPDATED: "Your SafariSmart request was updated",
            NotificationKind.SYNTHETIC_QUOTE_AVAILABLE: "A SafariSmart demo quote is available",
            NotificationKind.BOOKING_REJECTED: "Your SafariSmart request was updated",
            NotificationKind.SYNTHETIC_BOOKING_CONFIRMED: "SafariSmart demo workflow update",
        }
        messages = {
            NotificationKind.BOOKING_RECEIVED: (
                "Your travel request has been submitted successfully!\n\n"
                "Thank you for choosing SafariSmart AI Concierge.\n\n"
                "Your booking request has been received and is awaiting operator review.\n\n"
                "Booking Reference: {reference}\n"
                "Status: {status}\n\n"
                "Please note that this is a booking request, not a confirmed reservation."
            ),
            NotificationKind.STATUS_UPDATED: (
                "SafariSmart update for {reference}: status is {status}. Demo "
                "statuses do not prove a real reservation."
            ),
            NotificationKind.SYNTHETIC_QUOTE_AVAILABLE: (
                "A synthetic SafariSmart quote is available for {reference}. "
                "It is not live availability, a real offer, or a reservation."
            ),
            NotificationKind.BOOKING_REJECTED: (
                "SafariSmart booking request {reference} was rejected. No "
                "real-world reservation was made."
            ),
            NotificationKind.SYNTHETIC_BOOKING_CONFIRMED: (
                "SafariSmart demo workflow {reference} is marked confirmed. "
                "This is synthetic and does not prove a real reservation."
            ),
        }

    return subjects[kind], messages[kind].format(
        reference=booking_reference,
        status=status,
    )


def prepare_booking_email(
    booking: BookingRequest,
    kind: NotificationKind,
    language: NotificationLanguage,
    idempotency_key: str,
) -> PreparedEmail | None:
    """Prepare an email only for explicit, validated email consent."""

    if not booking.customer_consent or booking.customer_contact_preference != "email":
        return None
    if booking.customer_email is None:
        return None
    try:
        recipient = str(EMAIL_ADAPTER.validate_python(booking.customer_email))
    except ValidationError as error:
        raise ValueError("Invalid transactional email recipient") from error

    subject, text = email_content(
        kind,
        language,
        booking.booking_reference,
        BookingStatus(booking.status),
    )
    html = "".join(
        f"<p>{escape(paragraph)}</p>"
        for paragraph in text.split("\n\n")
    )
    return PreparedEmail(
        kind=kind,
        language=language,
        recipient=recipient,
        subject=subject,
        text=text,
        html=html,
        idempotency_key=idempotency_key,
    )


class EmailNotificationService:
    """Send prepared booking emails through the private Resend boundary."""

    def __init__(self, provider: ResendEmailProvider) -> None:
        self.provider = provider

    def send_prepared(self, prepared: PreparedEmail) -> ProviderAcceptance:
        """Submit an email using the outbox key for provider-side deduplication."""

        return self.provider.send(
            recipient=prepared.recipient,
            subject=prepared.subject,
            text=prepared.text,
            html=prepared.html,
            idempotency_key=prepared.idempotency_key,
        )
