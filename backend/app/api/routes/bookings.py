"""Public booking request submission endpoint."""

from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Header,
    HTTPException,
    Request,
    Response,
    status,
)
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.models.enums import NotificationChannel
from app.schemas.booking import (
    BookingNotificationAcknowledgement,
    BookingRequestCreate,
    BookingRequestResponse,
)
from app.services.bookings import (
    DestinationUnavailableError,
    IdempotencyConflictError,
    create_booking_request,
)


router = APIRouter(prefix="/v1/bookings", tags=["bookings"])


@router.post("", response_model=BookingRequestResponse, status_code=status.HTTP_201_CREATED)
def submit_booking_request(
    submission: BookingRequestCreate,
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
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

    client_key = request.client.host if request.client is not None else "unknown-client"
    if not request.app.state.booking_rate_limiter.allow(client_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many booking requests. Please try again in one minute.",
            headers={"Retry-After": "60"},
        )

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

    channel = (
        NotificationChannel.EMAIL
        if booking.customer_contact_preference == "email"
        else NotificationChannel.SMS
    )
    configured = channel in request.app.state.notification_runner.configured_channels
    settings = request.app.state.settings
    if channel is NotificationChannel.EMAIL and configured:
        mode = "resend"
    elif channel is NotificationChannel.SMS and configured:
        mode = (
            f"africastalking_{settings.africastalking_environment}"
            if settings.sms_provider == "africastalking"
            else "local"
        )
    else:
        mode = "unconfigured"

    if configured:
        background_tasks.add_task(request.app.state.notification_runner.drain_safely)

    return BookingRequestResponse(
        booking_reference=booking.booking_reference,
        status=booking.status,
        destination_id=booking.destination_id,
        travel_start_date=booking.travel_start_date,
        travel_end_date=booking.travel_end_date,
        party_size=booking.party_size,
        created_at=booking.created_at,
        notification=BookingNotificationAcknowledgement(
            channel=channel.value,
            state="queued" if configured else "unavailable",
            mode=mode,
        ),
    )
