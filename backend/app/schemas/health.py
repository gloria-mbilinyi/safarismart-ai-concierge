"""Health endpoint schemas."""

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Public health status payload."""

    status: Literal["ok"]
