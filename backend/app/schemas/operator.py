"""Authenticated operator identity schemas."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class OperatorOrganizationResponse(BaseModel):
    """Non-sensitive operator organization metadata."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    is_demo: bool


class CurrentOperatorResponse(BaseModel):
    """The authenticated operator user and organization."""

    id: UUID
    email: str
    full_name: str
    operator: OperatorOrganizationResponse
