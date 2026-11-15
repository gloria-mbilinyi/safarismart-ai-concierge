
"""Unit tests for Africa's Talking SMS integration."""

from unittest.mock import Mock

import pytest

from app.integrations.africastalking_sms import (
    AfricasTalkingSMSProvider,
    SMSDeliveryError,
)


def test_send_sms_success():
    client = Mock()
    client.send.return_value = {
        "SMSMessageData": {
            "Recipients": [
                {
                    "status": "Success",
                    "messageId": "test-message-123",
                }
            ]
        }
    }

    provider = AfricasTalkingSMSProvider(client)
    result = provider.send(
        "+255712345678",
        "Welcome to SafariSmart!",
    )

    assert result.status == "accepted"
    assert result.message_id == "test-message-123"
    client.send.assert_called_once_with(
        "Welcome to SafariSmart!",
        ["+255712345678"],
    )


def test_invalid_phone_number():
    provider = AfricasTalkingSMSProvider(Mock())

    with pytest.raises(ValueError):
        provider.send("0712345678", "Hello")


def test_empty_sms_message():
    provider = AfricasTalkingSMSProvider(Mock())

    with pytest.raises(ValueError):
        provider.send("+255712345678", "   ")


def test_provider_network_failure():
    client = Mock()
    client.send.side_effect = ConnectionError("Network failure")

    provider = AfricasTalkingSMSProvider(client)

    with pytest.raises(SMSDeliveryError) as raised:
        provider.send("+255712345678", "Hello")

    assert raised.value.retryable is True
    assert raised.value.code == "provider_transport_error"


def test_provider_rejected_message():
    client = Mock()
    client.send.return_value = {
        "SMSMessageData": {
            "Recipients": [{"status": "Failed"}]
        }
    }

    provider = AfricasTalkingSMSProvider(client)

    with pytest.raises(SMSDeliveryError) as raised:
        provider.send("+255712345678", "Hello")

    assert raised.value.retryable is False
    assert raised.value.code == "provider_rejected"


def test_unexpected_provider_response_is_safe_and_retryable():
    client = Mock()
    client.send.return_value = {"unexpected": "sensitive-provider-detail"}
    provider = AfricasTalkingSMSProvider(client)

    with pytest.raises(SMSDeliveryError) as raised:
        provider.send("+255712345678", "Hello")

    assert raised.value.retryable is True
    assert raised.value.code == "provider_response_invalid"
    assert "sensitive-provider-detail" not in str(raised.value)
