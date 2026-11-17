"""Resend HTTPS adapter contract and safe failure tests."""

import json
from unittest.mock import patch
from urllib.error import HTTPError

import pytest

from app.integrations.resend_email import EmailDeliveryError, ResendEmailProvider


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self, _: int) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def provider() -> ResendEmailProvider:
    return ResendEmailProvider(
        api_key="re_test_key_that_is_not_real",
        from_address="SafariSmart <bookings@example.com>",
        timeout_seconds=5,
    )


def test_resend_submits_https_json_with_provider_idempotency() -> None:
    captured = None

    def fake_urlopen(request, *, timeout: float):
        nonlocal captured
        captured = request
        assert timeout == 5
        return FakeResponse({"id": "resend-message-123"})

    with patch("app.integrations.resend_email.urlopen", side_effect=fake_urlopen):
        result = provider().send(
            recipient="traveller@example.com",
            subject="Request received",
            text="Booking Reference: SS-EMAIL123456",
            html="<p>Booking Reference: SS-EMAIL123456</p>",
            idempotency_key="email:SS-EMAIL123456:received",
        )

    assert result.status == "accepted"
    assert result.message_id == "resend-message-123"
    assert captured is not None
    assert captured.full_url == "https://api.resend.com/emails"
    assert captured.get_header("Authorization").startswith("Bearer re_")
    assert captured.get_header("Idempotency-key") == (
        "email:SS-EMAIL123456:received"
    )
    payload = json.loads(captured.data)
    assert payload["to"] == ["traveller@example.com"]


@pytest.mark.parametrize(
    ("status_code", "retryable"),
    [(422, False), (429, True), (503, True)],
)
def test_resend_http_failures_have_safe_retry_metadata(
    status_code: int,
    retryable: bool,
) -> None:
    error = HTTPError(
        "https://api.resend.com/emails",
        status_code,
        "provider detail must not persist",
        {},
        None,
    )
    with patch("app.integrations.resend_email.urlopen", side_effect=error):
        with pytest.raises(EmailDeliveryError) as raised:
            provider().send(
                recipient="traveller@example.com",
                subject="Request received",
                text="Safe body",
                html="<p>Safe body</p>",
                idempotency_key="email:safe-key",
            )

    assert raised.value.retryable is retryable
    assert raised.value.code == f"provider_http_{status_code}"
    assert "provider detail" not in str(raised.value)
