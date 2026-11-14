"""Organization-scoped operator booking management services."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models.booking import BookingRequest
from app.models.enums import BookingStatus, StatusActorType
from app.models.operator_user import OperatorUser
from app.models.quote import BookingQuote
from app.schemas.operator_booking import DemoQuoteCreate
from app.services.booking_workflow import WorkflowActor, transition_booking


class DemoQuoteOnlyError(Exception):
    """Raised when a non-demo operator attempts the synthetic quote workflow."""


class QuoteAlreadyExistsError(Exception):
    """Raised when a booking already has its one allowed demo quote."""


class QuoteExpiryError(Exception):
    """Raised when a quote would remain valid after travel begins."""


def workflow_actor(user: OperatorUser) -> WorkflowActor:
    """Build verified workflow authorization facts from the authenticated user."""

    return WorkflowActor(
        actor_type=StatusActorType.OPERATOR,
        principal_id=str(user.id),
        authorized_operator_id=user.operator_id,
    )


def list_operator_bookings(
    session: Session,
    *,
    operator_id: UUID,
    booking_status: BookingStatus | None,
    limit: int,
    offset: int,
) -> tuple[list[BookingRequest], int]:
    """Return only bookings assigned to one operator organization."""

    filters = [BookingRequest.operator_id == operator_id]
    if booking_status is not None:
        filters.append(BookingRequest.status == booking_status.value)

    statement = (
        select(BookingRequest)
        .options(joinedload(BookingRequest.destination))
        .where(*filters)
        .order_by(BookingRequest.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    count_statement = select(func.count()).select_from(BookingRequest).where(*filters)
    bookings = list(session.scalars(statement).all())
    total = session.scalar(count_statement) or 0
    return bookings, total


def create_demo_quote(
    session: Session,
    *,
    booking: BookingRequest,
    user: OperatorUser,
    quote_input: DemoQuoteCreate,
) -> BookingRequest:
    """Create a synthetic quote and transition pending availability atomically."""

    if not user.operator.is_demo:
        raise DemoQuoteOnlyError
    if booking.quote is not None:
        raise QuoteAlreadyExistsError
    if quote_input.expires_at.date() > booking.travel_start_date:
        raise QuoteExpiryError

    try:
        transition_booking(
            session,
            booking,
            BookingStatus.QUOTED,
            workflow_actor(user),
            reason="Synthetic demo quote created by assigned operator",
            commit=False,
        )
        booking.quote = BookingQuote(
            operator_id=user.operator_id,
            amount_minor=quote_input.amount_minor,
            currency=quote_input.currency,
            expires_at=quote_input.expires_at,
            terms=(quote_input.terms.strip() or None) if quote_input.terms else None,
            is_demo=True,
        )
        session.add(booking)
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise QuoteAlreadyExistsError from error
    except Exception:
        session.rollback()
        raise

    session.refresh(booking)
    return booking


def reject_booking(
    session: Session,
    *,
    booking: BookingRequest,
    user: OperatorUser,
    reason: str,
) -> BookingRequest:
    """Reject a booking only from a workflow-permitted state."""

    return transition_booking(
        session,
        booking,
        BookingStatus.REJECTED,
        workflow_actor(user),
        reason=reason,
    )


def confirm_booking(
    session: Session,
    *,
    booking: BookingRequest,
    user: OperatorUser,
    reason: str,
) -> BookingRequest:
    """Confirm only a customer-accepted quote; never pending availability."""

    return transition_booking(
        session,
        booking,
        BookingStatus.CONFIRMED,
        workflow_actor(user),
        reason=reason,
    )
