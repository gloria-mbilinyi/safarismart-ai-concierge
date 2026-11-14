"""Authenticated active operator identity resolution."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_db_session
from app.models.operator_user import OperatorUser
from app.security.tokens import (
    AuthenticationNotConfiguredError,
    TokenValidationError,
    decode_operator_access_token,
)


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


def credentials_error() -> HTTPException:
    """Return the uniform bearer authentication failure."""

    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_operator_user(
    request: Request,
    token: Annotated[str, Depends(oauth2_scheme)],
    session: Annotated[Session, Depends(get_db_session)],
) -> OperatorUser:
    """Resolve a token to its current active user and operator organization."""

    try:
        claims = decode_operator_access_token(token, request.app.state.settings)
    except AuthenticationNotConfiguredError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured",
        ) from error
    except TokenValidationError as error:
        raise credentials_error() from error

    user = session.scalar(
        select(OperatorUser)
        .options(joinedload(OperatorUser.operator))
        .where(OperatorUser.id == claims.user_id)
    )
    if (
        user is None
        or not user.is_active
        or user.token_version != claims.token_version
        or user.operator_id != claims.operator_id
    ):
        raise credentials_error()
    if not user.operator.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator organization is inactive",
        )
    return user


CurrentOperatorUser = Annotated[OperatorUser, Depends(get_current_operator_user)]
