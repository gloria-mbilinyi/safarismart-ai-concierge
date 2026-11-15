"""Consent, privacy, and template tests for booking SMS notifications."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.integrations.africastalking_sms import SMSResult
from app.models.enums import (
    BookingStatus,
    SMSLanguage,
    SMSNotificationKind,
)
from app.services.sms_notifications import (
    SMSNotificationService,
    notification_body,
    prepare_booking_sms,
)


def booking(**overrides: object) -> SimpleNamespace:
    """Build the minimum booking view required by the notification service."""

    values: dict[str, object] = {
        "booking_reference": "SS-SMS-001",
        "status": BookingStatus.PENDING_AVAILABILITY.value,
        "customer_name": "Sensitive Customer Name",
        "customer_email": "sensitive.customer@example.com",
        "customer_phone": "+255712345678",
        "customer_contact_preference": "phone",
        "customer_consent": True,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.parametrize("language", list(SMSLanguage))
@pytest.mark.parametrize("kind", list(SMSNotificationKind))
def test_every_template_is_localized_safe_and_reference_scoped(
    kind: SMSNotificationKind,
    language: SMSLanguage,
) -> None:
    current_status = (
        BookingStatus.REJECTED
        if kind is SMSNotificationKind.BOOKING_REJECTED
        else BookingStatus.CONFIRMED
        if kind is SMSNotificationKind.SYNTHETIC_BOOKING_CONFIRMED
        else BookingStatus.QUOTED
        if kind is SMSNotificationKind.SYNTHETIC_QUOTE_AVAILABLE
        else BookingStatus.PENDING_AVAILABILITY
    )
    message = notification_body(kind, language, "SS-SMS-001", current_status)

    assert "SS-SMS-001" in message
    assert len(message) <= 1600
    assert "Sensitive Customer Name" not in message
    assert "sensitive.customer@example.com" not in message
    if kind is SMSNotificationKind.BOOKING_RECEIVED:
        assert "pending" in message.lower() or "inasubiri" in message.lower()
    if kind in {
        SMSNotificationKind.SYNTHETIC_QUOTE_AVAILABLE,
        SMSNotificationKind.SYNTHETIC_BOOKING_CONFIRMED,
    }:
        assert "synthetic" in message.lower() or "majaribio" in message.lower()


@pytest.mark.parametrize(
    "overrides",
    [
        {"customer_consent": False},
        {"customer_contact_preference": "email"},
        {"customer_phone": None},
    ],
)
def test_sms_is_not_sent_without_phone_permission(overrides: dict[str, object]) -> None:
    provider = Mock()
    service = SMSNotificationService(provider)

    result = service.send_booking_notification(
        booking(**overrides),  # type: ignore[arg-type]
        SMSNotificationKind.BOOKING_RECEIVED,
    )

    assert result is None
    provider.send.assert_not_called()


def test_invalid_recipient_is_rejected_before_provider_call() -> None:
    provider = Mock()
    service = SMSNotificationService(provider)

    with pytest.raises(ValueError, match="Invalid international SMS recipient"):
        service.send_booking_notification(
            booking(customer_phone="0712345678"),  # type: ignore[arg-type]
            SMSNotificationKind.STATUS_UPDATED,
        )

    provider.send.assert_not_called()


def test_service_sends_only_the_prepared_template_and_recipient() -> None:
    provider = Mock()
    provider.send.return_value = SMSResult(
        status="accepted", message_id="sandbox-message-001"
    )
    service = SMSNotificationService(provider)
    customer_booking = booking(status=BookingStatus.REJECTED.value)

    result = service.send_booking_notification(
        customer_booking,  # type: ignore[arg-type]
        SMSNotificationKind.BOOKING_REJECTED,
        SMSLanguage.SWAHILI,
    )

    assert result == SMSResult(status="accepted", message_id="sandbox-message-001")
    phone, message = provider.send.call_args.args
    assert phone == "+255712345678"
    assert "SS-SMS-001" in message
    assert "limekataliwa" in message
    assert "Sensitive Customer Name" not in message
    assert "+255712345678" not in message


def test_status_update_uses_current_booking_status() -> None:
    prepared = prepare_booking_sms(
        booking(status=BookingStatus.CANCELLED.value),  # type: ignore[arg-type]
        SMSNotificationKind.STATUS_UPDATED,
        SMSLanguage.ENGLISH,
    )

    assert prepared is not None
    assert "status is cancelled" in prepared.body
    assert "do not prove a real reservation" in prepared.body
