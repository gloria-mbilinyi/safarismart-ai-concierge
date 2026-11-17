"""Environment validation for Resend transactional email."""

import secrets

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.integrations.resend_email import EmailConfigurationError, ResendEmailProvider


def email_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": "test",
        "database_url": "sqlite://",
        "_env_file": None,
    }
    values.update(overrides)
    return Settings(**values)


def test_email_is_disabled_and_secret_free_by_default() -> None:
    settings = email_settings()

    assert settings.email_enabled is False
    assert settings.resend_api_key is None
    assert settings.resend_from_email is None
    with pytest.raises(EmailConfigurationError, match="disabled"):
        ResendEmailProvider.from_settings(settings)


@pytest.mark.parametrize(
    "configured",
    [
        {"email_enabled": True},
        {"resend_api_key": f"re_{secrets.token_urlsafe(24)}"},
        {"resend_from_email": "bookings@example.com"},
    ],
)
def test_partial_email_configuration_is_rejected(configured: dict[str, object]) -> None:
    with pytest.raises(ValidationError, match="RESEND_API_KEY and RESEND_FROM_EMAIL"):
        email_settings(**configured)


def test_placeholder_and_header_injection_values_are_rejected() -> None:
    with pytest.raises(ValidationError, match="not a valid configured key"):
        email_settings(
            email_enabled=True,
            resend_api_key="re_<your-api-key>",
            resend_from_email="bookings@example.com",
        )
    with pytest.raises(ValidationError, match="single non-empty line"):
        email_settings(resend_from_name="SafariSmart\nBcc: attacker@example.com")


def test_valid_resend_configuration_is_redacted() -> None:
    api_key = f"re_{secrets.token_urlsafe(24)}"
    settings = email_settings(
        email_enabled=True,
        resend_api_key=api_key,
        resend_from_email="bookings@example.com",
    )

    provider = ResendEmailProvider.from_settings(settings)

    assert api_key not in repr(settings)
    assert "sqlite" not in repr(settings)
    assert provider.from_address == (
        "SafariSmart AI Concierge <bookings@example.com>"
    )


def test_production_neon_database_requires_psycopg_and_tls() -> None:
    secret = secrets.token_urlsafe(48)
    with pytest.raises(ValidationError, match=r"postgresql\+psycopg"):
        Settings(
            app_env="production",
            auth_secret_key=secret,
            database_url=(
                "postgresql://user:password@ep-demo-pooler.eu.neon.tech/neondb"
                "?sslmode=require"
            ),
            _env_file=None,
        )
    with pytest.raises(ValidationError, match="require PostgreSQL TLS"):
        Settings(
            app_env="production",
            auth_secret_key=secret,
            database_url=(
                "postgresql+psycopg://user:password@"
                "ep-demo-pooler.eu.neon.tech/neondb"
            ),
            _env_file=None,
        )

    settings = Settings(
        app_env="production",
        auth_secret_key=secret,
        database_url=(
            "postgresql+psycopg://user:password@"
            "ep-demo-pooler.eu.neon.tech/neondb?sslmode=require"
        ),
        _env_file=None,
    )
    assert settings.database_url.endswith("sslmode=require")
