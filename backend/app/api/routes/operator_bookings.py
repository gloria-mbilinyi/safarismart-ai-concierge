"""Protected organization-scoped booking management endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import CurrentOperatorUser
from app.db.session import get_db_session
from app.models.booking import BookingRequest
from app.models.enums import BookingStatus
from app.schemas.operator_booking import (
    BookingStatusHistoryResponse,
    DemoQuoteCreate,
    DemoQuoteResponse,
    OperatorBookingDestinationResponse,
    OperatorBookingDetailResponse,
    OperatorBookingListResponse,
    OperatorBookingSummaryResponse,
    OperatorDecisionRequest,
)
from app.services.booking_workflow import (
    BookingAuthorizationError,
    InvalidBookingTransitionError,
    TransitionReasonRequiredError,
)
from app.services.operator_access import (
    OperatorResourceNotFoundError,
    get_operator_booking,
)
from app.services.operator_bookings import (
    DemoQuoteOnlyError,
    QuoteAlreadyExistsError,
    QuoteExpiryError,
    confirm_booking,
    create_demo_quote,
    list_operator_bookings,
    reject_booking,
)


router = APIRouter(prefix="/v1/operator/bookings", tags=["operator-bookings"])


def booking_summary(booking: BookingRequest) -> OperatorBookingSummaryResponse:
    """Serialize an assigned booking without customer contact information."""

    return OperatorBookingSummaryResponse(
        booking_reference=booking.booking_reference,
        status=BookingStatus(booking.status),
        destination=OperatorBookingDestinationResponse(
            id=booking.destination.id,
            name=booking.destination.name,
            region=booking.destination.region,
        ),
        travel_start_date=booking.travel_start_date,
        travel_end_date=booking.travel_end_date,
        party_size=booking.party_size,
        created_at=booking.created_at,
        updated_at=booking.updated_at,
    )


def booking_detail(booking: BookingRequest) -> OperatorBookingDetailResponse:
    """Serialize protected detail for the assigned organization."""

    summary = booking_summary(booking)
    return OperatorBookingDetailResponse(
        **summary.model_dump(),
        customer_name=booking.customer_name,
        customer_email=booking.customer_email,
        customer_phone=booking.customer_phone,
        customer_contact_preference=booking.customer_contact_preference,
        customer_consent=booking.customer_consent,
        special_requests=booking.special_requests,
        status_history=[
            BookingStatusHistoryResponse.model_validate(item)
            for item in booking.status_history
        ],
        quote=(
            DemoQuoteResponse.model_validate(booking.quote)
            if booking.quote is not None
            else None
        ),
    )


def scoped_booking_or_404(
    session: Session,
    booking_reference: str,
    operator_id: UUID,
) -> BookingRequest:
    """Map missing and cross-organization resources to one safe response."""

    try:
        return get_operator_booking(
            session,
            booking_reference=booking_reference,
            operator_id=operator_id,
        )
    except OperatorResourceNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found",
        ) from error


def raise_workflow_http_error(error: Exception) -> None:
    """Convert internal workflow failures into safe operator API errors."""

    if isinstance(error, BookingAuthorizationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized for this booking action",
        ) from error
    if isinstance(error, TransitionReasonRequiredError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Booking cannot perform that transition from its current status",
    ) from error


@router.get("", response_model=OperatorBookingListResponse)
def list_assigned_bookings(
    user: CurrentOperatorUser,
    session: Annotated[Session, Depends(get_db_session)],
    booking_status: Annotated[BookingStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> OperatorBookingListResponse:
    """List only bookings assigned to the authenticated operator organization."""

    bookings, total = list_operator_bookings(
        session,
        operator_id=user.operator_id,
        booking_status=booking_status,
        limit=limit,
        offset=offset,
    )
    return OperatorBookingListResponse(
        items=[booking_summary(item) for item in bookings],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{booking_reference}", response_model=OperatorBookingDetailResponse)
def get_assigned_booking(
    booking_reference: str,
    user: CurrentOperatorUser,
    session: Annotated[Session, Depends(get_db_session)],
) -> OperatorBookingDetailResponse:
    """Return protected detail only for the assigned organization."""

    return booking_detail(
        scoped_booking_or_404(session, booking_reference, user.operator_id)
    )


@router.post(
    "/{booking_reference}/quote",
    response_model=OperatorBookingDetailResponse,
)
def quote_assigned_booking(
    booking_reference: str,
    quote_input: DemoQuoteCreate,
    user: CurrentOperatorUser,
    session: Annotated[Session, Depends(get_db_session)],
) -> OperatorBookingDetailResponse:
    """Create a synthetic quote and move pending availability to quoted."""

    booking = scoped_booking_or_404(session, booking_reference, user.operator_id)
    try:
        booking = create_demo_quote(
            session,
            booking=booking,
            user=user,
            quote_input=quote_input,
        )
    except DemoQuoteOnlyError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Quote actions are limited to synthetic demo operators",
        ) from error
    except QuoteAlreadyExistsError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Booking already has a quote",
        ) from error
    except QuoteExpiryError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Quote must expire on or before the travel start date",
        ) from error
    except (
        BookingAuthorizationError,
        InvalidBookingTransitionError,
        TransitionReasonRequiredError,
    ) as error:
        raise_workflow_http_error(error)
    return booking_detail(booking)


@router.post(
    "/{booking_reference}/reject",
    response_model=OperatorBookingDetailResponse,
)
def reject_assigned_booking(
    booking_reference: str,
    decision: OperatorDecisionRequest,
    user: CurrentOperatorUser,
    session: Annotated[Session, Depends(get_db_session)],
) -> OperatorBookingDetailResponse:
    """Reject a booking from a workflow-permitted operator decision state."""

    booking = scoped_booking_or_404(session, booking_reference, user.operator_id)
    try:
        booking = reject_booking(
            session,
            booking=booking,
            user=user,
            reason=decision.reason,
        )
    except (
        BookingAuthorizationError,
        InvalidBookingTransitionError,
        TransitionReasonRequiredError,
    ) as error:
        raise_workflow_http_error(error)
    return booking_detail(booking)


@router.post(
    "/{booking_reference}/confirm",
    response_model=OperatorBookingDetailResponse,
)
def confirm_assigned_booking(
    booking_reference: str,
    decision: OperatorDecisionRequest,
    user: CurrentOperatorUser,
    session: Annotated[Session, Depends(get_db_session)],
) -> OperatorBookingDetailResponse:
    """Confirm only a booking already awaiting operator confirmation."""

    booking = scoped_booking_or_404(session, booking_reference, user.operator_id)
    try:
        booking = confirm_booking(
            session,
            booking=booking,
            user=user,
            reason=decision.reason,
        )
    except (
        BookingAuthorizationError,
        InvalidBookingTransitionError,
        TransitionReasonRequiredError,
    ) as error:
        raise_workflow_http_error(error)
    return booking_detail(booking)
