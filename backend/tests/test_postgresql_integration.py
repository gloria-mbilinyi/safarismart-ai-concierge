"""PostgreSQL integration coverage for the protected booking workflow."""

from datetime import UTC, date, datetime, timedelta
import os
from pathlib import Path
import secrets
from typing import Any
from unittest.mock import Mock
from uuid import uuid4

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select

from app.config import Settings
from app.db.session import Database
from app.main import create_app
from app.integrations.africastalking_sms import SMSResult
from app.models import (
    Base,
    BookingNotification,
    BookingRequest,
    Destination,
    Operator,
)
from app.models.enums import (
    BookingStatus,
    DestinationCategory,
    NotificationStatus,
    SMSNotificationKind,
    StatusActorType,
)
from app.seed.destinations import seed_destinations
from app.services.booking_workflow import WorkflowActor, transition_booking
from app.services.demo_assignment import assign_demo_destinations
from app.services.notification_outbox import process_next_notification
from app.services.operator_bootstrap import bootstrap_demo_operator
from app.services.sms_notifications import SMSNotificationService


BACKEND_ROOT = Path(__file__).resolve().parents[1]
POSTGRES_TEST_URL = os.getenv("TEST_DATABASE_URL")


def booking_payload(destination_id: object) -> dict[str, Any]:
    """Build a valid synthetic request for the PostgreSQL workflow."""

    start_date = date.today() + timedelta(days=45)
    return {
        "destination_id": str(destination_id),
        "travel_start_date": start_date.isoformat(),
        "travel_end_date": (start_date + timedelta(days=4)).isoformat(),
        "party_size": 2,
        "customer_name": "PostgreSQL Synthetic Customer",
        "customer_email": "postgres.customer@example.com",
        "customer_phone": "+255713456789",
        "customer_contact_preference": "phone",
        "customer_consent": True,
        "special_requests": "CI integration test only.",
    }


def clear_domain_data(database: Database) -> None:
    """Remove test-owned rows while preserving the Alembic version table."""

    with database.engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())


