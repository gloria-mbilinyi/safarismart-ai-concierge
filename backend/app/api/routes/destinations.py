"""Public tourism destination catalog endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.models.enums import DestinationCategory
from app.schemas.destination import DestinationListResponse, DestinationResponse
from app.services.destinations import get_destination, list_destinations


router = APIRouter(prefix="/v1/destinations", tags=["destinations"])


@router.get("", response_model=DestinationListResponse)
def list_destination_catalog(
    session: Annotated[Session, Depends(get_db_session)],
    query: Annotated[
        str | None,
        Query(alias="q", min_length=1, max_length=100),
    ] = None,
    region: Annotated[str | None, Query(min_length=1, max_length=120)] = None,
    category: DestinationCategory | None = None,
    featured: bool | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DestinationListResponse:
    """Search and filter active curated destinations."""

    destinations, total = list_destinations(
        session,
        query=query,
        region=region,
        category=category,
        featured=featured,
        limit=limit,
        offset=offset,
    )
    return DestinationListResponse(
        items=[DestinationResponse.model_validate(item) for item in destinations],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{destination_id}", response_model=DestinationResponse)
def retrieve_destination(
    destination_id: UUID,
    session: Annotated[Session, Depends(get_db_session)],
) -> DestinationResponse:
    """Return one active catalog destination."""

    destination = get_destination(session, destination_id)
    if destination is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Destination not found",
        )
    return DestinationResponse.model_validate(destination)
