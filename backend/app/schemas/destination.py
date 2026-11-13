"""Public destination API schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import DestinationCategory


class DestinationResponse(BaseModel):
    """A curated destination exposed by the public catalog."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    country: str
    region: str
    category: DestinationCategory
    description: str
    is_featured: bool
    created_at: datetime
    updated_at: datetime


class DestinationListResponse(BaseModel):
    """A page of destination catalog results."""

    items: list[DestinationResponse]
    total: int
    limit: int
    offset: int
