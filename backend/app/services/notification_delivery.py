"""Channel-aware notification preparation and provider dispatch."""

from dataclasses import dataclass

from app.config import Settings
from app.integrations.notification_provider import ProviderAcceptance
from app.integrations.resend_email import ResendEmailProvider
from app.integrations.sms_provider import build_sms_provider
from app.models.booking import BookingRequest
from app.models.enums import (
    NotificationChannel,
    NotificationKind,
    NotificationLanguage,
)
from app.services.email_notifications import (
    EmailNotificationService,
    PreparedEmail,
    prepare_booking_email,
)
from app.services.sms_notifications import (
    PreparedSMS,
    SMSNotificationService,
    prepare_booking_sms,
)


PreparedNotification = PreparedSMS | PreparedEmail


@dataclass(frozen=True, slots=True)
class NotificationDeliveryServices:
    """Configured provider services; absent channels remain durably queued."""

    sms: SMSNotificationService | None = None
    email: EmailNotificationService | None = None

    @property
    def configured_channels(self) -> frozenset[NotificationChannel]:
        channels: set[NotificationChannel] = set()
        if self.sms is not None:
            channels.add(NotificationChannel.SMS)
        if self.email is not None:
            channels.add(NotificationChannel.EMAIL)
        return frozenset(channels)

    def prepare(
        self,
        booking: BookingRequest,
        channel: NotificationChannel,
        kind: NotificationKind,
        language: NotificationLanguage,
        idempotency_key: str,
    ) -> PreparedNotification | None:
        """Revalidate consent and selected recipient immediately before sending."""

        if channel is NotificationChannel.SMS:
            return prepare_booking_sms(booking, kind, language)
        return prepare_booking_email(booking, kind, language, idempotency_key)

    def send_prepared(
        self,
        channel: NotificationChannel,
        prepared: PreparedNotification,
    ) -> ProviderAcceptance:
        """Submit through exactly the selected configured channel."""

        if channel is NotificationChannel.SMS and isinstance(prepared, PreparedSMS):
            if self.sms is None:
                raise RuntimeError("SMS service is not configured")
            return self.sms.send_prepared(prepared)
        if channel is NotificationChannel.EMAIL and isinstance(prepared, PreparedEmail):
            if self.email is None:
                raise RuntimeError("Email service is not configured")
            return self.email.send_prepared(prepared)
        raise TypeError("Prepared notification does not match its channel")


def build_notification_delivery_services(
    settings: Settings,
) -> NotificationDeliveryServices:
    """Build only explicitly enabled provider services from validated settings."""

    sms = (
        SMSNotificationService(build_sms_provider(settings))
        if settings.sms_enabled
        else None
    )
    email = (
        EmailNotificationService(ResendEmailProvider.from_settings(settings))
        if settings.email_enabled
        else None
    )
    return NotificationDeliveryServices(sms=sms, email=email)
