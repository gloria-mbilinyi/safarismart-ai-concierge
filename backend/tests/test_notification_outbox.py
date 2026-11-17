"""Transactional SMS outbox idempotency, claiming, and retry tests."""

from datetime import UTC, date, datetime, timedelta
from typing import Any
from unittest.mock import Mock, patch
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import Database
from app.config import Settings
from app.main import create_app
from app.integrations.africastalking_sms import SMSDeliveryError, SMSResult
from app.integrations.notification_provider import ProviderAcceptance
from app.integrations.resend_email import EmailDeliveryError
from app.models import BookingNotification, BookingRequest, Destination, Operator
from app.models.enums import (
    BookingStatus,
    DestinationCategory,
    NotificationStatus,
    SMSNotificationKind,
    StatusActorType,
)
from app.services.booking_workflow import WorkflowActor, transition_booking
from app.services.notification_outbox import (
    claim_next_notification,
    process_next_notification,
    record_sms_delivery_status,
    schedule_booking_notification,
)
from app.services.email_notifications import EmailNotificationService
from app.services.notification_delivery import NotificationDeliveryServices
from app.services.sms_notifications import SMSNotificationService


NOW = datetime.now(UTC) + timedelta(hours=1)


def booking_payload(destination_id: object, *, phone_contact: bool = True) -> dict[str, Any]:
    """Return a future-dated booking request suitable for outbox tests."""

    start_date = date.today() + timedelta(days=45)
    payload: dict[str, Any] = {
        "destination_id": str(destination_id),
        "travel_start_date": start_date.isoformat(),
        "travel_end_date": (start_date + timedelta(days=3)).isoformat(),
        "party_size": 2,
        "customer_name": "Outbox Test Customer",
        "customer_email": "outbox.customer@example.com",
        "customer_phone": "+255712345678",
        "customer_contact_preference": "phone" if phone_contact else "email",
        "customer_consent": True,
    }
    return payload


def submit_phone_booking(
    client: TestClient,
    destination: Destination,
    *,
    idempotency_key: str,
) -> str:
    """Submit a phone-contact booking and return its public reference."""

    response = client.post(
        "/api/v1/bookings",
        headers={"Idempotency-Key": idempotency_key},
        json=booking_payload(destination.id),
    )
    assert response.status_code in {200, 201}, response.text
    return str(response.json()["booking_reference"])


def test_booking_replay_schedules_exactly_one_received_notification(
    client: TestClient,
    db_session: Session,
    seeded_destinations: list[Destination],
) -> None:
    idempotency_key = f"outbox-{uuid4().hex}"

    first_reference = submit_phone_booking(
        client, seeded_destinations[0], idempotency_key=idempotency_key
    )
    second_reference = submit_phone_booking(
        client, seeded_destinations[0], idempotency_key=idempotency_key
    )

    db_session.expire_all()
    notifications = list(db_session.scalars(select(BookingNotification)).all())
    assert first_reference == second_reference
    assert len(notifications) == 1
    assert notifications[0].kind == SMSNotificationKind.BOOKING_RECEIVED.value
    assert notifications[0].channel == "sms"
    assert notifications[0].status == NotificationStatus.QUEUED.value
    assert first_reference in notifications[0].idempotency_key


def test_email_preference_schedules_email_only(
    client: TestClient,
    db_session: Session,
    seeded_destinations: list[Destination],
) -> None:
    headers = {"Idempotency-Key": f"email-only-{uuid4().hex}"}
    payload = booking_payload(seeded_destinations[0].id, phone_contact=False)
    response = client.post(
        "/api/v1/bookings",
        headers=headers,
        json=payload,
    )
    replay = client.post("/api/v1/bookings", headers=headers, json=payload)

    assert response.status_code == 201
    assert replay.status_code == 200
    assert replay.json()["booking_reference"] == response.json()["booking_reference"]
    notification = db_session.scalar(select(BookingNotification))
    assert notification is not None
    assert notification.channel == "email"
    assert notification.kind == SMSNotificationKind.BOOKING_RECEIVED.value
    assert notification.attempt_count == 0


