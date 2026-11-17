"""Bilingual, consent-aware booking email tests."""

from datetime import date, timedelta
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.integrations.notification_provider import ProviderAcceptance
from app.models.booking import BookingRequest
from app.models.enums import BookingStatus, NotificationKind, NotificationLanguage
from app.services.email_notifications import (
    EmailNotificationService,
    email_content,
    prepare_booking_email,
)


def email_booking(**overrides: object) -> BookingRequest:
    start_date = date.today() + timedelta(days=30)
    values: dict[str, object] = {
        "booking_reference": "SS-EMAIL123456",
        "idempotency_key": f"email-{uuid4().hex}",
        "destination_id": uuid4(),
        "travel_start_date": start_date,
        "travel_end_date": start_date + timedelta(days=3),
        "party_size": 2,
        "customer_name": "Private Customer",
        "customer_email": "traveller@example.com",
        "customer_contact_preference": "email",
        "customer_language": "en",
        "customer_consent": True,
        "status": BookingStatus.PENDING_AVAILABILITY.value,
    }
    values.update(overrides)
    return BookingRequest(**values)


@pytest.mark.parametrize("language", list(NotificationLanguage))
@pytest.mark.parametrize("kind", list(NotificationKind))
def test_email_templates_are_reference_grounded_and_reservation_safe(
    kind: NotificationKind,
    language: NotificationLanguage,
) -> None:
    subject, body = email_content(
        kind,
        language,
        "SS-EMAIL123456",
        BookingStatus.PENDING_AVAILABILITY,
    )

    assert subject.strip()
    assert "SS-EMAIL123456" in body
    assert "Private Customer" not in body
    assert "reservation" in body.lower() or "nafasi" in body.lower()


def test_prepare_email_requires_email_preference_and_consent() -> None:
    assert prepare_booking_email(
        email_booking(customer_consent=False),
        NotificationKind.BOOKING_RECEIVED,
        NotificationLanguage.ENGLISH,
        "email-key",
    ) is None
    assert prepare_booking_email(
        email_booking(customer_contact_preference="phone"),
        NotificationKind.BOOKING_RECEIVED,
        NotificationLanguage.ENGLISH,
        "email-key",
    ) is None


def test_email_service_forwards_fixed_content_and_idempotency_key() -> None:
    provider = Mock()
    provider.send.return_value = ProviderAcceptance(
        status="accepted", message_id="email-provider-id"
    )
    prepared = prepare_booking_email(
        email_booking(),
        NotificationKind.BOOKING_RECEIVED,
        NotificationLanguage.ENGLISH,
        "email:SS-EMAIL123456:booking_received:pending_availability:en",
    )
    assert prepared is not None

    result = EmailNotificationService(provider).send_prepared(prepared)

    assert result.message_id == "email-provider-id"
    kwargs = provider.send.call_args.kwargs
    assert kwargs["recipient"] == "traveller@example.com"
    assert "SS-EMAIL123456" in kwargs["text"]
    assert kwargs["idempotency_key"].startswith("email:SS-EMAIL123456")
