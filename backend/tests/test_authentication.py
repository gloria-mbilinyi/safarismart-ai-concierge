"""Operator password, token, login, and bootstrap tests."""

import secrets
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.config import Settings
from app.models.operator_user import OperatorUser
from app.security.passwords import (
    PasswordPolicyError,
    hash_password,
    verify_password,
)
from app.security.tokens import (
    TokenValidationError,
    create_operator_access_token,
    decode_operator_access_token,
)
from app.services.operator_bootstrap import (
    DemoBootstrapConflictError,
    bootstrap_demo_operator,
)


def test_passwords_use_argon2_and_are_never_stored_verbatim() -> None:
    """Password helpers should enforce length and produce verifiable Argon2 hashes."""

    password = secrets.token_urlsafe(24)
    password_hash = hash_password(password)

    assert password_hash != password
    assert password_hash.startswith("$argon2")
    assert verify_password(password, password_hash)
    assert not verify_password("different password", password_hash)
    with pytest.raises(PasswordPolicyError):
        hash_password("too-short")


def test_demo_bootstrap_creates_synthetic_operator_identity(
    db_session: Session,
) -> None:
    """Bootstrap should label synthetic data and normalize login identifiers."""

    password = secrets.token_urlsafe(24)
    operator, user = bootstrap_demo_operator(
        db_session,
        operator_name="  Synthetic Coast Tours  ",
        operator_slug="synthetic-coast-tours",
        user_email="  LOCAL.DEMO@EXAMPLE.TEST  ",
        user_full_name="  Local Demo User  ",
        password=password,
    )

    assert operator.is_demo is True
    assert "Synthetic demonstration operator" in (operator.description or "")
    assert user.email == "local.demo@example.test"
    assert user.full_name == "Local Demo User"
    assert user.password_hash != password
    assert verify_password(password, user.password_hash)

    with pytest.raises(DemoBootstrapConflictError):
        bootstrap_demo_operator(
            db_session,
            operator_name="Synthetic Coast Tours",
            operator_slug="synthetic-coast-tours",
            user_email="local.demo@example.test",
            user_full_name="Local Demo User",
            password=secrets.token_urlsafe(24),
        )


def test_operator_login_returns_strictly_validated_token(
    auth_client: TestClient,
    auth_settings: Settings,
    demo_operator_user: OperatorUser,
    demo_password: str,
) -> None:
    """Valid credentials should produce a short-lived token with scoped claims."""

    response = auth_client.post(
        "/api/v1/auth/token",
        data={
            "username": "DEMO.OPERATOR@EXAMPLE.TEST",
            "password": demo_password,
        },
    )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["expires_in"] == 1800
    claims = decode_operator_access_token(
        response.json()["access_token"], auth_settings
    )
    assert claims.user_id == demo_operator_user.id
    assert claims.operator_id == demo_operator_user.operator_id
    assert claims.token_version == 1


@pytest.mark.parametrize(
    ("username", "use_valid_password"),
    [
        ("unknown@example.test", True),
        ("demo.operator@example.test", False),
    ],
)
def test_login_rejects_credentials_without_account_enumeration(
    auth_client: TestClient,
    demo_operator_user: OperatorUser,
    demo_password: str,
    username: str,
    use_valid_password: bool,
) -> None:
    """Unknown users and wrong passwords should receive the same generic response."""

    response = auth_client.post(
        "/api/v1/auth/token",
        data={
            "username": username,
            "password": (
                demo_password if use_valid_password else secrets.token_urlsafe(24)
            ),
        },
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Incorrect email or password"}
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("deactivate", ["user", "operator"])
def test_login_rejects_inactive_accounts(
    auth_client: TestClient,
    db_session: Session,
    demo_operator_user: OperatorUser,
    demo_password: str,
    deactivate: str,
) -> None:
    """Inactive identities and organizations cannot obtain new tokens."""

    if deactivate == "user":
        demo_operator_user.is_active = False
    else:
        demo_operator_user.operator.is_active = False
    db_session.commit()

    response = auth_client.post(
        "/api/v1/auth/token",
        data={
            "username": "demo.operator@example.test",
            "password": demo_password,
        },
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Incorrect email or password"}


def test_expired_and_tampered_tokens_are_rejected(
    auth_settings: Settings,
    demo_operator_user: OperatorUser,
) -> None:
    """Expiration and signature validation must both fail closed."""

    expired_token = create_operator_access_token(
        demo_operator_user,
        auth_settings,
        expires_delta=timedelta(seconds=-10),
    )
    valid_token = create_operator_access_token(demo_operator_user, auth_settings)
    header, payload, _ = valid_token.split(".")
    tampered_token = f"{header}.{payload}.invalid-signature"

    with pytest.raises(TokenValidationError):
        decode_operator_access_token(expired_token, auth_settings)
    with pytest.raises(TokenValidationError):
        decode_operator_access_token(tampered_token, auth_settings)


def test_wrong_issuer_or_audience_is_rejected(
    auth_settings: Settings,
    demo_operator_user: OperatorUser,
) -> None:
    """Tokens are valid only for the configured issuer and audience."""

    token = create_operator_access_token(demo_operator_user, auth_settings)

    with pytest.raises(TokenValidationError):
        decode_operator_access_token(
            token,
            auth_settings.model_copy(update={"auth_issuer": "other-issuer"}),
        )
    with pytest.raises(TokenValidationError):
        decode_operator_access_token(
            token,
            auth_settings.model_copy(update={"auth_audience": "other-audience"}),
        )


def test_authentication_requires_configuration_and_has_no_registration(
    client: TestClient,
    demo_operator_user: OperatorUser,
    demo_password: str,
) -> None:
    """Missing signing configuration fails closed and registration stays absent."""

    login_response = client.post(
        "/api/v1/auth/token",
        data={
            "username": "demo.operator@example.test",
            "password": demo_password,
        },
    )
    registration_response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "public@example.test",
            "password": secrets.token_urlsafe(24),
        },
    )

    assert login_response.status_code == 503
    assert registration_response.status_code == 404


def test_production_rejects_missing_or_development_security_defaults() -> None:
    """Production cannot start with a missing key, weak key, or local database URL."""

    with pytest.raises(ValidationError):
        Settings(app_env="production", _env_file=None)
    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            auth_secret_key="change-me-development-secret-key-value",
            database_url="postgresql+psycopg://db.example/safarismart",
            _env_file=None,
        )
    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            auth_secret_key=secrets.token_urlsafe(48),
            _env_file=None,
        )
