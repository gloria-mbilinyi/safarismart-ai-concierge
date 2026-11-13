"""Booking state transition and audit tests."""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import BookingRequest, BookingStatusHistory, Destination, Operator
from app.models.enums import (
    BookingStatus,
    DestinationCategory,
    StatusActorType,
)
from app.services.booking_workflow import (
    BookingAuthorizationError,
    InvalidBookingTransitionError,
    TransitionReasonRequiredError,
    WorkflowActor,
    transition_booking,
)


@pytest.fixture
def workflow_booking(db_session: Session) -> BookingRequest:
    """Create an operator-assigned pending booking with initial audit history."""

    operator = Operator(name="Workflow Safaris", slug="workflow-safaris")
    destination = Destination(
        operator=operator,
        name="Workflow Reserve",
        slug="workflow-reserve",
        country="Tanzania",
        region="Arusha",
        category=DestinationCategory.NATIONAL_PARK.value,
        description="A test-only destination for workflow verification.",
    )
    start_date = date.today() + timedelta(days=60)
    booking = BookingRequest(
        booking_reference="SS-WORKFLOW-001",
        idempotency_key="workflow-booking-001",
        destination=destination,
        operator=operator,
        travel_start_date=start_date,
        travel_end_date=start_date + timedelta(days=4),
        party_size=2,
        customer_name="Workflow Traveller",
        customer_email="workflow@example.com",
        customer_contact_preference="email",
        customer_consent=True,
        status=BookingStatus.PENDING_AVAILABILITY.value,
    )
    booking.status_history.append(
        BookingStatusHistory(
            from_status=None,
            to_status=BookingStatus.PENDING_AVAILABILITY.value,
            actor_type=StatusActorType.CUSTOMER.value,
            actor_reference="customer-submission",
            reason="Booking request submitted",
        )
    )
    db_session.add(booking)
    db_session.commit()
    db_session.refresh(booking)
    return booking


def operator_actor(booking: BookingRequest) -> WorkflowActor:
    """Return authorization facts for the booking's assigned operator."""

    assert booking.operator_id is not None
    return WorkflowActor(
        actor_type=StatusActorType.OPERATOR,
        principal_id="operator-user-001",
        authorized_operator_id=booking.operator_id,
    )


def customer_actor(booking: BookingRequest) -> WorkflowActor:
    """Return authorization facts for the booking's authenticated customer."""

    return WorkflowActor(
        actor_type=StatusActorType.CUSTOMER,
        principal_id="customer-user-001",
        authorized_booking_id=booking.id,
    )


def test_complete_booking_workflow_records_audit_history(
    db_session: Session,
    workflow_booking: BookingRequest,
) -> None:
    """Each valid decision should update state and append an audit event."""

    transition_booking(
        db_session,
        workflow_booking,
        BookingStatus.QUOTED,
        operator_actor(workflow_booking),
        reason="Operator prepared an offer",
    )
    transition_booking(
        db_session,
        workflow_booking,
        BookingStatus.PENDING_CONFIRMATION,
        customer_actor(workflow_booking),
        reason="Traveller selected the offer",
    )
    transition_booking(
        db_session,
        workflow_booking,
        BookingStatus.CONFIRMED,
        operator_actor(workflow_booking),
        reason="Operator confirmed the reservation",
    )
    transition_booking(
        db_session,
        workflow_booking,
        BookingStatus.CANCELLED,
        customer_actor(workflow_booking),
        reason="Traveller requested cancellation",
    )

    assert workflow_booking.status == "cancelled"
    assert [event.to_status for event in workflow_booking.status_history] == [
        "pending_availability",
        "quoted",
        "pending_confirmation",
        "confirmed",
        "cancelled",
    ]
    assert [event.from_status for event in workflow_booking.status_history] == [
        None,
        "pending_availability",
        "quoted",
        "pending_confirmation",
        "confirmed",
    ]
    assert all(event.occurred_at is not None for event in workflow_booking.status_history)
    assert workflow_booking.status_history[-1].actor_reference == "customer-user-001"


def test_invalid_transition_leaves_booking_unchanged(
    db_session: Session,
    workflow_booking: BookingRequest,
) -> None:
    """Skipping workflow states should fail without adding audit history."""

    with pytest.raises(InvalidBookingTransitionError):
        transition_booking(
            db_session,
            workflow_booking,
            BookingStatus.CONFIRMED,
            operator_actor(workflow_booking),
        )

    assert workflow_booking.status == "pending_availability"
    assert len(workflow_booking.status_history) == 1


def test_unassigned_operator_cannot_change_booking(
    db_session: Session,
    workflow_booking: BookingRequest,
) -> None:
    """An operator authorization must match the booking's assigned operator."""

    unauthorized_actor = WorkflowActor(
        actor_type=StatusActorType.OPERATOR,
        principal_id="different-operator-user",
        authorized_operator_id=None,
    )

    with pytest.raises(BookingAuthorizationError):
        transition_booking(
            db_session,
            workflow_booking,
            BookingStatus.QUOTED,
            unauthorized_actor,
        )

    assert workflow_booking.status == "pending_availability"
    assert len(workflow_booking.status_history) == 1


def test_customer_cannot_make_operator_decision(
    db_session: Session,
    workflow_booking: BookingRequest,
) -> None:
    """A booking-authorized customer still cannot issue an operator quote."""

    with pytest.raises(BookingAuthorizationError):
        transition_booking(
            db_session,
            workflow_booking,
            BookingStatus.QUOTED,
            customer_actor(workflow_booking),
        )

    assert workflow_booking.status == "pending_availability"


def test_terminal_transition_requires_audit_reason(
    db_session: Session,
    workflow_booking: BookingRequest,
) -> None:
    """Rejection and cancellation decisions must carry an audit reason."""

    with pytest.raises(TransitionReasonRequiredError):
        transition_booking(
            db_session,
            workflow_booking,
            BookingStatus.REJECTED,
            operator_actor(workflow_booking),
        )

    assert workflow_booking.status == "pending_availability"
    assert len(workflow_booking.status_history) == 1


def test_system_can_expire_quote_but_terminal_state_cannot_transition(
    db_session: Session,
    workflow_booking: BookingRequest,
) -> None:
    """System expiry is valid, and expired bookings are terminal."""

    transition_booking(
        db_session,
        workflow_booking,
        BookingStatus.QUOTED,
        operator_actor(workflow_booking),
    )
    system_actor = WorkflowActor(
        actor_type=StatusActorType.SYSTEM,
        principal_id="quote-expiry-job",
    )
    transition_booking(
        db_session,
        workflow_booking,
        BookingStatus.EXPIRED,
        system_actor,
        reason="Quote validity period elapsed",
    )

    with pytest.raises(InvalidBookingTransitionError):
        transition_booking(
            db_session,
            workflow_booking,
            BookingStatus.PENDING_CONFIRMATION,
            customer_actor(workflow_booking),
        )

    assert workflow_booking.status == "expired"
    assert workflow_booking.status_history[-1].actor_type == "system"


@pytest.mark.parametrize("method", ["get", "patch", "put", "delete"])
def test_protected_booking_management_routes_are_not_exposed(
    client: TestClient,
    method: str,
) -> None:
    """No unauthenticated booking detail or status-management route should exist."""

    response = getattr(client, method)("/api/v1/bookings/SS-WORKFLOW-001")

    assert response.status_code == 404
