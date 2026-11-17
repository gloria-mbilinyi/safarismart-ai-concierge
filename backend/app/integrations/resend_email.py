"""Minimal Resend HTTPS API adapter with idempotent provider submission."""

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.config import Settings
from app.integrations.notification_provider import (
    NotificationDeliveryError,
    ProviderAcceptance,
)


RESEND_EMAILS_URL = "https://api.resend.com/emails"


class EmailConfigurationError(Exception):
    """Raised when transactional email is disabled or incomplete."""


class EmailDeliveryError(NotificationDeliveryError):
    """Raised when Resend cannot safely accept an email."""


class ResendEmailProvider:
    """Submit transactional email through Resend without logging message data."""

    def __init__(
        self,
        *,
        api_key: str,
        from_address: str,
        timeout_seconds: float,
        endpoint: str = RESEND_EMAILS_URL,
    ) -> None:
        self._api_key = api_key
        self.from_address = from_address
        self.timeout_seconds = timeout_seconds
        self.endpoint = endpoint

    @classmethod
    def from_settings(cls, settings: Settings) -> "ResendEmailProvider":
        """Build a provider only from validated, explicitly enabled settings."""

        if not settings.email_enabled:
            raise EmailConfigurationError("Transactional email is disabled")
        if settings.resend_api_key is None or settings.resend_from_email is None:
            raise EmailConfigurationError("Resend credentials are not configured")
        return cls(
            api_key=settings.resend_api_key.get_secret_value(),
            from_address=(
                f"{settings.resend_from_name} <{settings.resend_from_email}>"
            ),
            timeout_seconds=settings.resend_timeout_seconds,
        )

    def send(
        self,
        *,
        recipient: str,
        subject: str,
        text: str,
        html: str,
        idempotency_key: str,
    ) -> ProviderAcceptance:
        """Submit one email and return provider acceptance, never delivery."""

        payload = json.dumps(
            {
                "from": self.from_address,
                "to": [recipient],
                "subject": subject,
                "text": text,
                "html": html,
            }
        ).encode("utf-8")
        request = Request(
            self.endpoint,
            data=payload,
            method="POST",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "Idempotency-Key": idempotency_key,
                "User-Agent": "SafariSmart/0.1",
            },
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310
                response_payload = json.loads(response.read(16_384).decode("utf-8"))
        except HTTPError as error:
            retryable = error.code in {408, 409, 425, 429} or error.code >= 500
            raise EmailDeliveryError(
                "Email provider rejected the request",
                retryable=retryable,
                code=f"provider_http_{error.code}",
            ) from None
        except (TimeoutError, URLError):
            raise EmailDeliveryError(
                "Email provider request failed",
                retryable=True,
                code="provider_transport_error",
            ) from None
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise EmailDeliveryError(
                "Email provider returned an invalid response",
                retryable=True,
                code="provider_response_invalid",
            ) from None

        message_id = response_payload.get("id") if isinstance(response_payload, dict) else None
        if not isinstance(message_id, str) or not message_id.strip():
            raise EmailDeliveryError(
                "Email provider returned an invalid response",
                retryable=True,
                code="provider_response_invalid",
            )
        return ProviderAcceptance(status="accepted", message_id=message_id[:160])
