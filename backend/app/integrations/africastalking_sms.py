
"""Africa's Talking SMS provider adapter."""

import re
from dataclasses import dataclass
from typing import Any

import africastalking


PHONE_PATTERN = re.compile(r"^\+[1-9]\d{7,14}$")


class SMSDeliveryError(Exception):
    """Raised when the SMS provider cannot accept a message."""


@dataclass(frozen=True)
class SMSResult:
    status: str
    message_id: str | None


class AfricasTalkingSMSProvider:
    """Send SMS through the Africa's Talking SDK."""

    def __init__(self, client: Any):
        self.client = client

    @classmethod
    def from_credentials(
        cls, username: str, api_key: str
    ) -> "AfricasTalkingSMSProvider":
        if not username.strip() or not api_key.strip():
            raise ValueError("SMS credentials are required")

        africastalking.initialize(username, api_key)
        return cls(africastalking.SMS)

    def send(self, phone: str, message: str) -> SMSResult:
        if not PHONE_PATTERN.fullmatch(phone):
            raise ValueError("Invalid international phone number")

        message = message.strip()
        if not message or len(message) > 1600:
            raise ValueError("SMS message length is invalid")

        try:
            response = self.client.send(message, [phone])
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
