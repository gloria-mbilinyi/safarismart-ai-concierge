"""Operator credential authentication service."""

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.operator_user import OperatorUser
from app.security.passwords import perform_dummy_password_check, verify_password


class InvalidOperatorCredentialsError(Exception):
    """Raised for every invalid, inactive, or unknown login attempt."""


def normalize_email(email: str) -> str:
    """Normalize an operator login identifier for storage and lookup."""

    return email.strip().lower()


def authenticate_operator(
    session: Session,
    email: str,
    password: str,
) -> OperatorUser:
    """Authenticate an active operator user without revealing failure details."""

    normalized_email = normalize_email(email)
    user = session.scalar(
        select(OperatorUser)
        .options(joinedload(OperatorUser.operator))
        .where(func.lower(OperatorUser.email) == normalized_email)
    )
    if user is None:
        perform_dummy_password_check(password)
        raise InvalidOperatorCredentialsError
    if not verify_password(password, user.password_hash):
        raise InvalidOperatorCredentialsError
    if not user.is_active or not user.operator.is_active:
        raise InvalidOperatorCredentialsError

    user.last_login_at = datetime.now(UTC)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user
