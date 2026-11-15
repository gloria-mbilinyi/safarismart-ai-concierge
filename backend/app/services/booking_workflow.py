"""Authorized booking status workflow and audit recording."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.booking import BookingRequest, BookingStatusHistory
from app.models.enums import BookingStatus, StatusActorType


class InvalidBookingTransitionError(Exception):
    """Raised when a requested status edge is not in the workflow graph."""


class BookingAuthorizationError(Exception):
    """Raised when an actor is not authorized for a status transition."""


class TransitionReasonRequiredError(Exception):
    """Raised when an auditable terminal decision omits its reason."""


@dataclass(frozen=True, slots=True)
class WorkflowActor:
    """Authorization facts established before invoking the workflow service."""

    actor_type: StatusActorType
    principal_id: str
    authorized_booking_id: UUID | None = None
    authorized_operator_id: UUID | None = None


TRANSITION_RULES: dict[
    BookingStatus,
    dict[BookingStatus, frozenset[StatusActorType]],
] = {
    BookingStatus.DRAFT: {
        BookingStatus.PENDING_AVAILABILITY: frozenset(
            {StatusActorType.CUSTOMER, StatusActorType.SYSTEM}
        ),
    },
    BookingStatus.PENDING_AVAILABILITY: {
        BookingStatus.QUOTED: frozenset({StatusActorType.OPERATOR}),
        BookingStatus.REJECTED: frozenset({StatusActorType.OPERATOR}),
    },
    BookingStatus.QUOTED: {
        BookingStatus.PENDING_CONFIRMATION: frozenset({StatusActorType.CUSTOMER}),
        BookingStatus.EXPIRED: frozenset({StatusActorType.SYSTEM}),
    },
    BookingStatus.PENDING_CONFIRMATION: {
        BookingStatus.CONFIRMED: frozenset({StatusActorType.OPERATOR}),
        BookingStatus.REJECTED: frozenset({StatusActorType.OPERATOR}),
    },
    BookingStatus.CONFIRMED: {
        BookingStatus.CANCELLED: frozenset(
            {StatusActorType.CUSTOMER, StatusActorType.OPERATOR}
        ),
    },
    BookingStatus.REJECTED: {},
    BookingStatus.EXPIRED: {},
    BookingStatus.CANCELLED: {},
}

REASON_REQUIRED_STATUSES = frozenset(
    {BookingStatus.REJECTED, BookingStatus.CANCELLED}
)


def authorize_transition(
    booking: BookingRequest,
    target_status: BookingStatus,
    actor: WorkflowActor,
) -> None:
    """Verify the workflow edge and actor's resource-scoped authorization."""

    current_status = BookingStatus(booking.status)
    permitted_actor_types = TRANSITION_RULES[current_status].get(target_status)
    if permitted_actor_types is None:
        raise InvalidBookingTransitionError(
            f"Cannot transition booking from {current_status.value} "
            f"to {target_status.value}"
        )
    if actor.actor_type not in permitted_actor_types:
        raise BookingAuthorizationError("Actor type cannot perform this transition")
    if not actor.principal_id.strip() or len(actor.principal_id) > 120:
        raise BookingAuthorizationError("A valid authenticated principal is required")

    if actor.actor_type is StatusActorType.CUSTOMER:
        if actor.authorized_booking_id != booking.id:
            raise BookingAuthorizationError("Customer is not authorized for this booking")
    elif actor.actor_type is StatusActorType.OPERATOR:
        if booking.operator_id is None:
            raise BookingAuthorizationError("Booking has no assigned operator")
        if actor.authorized_operator_id != booking.operator_id:
            raise BookingAuthorizationError("Operator is not assigned to this booking")


def transition_booking(
    session: Session,
    booking: BookingRequest,
    target_status: BookingStatus,
    actor: WorkflowActor,
    *,
    reason: str | None = None,
    commit: bool = True,
) -> BookingRequest:
    """Apply one authorized transition and append its audit history atomically."""

    # Limit the locking refresh to booking columns. Refreshing the whole object
    # also reloads its eagerly loaded optional relationships, and PostgreSQL
    # rejects FOR UPDATE when it is applied across those outer joins.
    session.refresh(
        booking,
        attribute_names=["status", "operator_id"],
        with_for_update=True,
    )
    authorize_transition(booking, target_status, actor)
    normalized_reason = reason.strip() if reason else None
    if target_status in REASON_REQUIRED_STATUSES and not normalized_reason:
        raise TransitionReasonRequiredError(
            f"A reason is required when moving to {target_status.value}"
        )

    previous_status = booking.status
    booking.status = target_status.value
    booking.status_history.append(
        BookingStatusHistory(
            from_status=previous_status,
            to_status=target_status.value,
            actor_type=actor.actor_type.value,
            actor_reference=actor.principal_id.strip(),
            reason=normalized_reason,
        )
    )
    session.add(booking)
    if commit:
        session.commit()
        session.refresh(booking)
    else:
        session.flush()
    return booking
