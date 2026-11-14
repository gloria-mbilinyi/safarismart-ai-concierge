"""JWT access-token creation and strict validation."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
from jwt.exceptions import InvalidTokenError

from app.config import Settings
from app.models.operator_user import OperatorUser


JWT_ALGORITHM = "HS256"
TOKEN_SUBJECT_PREFIX = "operator_user:"


class AuthenticationNotConfiguredError(RuntimeError):
    """Raised when an endpoint requires an unset signing key."""


class TokenValidationError(ValueError):
    """Raised when a bearer token fails any validation step."""


@dataclass(frozen=True, slots=True)
class OperatorTokenClaims:
    """Validated operator identity claims extracted from a bearer token."""

    user_id: UUID
    operator_id: UUID
    token_version: int
    token_id: UUID


def get_signing_secret(settings: Settings) -> str:
    """Return the configured secret or fail closed."""

    if settings.auth_secret_key is None:
        raise AuthenticationNotConfiguredError("Authentication is not configured")
    return settings.auth_secret_key.get_secret_value()


def create_operator_access_token(
    user: OperatorUser,
    settings: Settings,
    *,
    expires_delta: timedelta | None = None,
    now: datetime | None = None,
) -> str:
    """Issue a short-lived signed token for one operator identity."""

    issued_at = now or datetime.now(UTC)
    expires_at = issued_at + (
        expires_delta
        or timedelta(minutes=settings.auth_access_token_expire_minutes)
    )
    payload = {
        "sub": f"{TOKEN_SUBJECT_PREFIX}{user.id}",
        "operator_id": str(user.operator_id),
        "token_version": user.token_version,
        "jti": str(uuid4()),
        "iat": issued_at,
        "nbf": issued_at,
        "exp": expires_at,
        "iss": settings.auth_issuer,
        "aud": settings.auth_audience,
    }
    return jwt.encode(
        payload,
        get_signing_secret(settings),
        algorithm=JWT_ALGORITHM,
    )


def decode_operator_access_token(
    token: str,
    settings: Settings,
) -> OperatorTokenClaims:
    """Validate signature and required claims using a fixed algorithm allowlist."""

    try:
        payload = jwt.decode(
            token,
            get_signing_secret(settings),
            algorithms=[JWT_ALGORITHM],
            audience=settings.auth_audience,
            issuer=settings.auth_issuer,
            leeway=5,
            options={
                "require": [
                    "sub",
                    "operator_id",
                    "token_version",
                    "jti",
                    "iat",
                    "nbf",
                    "exp",
                    "iss",
                    "aud",
                ]
            },
        )
        subject = payload["sub"]
        if not isinstance(subject, str) or not subject.startswith(TOKEN_SUBJECT_PREFIX):
            raise TokenValidationError("Invalid token subject")
        token_version = payload["token_version"]
        if not isinstance(token_version, int) or isinstance(token_version, bool):
            raise TokenValidationError("Invalid token version")

        return OperatorTokenClaims(
            user_id=UUID(subject.removeprefix(TOKEN_SUBJECT_PREFIX)),
            operator_id=UUID(str(payload["operator_id"])),
            token_version=token_version,
            token_id=UUID(str(payload["jti"])),
        )
    except AuthenticationNotConfiguredError:
        raise
    except (InvalidTokenError, KeyError, TypeError, ValueError) as error:
        raise TokenValidationError("Invalid access token") from error
