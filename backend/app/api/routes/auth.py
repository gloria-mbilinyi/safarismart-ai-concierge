"""Operator login endpoint; public registration is intentionally absent."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.auth import OperatorTokenResponse
from app.security.tokens import (
    AuthenticationNotConfiguredError,
    create_operator_access_token,
    get_signing_secret,
)
from app.services.authentication import (
    InvalidOperatorCredentialsError,
    authenticate_operator,
)


router = APIRouter(prefix="/v1/auth", tags=["operator-authentication"])


@router.post("/token", response_model=OperatorTokenResponse)
def login_operator(
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Annotated[Session, Depends(get_db_session)],
) -> OperatorTokenResponse:
    """Exchange an operator email and password for a short-lived access token."""

    settings = request.app.state.settings
    try:
        get_signing_secret(settings)
    except AuthenticationNotConfiguredError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured",
        ) from error

    try:
        user = authenticate_operator(session, form_data.username, form_data.password)
    except InvalidOperatorCredentialsError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error

    token = create_operator_access_token(user, settings)
    return OperatorTokenResponse(
        access_token=token,
        expires_in=settings.auth_access_token_expire_minutes * 60,
    )
