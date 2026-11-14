"""Development-only demo operator bootstrap service."""

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.operator import Operator
from app.models.operator_user import OperatorUser
from app.security.passwords import hash_password
from app.services.authentication import normalize_email


OPERATOR_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class DemoBootstrapConflictError(Exception):
    """Raised when bootstrap input conflicts with existing non-demo data."""


def bootstrap_demo_operator(
    session: Session,
    *,
    operator_name: str,
    operator_slug: str,
    user_email: str,
    user_full_name: str,
    password: str,
) -> tuple[Operator, OperatorUser]:
    """Create a clearly synthetic demo organization and its first identity."""

    normalized_slug = operator_slug.strip().lower()
    normalized_email = normalize_email(user_email)
    if not OPERATOR_SLUG_PATTERN.fullmatch(normalized_slug):
        raise ValueError("Operator slug must use lowercase letters, numbers, and hyphens")
    if not operator_name.strip() or not user_full_name.strip():
        raise ValueError("Operator and user names must not be blank")

    existing_user = session.scalar(
        select(OperatorUser).where(OperatorUser.email == normalized_email)
    )
    if existing_user is not None:
        raise DemoBootstrapConflictError("Operator user already exists")

    operator = session.scalar(select(Operator).where(Operator.slug == normalized_slug))
    if operator is None:
        operator = Operator(
            name=operator_name.strip(),
            slug=normalized_slug,
            description=(
                "Synthetic demonstration operator for local SafariSmart testing; "
                "not a real operator partnership."
            ),
            contact_email=normalized_email,
            is_demo=True,
        )
        session.add(operator)
        session.flush()
    elif not operator.is_demo:
        raise DemoBootstrapConflictError(
            "Refusing to attach demo credentials to a non-demo operator"
        )

    user = OperatorUser(
        operator=operator,
        email=normalized_email,
        full_name=user_full_name.strip(),
        password_hash=hash_password(password),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return operator, user