def test_email_outbox_uses_reference_and_provider_idempotency(
    database: Database,
    client: TestClient,
    seeded_destinations: list[Destination],
) -> None:
    response = client.post(
        "/api/v1/bookings",
        headers={"Idempotency-Key": f"email-send-{uuid4().hex}"},
        json=booking_payload(seeded_destinations[0].id, phone_contact=False),
    )
    assert response.status_code == 201
    reference = response.json()["booking_reference"]
    provider = Mock()
    provider.send.return_value = ProviderAcceptance(
        status="accepted", message_id="resend-message-001"
    )

    result = process_next_notification(
        database.session_factory,
        NotificationDeliveryServices(
            email=EmailNotificationService(provider),
        ),
        now=NOW,
    )

    assert result is not None
    assert result.status is NotificationStatus.ACCEPTED
    kwargs = provider.send.call_args.kwargs
    assert reference in kwargs["text"]
    assert kwargs["idempotency_key"].startswith(f"email:{reference}:")
    with database.session_factory() as session:
        notification = session.get(BookingNotification, result.notification_id)
        assert notification is not None
        assert notification.channel == "email"
        assert notification.provider_message_id == "resend-message-001"
        assert notification.delivered_at is None


def test_dispatcher_never_switches_an_email_job_to_sms(
    database: Database,
    client: TestClient,
    seeded_destinations: list[Destination],
) -> None:
    response = client.post(
        "/api/v1/bookings",
        headers={"Idempotency-Key": f"email-no-switch-{uuid4().hex}"},
        json=booking_payload(seeded_destinations[0].id, phone_contact=False),
    )
    assert response.status_code == 201
    sms_provider = Mock()

    result = process_next_notification(
        database.session_factory,
        SMSNotificationService(sms_provider),
        now=NOW,
    )

    assert result is None
    sms_provider.send.assert_not_called()
    with database.session_factory() as session:
        notification = session.scalar(select(BookingNotification))
        assert notification is not None
        assert notification.channel == "email"
        assert notification.status == NotificationStatus.QUEUED.value
        assert notification.attempt_count == 0


def test_transient_email_failure_requeues_without_exposing_provider_detail(
    database: Database,
    client: TestClient,
    seeded_destinations: list[Destination],
) -> None:
    response = client.post(
        "/api/v1/bookings",
        headers={"Idempotency-Key": f"email-retry-{uuid4().hex}"},
        json=booking_payload(seeded_destinations[0].id, phone_contact=False),
    )
    assert response.status_code == 201
    provider = Mock()
    provider.send.side_effect = EmailDeliveryError(
        "private provider response",
        retryable=True,
        code="provider_http_503",
    )

    result = process_next_notification(
        database.session_factory,
        NotificationDeliveryServices(
            email=EmailNotificationService(provider),
        ),
        now=NOW,
    )

    assert result is not None
    assert result.status is NotificationStatus.QUEUED
    with database.session_factory() as session:
        notification = session.get(BookingNotification, result.notification_id)
        assert notification is not None
        assert notification.last_error_code == "provider_http_503"
        assert "private" not in notification.last_error_code


def test_web_submission_triggers_bounded_post_commit_email_dispatch(
    database: Database,
    seeded_destinations: list[Destination],
) -> None:
    provider = Mock()
    provider.send.return_value = ProviderAcceptance(
        status="accepted", message_id="post-commit-email-id"
    )
    services = NotificationDeliveryServices(
        email=EmailNotificationService(provider),
    )
    settings = Settings(
        app_env="test",
        database_url=str(database.engine.url),
        notification_dispatch_interval_seconds=300,
        _env_file=None,
    )

    with patch(
        "app.main.build_notification_delivery_services",
        return_value=services,
    ):
        with TestClient(create_app(settings)) as configured_client:
            response = configured_client.post(
                "/api/v1/bookings",
                headers={"Idempotency-Key": f"post-commit-{uuid4().hex}"},
                json=booking_payload(
                    seeded_destinations[0].id,
                    phone_contact=False,
                ),
            )

    assert response.status_code == 201
    assert response.json()["notification"] == {
        "channel": "email",
        "state": "queued",
        "mode": "resend",
    }
    provider.send.assert_called_once()
    with database.session_factory() as session:
        notification = session.scalar(select(BookingNotification))
        assert notification is not None
        assert notification.status == NotificationStatus.ACCEPTED.value
        assert notification.provider_message_id == "post-commit-email-id"


