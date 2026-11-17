"""Environment-based Africa's Talking SMS configuration tests."""

import secrets
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.integrations.africastalking_sms import (
    AfricasTalkingSMSProvider,
    SMSConfigurationError,
)
from app.integrations.sms_provider import LocalSMSProvider, build_sms_provider


def sms_settings(**overrides: object) -> Settings:
    """Build isolated SMS settings without reading a developer's `.env` file."""

    values: dict[str, object] = {
        "app_env": "test",
        "database_url": "sqlite://",
        "_env_file": None,
    }
    values.update(overrides)
    return Settings(**values)


def test_sms_is_sandboxed_and_disabled_by_default() -> None:
    settings = sms_settings()

    assert settings.sms_enabled is False
    assert settings.africastalking_environment == "sandbox"
    assert settings.africastalking_username is None
    assert settings.africastalking_api_key is None

    with pytest.raises(SMSConfigurationError, match="disabled"):
        AfricasTalkingSMSProvider.from_settings(settings)


def test_local_sms_provider_is_development_only_and_pii_silent(capsys) -> None:
    """Local mode exercises the outbox without credentials, network, or PII logs."""

    settings = sms_settings(sms_enabled=True, sms_provider="local")
    provider = build_sms_provider(settings)

    assert isinstance(provider, LocalSMSProvider)
    result = provider.send("+255712345678", "Private synthetic test message")
    assert result.status == "local-accepted"
    assert result.message_id is not None
    assert result.message_id.startswith("local-")
    assert capsys.readouterr().out == ""

    with pytest.raises(ValidationError, match="limited to development"):
        Settings(
            app_env="production",
            database_url="postgresql+psycopg://db.example/safarismart",
            auth_secret_key=secrets.token_urlsafe(48),
            sms_enabled=True,
            sms_provider="local",
            _env_file=None,
        )


@pytest.mark.parametrize(
    "configured",
    [
        {"sms_enabled": True},
        {"africastalking_username": "sandbox"},
        {"africastalking_api_key": secrets.token_urlsafe(24)},
    ],
)
def test_partial_or_missing_sms_credentials_are_rejected(
    configured: dict[str, object],
) -> None:
    with pytest.raises(ValidationError, match="must be configured together"):
        sms_settings(**configured)


def test_sandbox_and_production_credentials_cannot_be_mixed() -> None:
    api_key = secrets.token_urlsafe(24)

    with pytest.raises(ValidationError, match="sandbox username"):
        sms_settings(
            sms_enabled=True,
            africastalking_environment="sandbox",
            africastalking_username="production-app",
            africastalking_api_key=api_key,
        )
    with pytest.raises(ValidationError, match="sandbox username"):
        sms_settings(
            sms_enabled=True,
            africastalking_environment="production",
            africastalking_username="sandbox",
            africastalking_api_key=api_key,
        )


def test_placeholder_api_key_is_rejected() -> None:
    with pytest.raises(ValidationError, match="not a valid configured key"):
        sms_settings(
            sms_enabled=True,
            africastalking_username="sandbox",
            africastalking_api_key="<your-api-key>",
        )


def test_api_key_is_redacted_and_provider_uses_validated_settings() -> None:
    api_key = secrets.token_urlsafe(24)
    settings = sms_settings(
        sms_enabled=True,
        africastalking_username="sandbox",
        africastalking_api_key=api_key,
    )

    assert api_key not in repr(settings)
    with patch("app.integrations.africastalking_sms.africastalking") as sdk:
        provider = AfricasTalkingSMSProvider.from_settings(settings)

    sdk.initialize.assert_called_once_with("sandbox", api_key)
    assert provider.client is sdk.SMS


def test_sender_id_is_forwarded_only_when_configured() -> None:
    api_key = secrets.token_urlsafe(24)
    settings = sms_settings(
        sms_enabled=True,
        africastalking_username="sandbox",
        africastalking_api_key=api_key,
        africastalking_sender_id="SAFARISMART",
    )

    with patch("app.integrations.africastalking_sms.africastalking") as sdk:
        sdk.SMS.send.return_value = {
            "SMSMessageData": {
                "Recipients": [
                    {"status": "Success", "messageId": "sandbox-message"}
                ]
            }
        }
        provider = AfricasTalkingSMSProvider.from_settings(settings)
        provider.send("+255712345678", "Sandbox test")

    sdk.SMS.send.assert_called_once_with(
        "Sandbox test", ["+255712345678"], "SAFARISMART"
    )
