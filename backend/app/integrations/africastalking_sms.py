
"""Africa's Talking SMS provider adapter."""

import re
from dataclasses import dataclass
from typing import Any

import africastalking

from app.config import Settings


PHONE_PATTERN = re.compile(r"^\+[1-9]\d{7,14}$")


class SMSDeliveryError(Exception):
    """Raised when the SMS provider cannot accept a message."""


class SMSConfigurationError(Exception):
    """Raised when SMS sending is disabled or incompletely configured."""


@dataclass(frozen=True)
class SMSResult:
    status: str
    message_id: str | None


class AfricasTalkingSMSProvider:
    """Send SMS through the Africa's Talking SDK."""

    def __init__(self, client: Any, sender_id: str | None = None):
        self.client = client
        self.sender_id = sender_id

    @classmethod
    def from_settings(cls, settings: Settings) -> "AfricasTalkingSMSProvider":
        """Create a provider only from validated, explicitly enabled settings."""

        if not settings.sms_enabled:
            raise SMSConfigurationError("SMS sending is disabled")
        if (
            settings.africastalking_username is None
            or settings.africastalking_api_key is None
        ):
            raise SMSConfigurationError("SMS credentials are not configured")

        return cls.from_credentials(
            settings.africastalking_username,
            settings.africastalking_api_key.get_secret_value(),
            environment=settings.africastalking_environment,
            sender_id=settings.africastalking_sender_id,
        )

    @classmethod
    def from_credentials(
        cls,
        username: str,
        api_key: str,
        *,
        environment: str = "sandbox",
        sender_id: str | None = None,
    ) -> "AfricasTalkingSMSProvider":
        normalized_username = username.strip()
        if not normalized_username or not api_key.strip():
            raise SMSConfigurationError("SMS credentials are required")
        if environment == "sandbox" and normalized_username.lower() != "sandbox":
            raise SMSConfigurationError("Sandbox SMS requires username 'sandbox'")
        if environment == "production" and normalized_username.lower() == "sandbox":
            raise SMSConfigurationError("Production SMS cannot use sandbox credentials")
        if environment not in {"sandbox", "production"}:
            raise SMSConfigurationError("Unsupported SMS environment")

        africastalking.initialize(normalized_username, api_key)
        return cls(africastalking.SMS, sender_id=sender_id)

    def send(self, phone: str, message: str) -> SMSResult:
        if not PHONE_PATTERN.fullmatch(phone):
            raise ValueError("Invalid international phone number")

        message = message.strip()
        if not message or len(message) > 1600:
            raise ValueError("SMS message length is invalid")

        try:
            if self.sender_id is None:
                response = self.client.send(message, [phone])
            else:
                response = self.client.send(message, [phone], self.sender_id)
        except Exception as exc:
            raise SMSDeliveryError(
                "SMS provider request failed"
            ) from exc

        try:
            recipient = response["SMSMessageData"]["Recipients"][0]
            provider_status = recipient["status"]
        except (KeyError, IndexError, TypeError):
            raise SMSDeliveryError(
                "Unexpected SMS provider response"
            ) from None

        if provider_status != "Success":
            raise SMSDeliveryError(
                "SMS provider did not accept the message"
            )

        return SMSResult(
            status="accepted",
            message_id=recipient.get("messageId"),
        )
