"""Environment-selected SMS provider construction."""

from dataclasses import dataclass
from uuid import uuid4

from app.config import Settings
from app.integrations.africastalking_sms import (
    PHONE_PATTERN,
    AfricasTalkingSMSProvider,
    SMSConfigurationError,
    SMSResult,
)


@dataclass(frozen=True, slots=True)
class LocalSMSProvider:
    """PII-silent provider for local outbox demonstrations without network calls."""

    def send(self, phone: str, message: str) -> SMSResult:
        """Validate like the real adapter, but emit no recipient or message content."""

        if not PHONE_PATTERN.fullmatch(phone):
            raise ValueError("Invalid international phone number")
        normalized_message = message.strip()
        if not normalized_message or len(normalized_message) > 1600:
            raise ValueError("SMS message length is invalid")
        return SMSResult(
            status="local-accepted",
            message_id=f"local-{uuid4().hex}",
        )


def build_sms_provider(
    settings: Settings,
) -> AfricasTalkingSMSProvider | LocalSMSProvider:
    """Build one explicitly enabled provider after settings validation."""

    if not settings.sms_enabled:
        raise SMSConfigurationError("SMS sending is disabled")
    if settings.sms_provider == "local":
        return LocalSMSProvider()
    return AfricasTalkingSMSProvider.from_settings(settings)