def test_workflow_transition_schedules_specific_event_once(
    db_session: Session,
) -> None:
    operator = Operator(name="Outbox Synthetic Operator", slug="outbox-synthetic")
    destination = Destination(
        operator=operator,
        name="Outbox Synthetic Destination",
        slug="outbox-synthetic-destination",
        country="Tanzania",
        region="Synthetic",
        category=DestinationCategory.NATIONAL_PARK.value,
        description="Synthetic outbox workflow fixture.",
    )
    start_date = date.today() + timedelta(days=30)
    booking = BookingRequest(
        booking_reference=f"SS-OUTBOX-{uuid4().hex[:8].upper()}",
        idempotency_key=f"outbox-workflow-{uuid4().hex}",
        destination=destination,
        operator=operator,
        travel_start_date=start_date,
        travel_end_date=start_date + timedelta(days=2),
        party_size=2,
        customer_name="Outbox Workflow Customer",
        customer_phone="+255712345678",
        customer_contact_preference="phone",
        customer_consent=True,
        status=BookingStatus.PENDING_AVAILABILITY.value,
    )
    db_session.add(booking)
    db_session.commit()

    transition_booking(
        db_session,
        booking,
        BookingStatus.QUOTED,
        WorkflowActor(
            actor_type=StatusActorType.OPERATOR,
            principal_id="outbox-operator-user",
            authorized_operator_id=operator.id,
        ),
    )

    notification = db_session.scalar(select(BookingNotification))
    assert notification is not None
    assert notification.kind == SMSNotificationKind.SYNTHETIC_QUOTE_AVAILABLE.value
    assert notification.status == NotificationStatus.QUEUED.value


def test_claim_is_committed_and_prevents_concurrent_second_claim(
    database: Database,
    client: TestClient,
    seeded_destinations: list[Destination],
) -> None:
    submit_phone_booking(
        client,
        seeded_destinations[0],
        idempotency_key=f"claim-{uuid4().hex}",
    )

    with database.session_factory() as first_session:
        first_claim = claim_next_notification(first_session, now=NOW)
    with database.session_factory() as second_session:
        second_claim = claim_next_notification(second_session, now=NOW)

    assert first_claim is not None
    assert second_claim is None
    with database.session_factory() as verification_session:
        claimed = verification_session.get(
            BookingNotification, first_claim.notification_id
        )
        assert claimed is not None
        assert claimed.status == NotificationStatus.PROCESSING.value
        assert claimed.attempt_count == 1


def test_transient_failure_retries_then_records_provider_acceptance(
    database: Database,
    client: TestClient,
    seeded_destinations: list[Destination],
) -> None:
    submit_phone_booking(
        client,
        seeded_destinations[0],
        idempotency_key=f"retry-{uuid4().hex}",
    )
    provider = Mock()
    provider.send.side_effect = [
        SMSDeliveryError(
            "temporary provider failure",
            retryable=True,
            code="provider_transport_error",
        ),
        SMSResult(status="accepted", message_id="provider-message-001"),
    ]
    service = SMSNotificationService(provider)

    first_result = process_next_notification(
        database.session_factory, service, now=NOW
    )
    second_result = process_next_notification(
        database.session_factory,
        service,
        now=NOW + timedelta(minutes=2),
    )

    assert first_result is not None
    assert first_result.status is NotificationStatus.QUEUED
    assert first_result.attempt_count == 1
    assert second_result is not None
    assert second_result.status is NotificationStatus.ACCEPTED
    assert second_result.attempt_count == 2
    with database.session_factory() as session:
        notification = session.get(BookingNotification, second_result.notification_id)
        assert notification is not None
        assert notification.status == NotificationStatus.ACCEPTED.value
        assert notification.provider_message_id == "provider-message-001"
        assert notification.accepted_at is not None
        assert notification.delivered_at is None


