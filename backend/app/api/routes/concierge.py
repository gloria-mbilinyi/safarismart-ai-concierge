"""Public, catalog-grounded concierge and trip-planning endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.concierge import (
    ConciergeChatRequest,
    ConciergeChatResponse,
    TripPlanRequest,
    TripPlanResponse,
)
from app.services.concierge import chat_about_destinations, create_trip_plan


router = APIRouter(prefix="/v1/concierge", tags=["concierge"])


@router.post("/plan", response_model=TripPlanResponse)
def plan_trip(
    payload: TripPlanRequest,
    request: Request,
    session: Annotated[Session, Depends(get_db_session)],
) -> TripPlanResponse:
    """Build a high-level trip idea using only active catalog destinations."""

    return create_trip_plan(
        session,
        payload,
        request.app.state.concierge_provider,
    )


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
