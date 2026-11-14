"""Protected operator booking management schemas."""

from datetime import UTC, date, datetime
from typing import Annotated
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
)

from app.models.enums import BookingStatus, StatusActorType


def strip_reason(value: str) -> str:
    """Normalize and reject blank audit reasons."""

    normalized = value.strip()
    if not normalized:
        raise ValueError("must not be blank")
    return normalized


AuditReason = Annotated[
    str,
    StringConstraints(min_length=3, max_length=1000),
    AfterValidator(strip_reason),
]


class OperatorBookingDestinationResponse(BaseModel):
    """Destination metadata required by an assigned operator."""

    id: UUID
    name: str
    region: str


class BookingStatusHistoryResponse(BaseModel):
    """Audit event without internal principal identifiers."""

    model_config = ConfigDict(from_attributes=True)

    from_status: BookingStatus | None
    to_status: BookingStatus
    actor_type: StatusActorType
    reason: str | None
    occurred_at: datetime


class DemoQuoteResponse(BaseModel):
    """Synthetic quote details that cannot represent a real reservation."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    amount_minor: int
    currency: str
    expires_at: datetime
    terms: str | None
    is_demo: bool
    disclaimer: str = (
        "Synthetic demonstration quote only; it is not live availability or a "
        "real-world reservation offer."
    )


class OperatorBookingSummaryResponse(BaseModel):
    """PII-minimized booking row for an operator queue."""

    booking_reference: str
    status: BookingStatus
    destination: OperatorBookingDestinationResponse
    travel_start_date: date
    travel_end_date: date
    party_size: int
    created_at: datetime
    updated_at: datetime


class OperatorBookingListResponse(BaseModel):
    """A page of bookings assigned to the authenticated organization."""

    items: list[OperatorBookingSummaryResponse]
    total: int
    limit: int
    offset: int


class OperatorBookingDetailResponse(OperatorBookingSummaryResponse):
    """Protected booking detail visible only to the assigned organization."""

    customer_name: str
    customer_email: str | None
    customer_phone: str | None
    customer_contact_preference: str
    customer_consent: bool
    special_requests: str | None
    status_history: list[BookingStatusHistoryResponse]
    quote: DemoQuoteResponse | None
    reservation_disclaimer: str = (
        "SafariSmart demonstration statuses do not prove that a real-world "
        "reservation has been made."
    )


class DemoQuoteCreate(BaseModel):
    """Input for a time-limited synthetic quote."""

    amount_minor: int = Field(gt=0, le=1_000_000_000)
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$")
    expires_at: datetime
    terms: str | None = Field(default=None, max_length=2000)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        """Persist ISO-style currency codes in uppercase."""

        return value.upper()

    @field_validator("expires_at")
    @classmethod
    def validate_expiry(cls, value: datetime) -> datetime:
        """Require an aware future expiry timestamp."""

        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("expires_at must include a timezone")
        if value <= datetime.now(UTC):
            raise ValueError("expires_at must be in the future")
        return value


class OperatorDecisionRequest(BaseModel):
    """Auditable operator decision input."""

    reason: AuditReason
