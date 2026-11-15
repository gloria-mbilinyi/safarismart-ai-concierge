"""Safety tests for the explicitly invoked Sandbox SMS command."""

import secrets
from unittest.mock import Mock

import pytest

from app.cli.send_sandbox_sms import SANDBOX_TEST_MESSAGE, send_sandbox_test
from app.config import Settings
from app.integrations.africastalking_sms import SMSConfigurationError, SMSResult


def sandbox_settings(**overrides: object) -> Settings:
    """Return enabled sandbox settings with an unpredictable test-only key."""

    values: dict[str, object] = {
        "app_env": "test",
        "database_url": "sqlite://",
        "sms_enabled": True,
        "africastalking_environment": "sandbox",
        "africastalking_username": "sandbox",
        "africastalking_api_key": secrets.token_urlsafe(24),
        "_env_file": None,
    }
    values.update(overrides)
    return Settings(**values)


def test_sandbox_command_sends_one_fixed_non_booking_message() -> None:
    provider = Mock()
    provider.send.return_value = SMSResult(
        status="accepted", message_id="sandbox-cli-message"
    )
    provider_factory = Mock(return_value=provider)
    settings = sandbox_settings()

    result = send_sandbox_test(
        settings,
        "+255712345678",
        provider_factory=provider_factory,
    )

    assert result.status == "accepted"
    provider_factory.assert_called_once_with(settings)
    provider.send.assert_called_once_with("+255712345678", SANDBOX_TEST_MESSAGE)
    assert "No real booking or reservation" in SANDBOX_TEST_MESSAGE


def test_sandbox_command_refuses_production_configuration() -> None:
    provider_factory = Mock()
    settings = sandbox_settings(
        africastalking_environment="production",
        africastalking_username="safarismart-live",
    )

    with pytest.raises(SMSConfigurationError, match="sandbox-only"):
        send_sandbox_test(
            settings,
            "+255712345678",
            provider_factory=provider_factory,
        )

    provider_factory.assert_not_called()


@pytest.mark.parametrize(
    "invalid_number",
    ["0712345678", "255712345678", "+255-712-345-678", ""],
)
def test_sandbox_command_rejects_invalid_simulator_numbers(
    invalid_number: str,
) -> None:
    provider_factory = Mock()

    with pytest.raises(ValueError, match="international format"):
        send_sandbox_test(
            sandbox_settings(),
            invalid_number,
            provider_factory=provider_factory,
        )

    provider_factory.assert_not_called()


def test_sandbox_command_does_not_accept_an_arbitrary_message() -> None:
    """The callable has no message parameter that could expose an SMS relay."""

    provider = Mock()
    provider.send.return_value = SMSResult(status="accepted", message_id=None)

    send_sandbox_test(
        sandbox_settings(),
        "+255712345678",
        provider_factory=Mock(return_value=provider),
    )

    assert provider.send.call_args.args[1] == SANDBOX_TEST_MESSAGE
