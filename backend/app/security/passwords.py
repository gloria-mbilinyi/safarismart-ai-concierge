"""Argon2 password hashing and password policy."""

import secrets

from pwdlib import PasswordHash


PASSWORD_HASH = PasswordHash.recommended()
DUMMY_PASSWORD_HASH = PASSWORD_HASH.hash(secrets.token_urlsafe(32))
MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 128


class PasswordPolicyError(ValueError):
    """Raised when a new password does not meet the local policy."""


def validate_password(password: str) -> None:
    """Require a long password while permitting passphrases."""

    if len(password) < MIN_PASSWORD_LENGTH:
        raise PasswordPolicyError(
            f"Password must contain at least {MIN_PASSWORD_LENGTH} characters"
        )
    if len(password) > MAX_PASSWORD_LENGTH:
        raise PasswordPolicyError(
            f"Password must contain at most {MAX_PASSWORD_LENGTH} characters"
        )


def hash_password(password: str) -> str:
    """Validate and hash a password with the recommended Argon2 settings."""

    validate_password(password)
    return PASSWORD_HASH.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password without propagating malformed-hash details."""

    try:
        return PASSWORD_HASH.verify(password, password_hash)
    except Exception:
        return False


def perform_dummy_password_check(password: str) -> None:
    """Reduce username-enumeration timing differences for missing accounts."""

    verify_password(password, DUMMY_PASSWORD_HASH)