def test_permanent_provider_rejection_is_not_retried(
    database: Database,
    client: TestClient,
    seeded_destinations: list[Destination],
) -> None:
    submit_phone_booking(
        client,
        seeded_destinations[0],
        idempotency_key=f"rejected-{uuid4().hex}",
    )
    provider = Mock()
    provider.send.side_effect = SMSDeliveryError(
        "provider rejected message",
        retryable=False,
        code="provider_rejected",
    )

    result = process_next_notification(
        database.session_factory,
        SMSNotificationService(provider),
        now=NOW,
    )

    assert result is not None
    assert result.status is NotificationStatus.FAILED
    assert result.attempt_count == 1
    with database.session_factory() as session:
        notification = session.get(BookingNotification, result.notification_id)
        assert notification is not None
        assert notification.last_error_code == "provider_rejected"
        assert notification.failed_at is not None
        assert notification.claim_token is None


def test_external_send_observes_committed_claim_not_an_open_transaction(
    database: Database,
    client: TestClient,
    seeded_destinations: list[Destination],
) -> None:
    submit_phone_booking(
        client,
        seeded_destinations[0],
        idempotency_key=f"transaction-{uuid4().hex}",
    )
    provider = Mock()

    def assert_committed_claim(_: str, __: str) -> SMSResult:
        with database.session_factory() as independent_session:
            notification = independent_session.scalar(select(BookingNotification))
            assert notification is not None
            assert notification.status == NotificationStatus.PROCESSING.value
            assert notification.claim_token is not None
        return SMSResult(status="accepted", message_id="outside-transaction")

    provider.send.side_effect = assert_committed_claim

    result = process_next_notification(
        database.session_factory,
        SMSNotificationService(provider),
        now=NOW,
    )

    assert result is not None
    assert result.status is NotificationStatus.ACCEPTED


def test_delivery_updates_do_not_confuse_acceptance_with_delivery(
    database: Database,
    client: TestClient,
    seeded_destinations: list[Destination],
) -> None:
    submit_phone_booking(
        client,
        seeded_destinations[0],
        idempotency_key=f"delivery-{uuid4().hex}",
    )
    provider = Mock()
    provider.send.return_value = SMSResult(
        status="accepted", message_id="delivery-message-001"
    )
    result = process_next_notification(
        database.session_factory,
        SMSNotificationService(provider),
        now=NOW,
    )
    assert result is not None
    assert result.status is NotificationStatus.ACCEPTED

    with database.session_factory() as session:
        delivered = record_sms_delivery_status(
            session,
            "delivery-message-001",
            "Delivered",
            now=NOW + timedelta(minutes=1),
        )
        assert delivered.status == NotificationStatus.DELIVERED.value
        assert delivered.delivered_at is not None


def test_schedule_function_is_repeatable_inside_one_transaction(
    db_session: Session,
) -> None:
    booking = BookingRequest(
        booking_reference=f"SS-REPEAT-{uuid4().hex[:8].upper()}",
        idempotency_key=f"repeat-{uuid4().hex}",
        destination_id=uuid4(),
        travel_start_date=date.today() + timedelta(days=30),
        travel_end_date=date.today() + timedelta(days=32),
        party_size=1,
        customer_name="Repeat Test",
        customer_phone="+255712345678",
        customer_contact_preference="phone",
        customer_consent=True,
        status=BookingStatus.PENDING_AVAILABILITY.value,
    )

    first, first_created = schedule_booking_notification(
        db_session, booking, SMSNotificationKind.BOOKING_RECEIVED, now=NOW
    )
    second, second_created = schedule_booking_notification(
        db_session, booking, SMSNotificationKind.BOOKING_RECEIVED, now=NOW
    )

    assert first is second
    assert first_created is True
    assert second_created is False