@pytest.mark.skipif(
    POSTGRES_TEST_URL is None,
    reason="TEST_DATABASE_URL is required for PostgreSQL integration coverage",
)
def test_postgresql_authenticated_operator_booking_workflow() -> None:
    """Exercise migrations, auth, tenant isolation, quoting, and confirmation."""

    assert POSTGRES_TEST_URL is not None
    database = Database(POSTGRES_TEST_URL)
    settings = Settings(
        app_env="test",
        database_url=POSTGRES_TEST_URL,
        auth_secret_key=secrets.token_urlsafe(48),
        _env_file=None,
    )
    password = secrets.token_urlsafe(24)
    email = f"postgres-operator-{uuid4().hex}@example.test"

    try:
        alembic_config = Config(str(BACKEND_ROOT / "alembic.ini"))
        expected_head = ScriptDirectory.from_config(alembic_config).get_current_head()
        with database.engine.connect() as connection:
            current_revision = MigrationContext.configure(
                connection
            ).get_current_revision()
        assert current_revision == expected_head

        clear_domain_data(database)
        with database.session_factory() as session:
            seed_destinations(session)
            operator, _ = bootstrap_demo_operator(
                session,
                operator_name="PostgreSQL Synthetic Safaris",
                operator_slug=f"postgres-synthetic-{uuid4().hex[:8]}",
                user_email=email,
                user_full_name="PostgreSQL Demo Operator",
                password=password,
            )
            assert assign_demo_destinations(session, operator) == 5
            destination = session.scalar(
                select(Destination).where(Destination.operator_id == operator.id)
            )
            assert destination is not None
            destination_id = destination.id

        with TestClient(create_app(settings)) as client:
            submission = client.post(
                "/api/v1/bookings",
                headers={"Idempotency-Key": f"postgres-{uuid4().hex}"},
                json=booking_payload(destination_id),
            )
            assert submission.status_code == 201, submission.text
            booking_reference = submission.json()["booking_reference"]

            with database.session_factory() as session:
                queued_notification = session.scalar(select(BookingNotification))
                assert queued_notification is not None
                assert queued_notification.kind == (
                    SMSNotificationKind.BOOKING_RECEIVED.value
                )
                assert queued_notification.channel == "sms"
                assert queued_notification.status == NotificationStatus.QUEUED.value

            provider = Mock()
            provider.send.return_value = SMSResult(
                status="accepted", message_id="postgres-provider-message"
            )
            processed = process_next_notification(
                database.session_factory,
                SMSNotificationService(provider),
                now=datetime.now(UTC) + timedelta(minutes=1),
            )
            assert processed is not None
            assert processed.status is NotificationStatus.ACCEPTED

            login = client.post(
                "/api/v1/auth/token",
                data={"username": email, "password": password},
            )
            assert login.status_code == 200, login.text
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

            queue = client.get("/api/v1/operator/bookings", headers=headers)
            assert queue.status_code == 200
            assert queue.json()["total"] == 1

            with database.session_factory() as session:
                other_operator = Operator(
                    name="Other PostgreSQL Synthetic Organization",
                    slug=f"postgres-other-{uuid4().hex[:8]}",
                    is_demo=True,
                )
                other_destination = Destination(
                    operator=other_operator,
                    name=f"PostgreSQL Other Destination {uuid4().hex[:8]}",
                    slug=f"postgres-other-destination-{uuid4().hex[:8]}",
                    country="Tanzania",
                    region="Synthetic CI Region",
                    category=DestinationCategory.NATIONAL_PARK.value,
                    description="Synthetic cross-organization PostgreSQL fixture.",
                )
                start_date = date.today() + timedelta(days=60)
                other_booking = BookingRequest(
                    booking_reference=f"SS-PG-{uuid4().hex[:10].upper()}",
                    idempotency_key=f"postgres-other-{uuid4().hex}",
                    destination=other_destination,
                    operator=other_operator,
                    travel_start_date=start_date,
                    travel_end_date=start_date + timedelta(days=2),
                    party_size=2,
                    customer_name="Other PostgreSQL Customer",
                    customer_email="other.postgres@example.test",
                    customer_contact_preference="email",
                    customer_consent=True,
                )
                session.add(other_booking)
                session.commit()
                other_reference = other_booking.booking_reference

            hidden = client.get(
                f"/api/v1/operator/bookings/{other_reference}", headers=headers
            )
            assert hidden.status_code == 404

            quote = client.post(
                f"/api/v1/operator/bookings/{booking_reference}/quote",
                headers=headers,
                json={
                    "amount_minor": 250000,
                    "currency": "TZS",
                    "expires_at": (
                        datetime.now(UTC) + timedelta(days=7)
                    ).isoformat(),
                    "terms": "Synthetic PostgreSQL CI quote only.",
                },
            )
            assert quote.status_code == 200, quote.text
            assert quote.json()["status"] == "quoted"

            direct_confirmation = client.post(
                f"/api/v1/operator/bookings/{booking_reference}/confirm",
                headers=headers,
                json={"reason": "Direct confirmation must be rejected"},
            )
            assert direct_confirmation.status_code == 409

            with database.session_factory() as session:
                booking = session.scalar(
                    select(BookingRequest).where(
                        BookingRequest.booking_reference == booking_reference
                    )
                )
                assert booking is not None
                transition_booking(
                    session,
                    booking,
                    BookingStatus.PENDING_CONFIRMATION,
                    WorkflowActor(
                        actor_type=StatusActorType.CUSTOMER,
                        principal_id="verified-postgresql-test-context",
                        authorized_booking_id=booking.id,
                    ),
                    reason="Simulated verified customer acceptance in CI",
                )

            confirmation = client.post(
                f"/api/v1/operator/bookings/{booking_reference}/confirm",
                headers=headers,
                json={"reason": "Synthetic PostgreSQL operator confirmation"},
            )
            assert confirmation.status_code == 200, confirmation.text
            assert confirmation.json()["status"] == "confirmed"
            assert [
                item["to_status"] for item in confirmation.json()["status_history"]
            ][-3:] == ["quoted", "pending_confirmation", "confirmed"]

            with database.session_factory() as session:
                notifications = list(
                    session.scalars(
                        select(BookingNotification).order_by(
                            BookingNotification.created_at
                        )
                    ).all()
                )
                assert len(notifications) == 4
                assert notifications[0].status == NotificationStatus.ACCEPTED.value
                assert {item.kind for item in notifications[1:]} == {
                    SMSNotificationKind.SYNTHETIC_QUOTE_AVAILABLE.value,
                    SMSNotificationKind.STATUS_UPDATED.value,
                    SMSNotificationKind.SYNTHETIC_BOOKING_CONFIRMED.value,
                }
    finally:
        clear_domain_data(database)
        database.dispose()
