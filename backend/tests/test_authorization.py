"""Operator identity resolution and authorization tests."""

from datetime import date, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import BookingRequest, Destination, Operator
from app.models.enums import DestinationCategory
from app.models.operator_user import OperatorUser
from app.security.tokens import create_operator_access_token
from app.services.operator_access import (
    OperatorResourceNotFoundError,
    get_operator_booking,
)


def test_current_operator_resolves_active_database_identity(
    auth_client: TestClient,
    operator_headers: dict[str, str],
    demo_operator_user: OperatorUser,
) -> None:
    """A bearer token should resolve to current non-sensitive database state."""

    response = auth_client.get("/api/v1/operator/me", headers=operator_headers)

    assert response.status_code == 200
    assert response.json() == {
        "id": str(demo_operator_user.id),
        "email": "demo.operator@example.test",
        "full_name": "Demo Operator",
        "operator": {
            "id": str(demo_operator_user.operator_id),
            "name": "SafariSmart Synthetic Safaris",
            "slug": "safarismart-synthetic-safaris",
            "is_demo": True,
        },
    }
    assert "password_hash" not in response.text
    assert "token_version" not in response.text


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Bearer malformed-token"},
        {"Authorization": "Basic unsupported"},
    ],
)
def test_operator_endpoint_requires_valid_bearer_authentication(
    auth_client: TestClient,
    headers: dict[str, str],
) -> None:
    """Missing and malformed authorization should consistently return 401."""

    response = auth_client.get("/api/v1/operator/me", headers=headers)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("change", ["inactive_user", "revoked_token"])
def test_user_state_changes_invalidate_existing_tokens(
    auth_client: TestClient,
    db_session: Session,
    demo_operator_user: OperatorUser,
    operator_headers: dict[str, str],
    change: str,
) -> None:
    """Every request should enforce current user status and token version."""

    if change == "inactive_user":
        demo_operator_user.is_active = False
    else:
        demo_operator_user.token_version += 1
    db_session.commit()

    response = auth_client.get("/api/v1/operator/me", headers=operator_headers)

    assert response.status_code == 401
    assert response.json() == {"detail": "Could not validate credentials"}


def test_inactive_operator_is_forbidden_after_token_issuance(
    auth_client: TestClient,
    db_session: Session,
    demo_operator_user: OperatorUser,
    operator_headers: dict[str, str],
) -> None:
    """An authenticated user cannot act for a deactivated organization."""

    demo_operator_user.operator.is_active = False
    db_session.commit()

    response = auth_client.get("/api/v1/operator/me", headers=operator_headers)

    assert response.status_code == 403
    assert response.json() == {"detail": "Operator organization is inactive"}


def test_expired_token_is_rejected_by_operator_endpoint(
    auth_client: TestClient,
    auth_settings: Settings,
    demo_operator_user: OperatorUser,
) -> None:
    """Expired credentials should fail before identity resolution."""

    expired_token = create_operator_access_token(
        demo_operator_user,
        auth_settings,
        expires_delta=timedelta(seconds=-10),
    )

    response = auth_client.get(
        "/api/v1/operator/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )

    assert response.status_code == 401


def test_operator_booking_lookup_hides_cross_organization_resources(
    db_session: Session,
    demo_operator_user: OperatorUser,
) -> None:
    """A booking assigned elsewhere must look absent to the current operator."""

    other_operator = Operator(
        name="Other Synthetic Operator",
        slug=f"other-synthetic-{uuid4().hex[:8]}",
        is_demo=True,
    )
    destination = Destination(
        operator=other_operator,
        name=f"Other Test Destination {uuid4().hex[:8]}",
        slug=f"other-test-{uuid4().hex[:8]}",
        country="Tanzania",
        region="Test Region",
        category=DestinationCategory.NATIONAL_PARK.value,
        description="Synthetic authorization test data.",
    )
    start_date = date.today() + timedelta(days=30)
    booking = BookingRequest(
        booking_reference=f"SS-AUTHZ-{uuid4().hex[:8].upper()}",
        idempotency_key=f"authz-{uuid4().hex}",
        destination=destination,
        operator=other_operator,
        travel_start_date=start_date,
        travel_end_date=start_date + timedelta(days=2),
        party_size=2,
        customer_name="Authorization Test Customer",
        customer_email="authorization@example.test",
        customer_contact_preference="email",
        customer_consent=True,
    )
    db_session.add(booking)
    db_session.commit()

    with pytest.raises(OperatorResourceNotFoundError):
        get_operator_booking(
            db_session,
            booking_reference=booking.booking_reference,
            operator_id=demo_operator_user.operator_id,
        )

    authorized_booking = get_operator_booking(
        db_session,
        booking_reference=booking.booking_reference,
        operator_id=other_operator.id,
    )
    assert authorized_booking.id == booking.id
