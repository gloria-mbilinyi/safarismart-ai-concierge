"""Public, catalog-grounded concierge and trip-planning endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.concierge import (
    ConciergeChatRequest,
    ConciergeChatResponse,
    TripPlanRequest,
    TripPlanResponse,
)
from app.services.concierge import (
    DestinationSelectionError,
    create_trip_plan,
)
from app.services.concierge_chat import chat_about_destinations


router = APIRouter(prefix="/v1/concierge", tags=["concierge"])


@router.post("/plan", response_model=TripPlanResponse)
def plan_trip(
    payload: TripPlanRequest,
    request: Request,
    session: Annotated[Session, Depends(get_db_session)],
) -> TripPlanResponse:
    """Build a high-level trip idea using only active catalog destinations."""

    try:
        return create_trip_plan(
            session,
            payload,
            request.app.state.concierge_provider,
        )
    except DestinationSelectionError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error


@router.post("/chat", response_model=ConciergeChatResponse)
def concierge_chat(
    payload: ConciergeChatRequest,
    request: Request,
    session: Annotated[Session, Depends(get_db_session)],
) -> ConciergeChatResponse:
    """Answer bounded destination-discovery questions in English or Swahili."""

    return chat_about_destinations(
        session,
        payload,
        request.app.state.concierge_provider,
    )
