"""Public booking request submission endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.booking import BookingRequestCreate, BookingRequestResponse
from app.services.bookings import (
    DestinationUnavailableError,
    IdempotencyConflictError,
    create_booking_request,
)


router = APIRouter(prefix="/v1/bookings", tags=["bookings"])


@router.post("", response_model=BookingRequestResponse, status_code=status.HTTP_201_CREATED)
def submit_booking_request(
    submission: BookingRequestCreate,
    response: Response,
    session: Annotated[Session, Depends(get_db_session)],
    idempotency_key: Annotated[
        str,
        Header(
            alias="Idempotency-Key",
            min_length=8,
            max_length=128,
            pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
        ),
    ],
) -> BookingRequestResponse:
    """Create an operator-reviewed booking request without confirming it."""

    try:
        booking, created = create_booking_request(
            session,
            submission,
            idempotency_key,
        )
    except DestinationUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Destination not found",
        ) from error
    except IdempotencyConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Idempotency key was already used for a different request",
        ) from error

    if not created:
        response.status_code = status.HTTP_200_OK

    return BookingRequestResponse.model_validate(booking, from_attributes=True)
