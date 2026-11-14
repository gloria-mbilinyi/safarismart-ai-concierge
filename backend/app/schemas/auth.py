"""Operator authentication API schemas."""

from typing import Literal

from pydantic import BaseModel


class OperatorTokenResponse(BaseModel):
    """OAuth2-compatible bearer token response."""

    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
