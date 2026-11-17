"""Booking request API schemas."""

from datetime import date, datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    model_validator,
)

from app.models.enums import BookingStatus


def strip_non_empty(value: str) -> str:
    """Trim a required string and reject whitespace-only values."""

    normalized = value.strip()
    if not normalized:
        raise ValueError("must not be blank")
    return normalized


RequiredName = Annotated[
    str,
    StringConstraints(min_length=2, max_length=150),
    AfterValidator(strip_non_empty),
]
PhoneNumber = Annotated[
    str,
    StringConstraints(pattern=r"^\+[1-9]\d{7,14}$"),
]
SpecialRequests = Annotated[
    str,
    StringConstraints(max_length=1000),
    AfterValidator(strip_non_empty),
]


class BookingRequestCreate(BaseModel):
    """Validated traveller input for a booking request submission."""

    model_config = ConfigDict(str_strip_whitespace=True)

    destination_id: UUID
    travel_start_date: date
    travel_end_date: date
    party_size: int = Field(ge=1, le=50)
    customer_name: RequiredName
    customer_email: EmailStr | None = None
    customer_phone: PhoneNumber | None = None
    customer_contact_preference: Literal["email", "phone"]
    customer_language: Literal["en", "sw"] = "en"
    customer_consent: Literal[True]
    special_requests: SpecialRequests | None = None

    @model_validator(mode="after")
    def validate_booking_details(self) -> Self:
        """Enforce travel chronology and preferred-contact requirements."""

        if self.travel_start_date < date.today():
            raise ValueError("travel_start_date cannot be in the past")
        if self.travel_end_date < self.travel_start_date:
            raise ValueError("travel_end_date cannot be before travel_start_date")
        if self.customer_contact_preference == "email" and self.customer_email is None:
            raise ValueError("customer_email is required when email is preferred")
        if self.customer_contact_preference == "phone" and self.customer_phone is None:
            raise ValueError("customer_phone is required when phone is preferred")
        return self


class BookingNotificationAcknowledgement(BaseModel):
    """Truthful public state for the selected external contact channel."""

    channel: Literal["email", "sms"]
    state: Literal["queued", "unavailable"]
    mode: Literal[
        "resend",
        "africastalking_sandbox",
        "africastalking_production",
        "local",
        "unconfigured",
    ]


class BookingRequestResponse(BaseModel):
    """Non-sensitive acknowledgement returned after submission."""

    booking_reference: str
    status: BookingStatus
    destination_id: UUID
    travel_start_date: date
    travel_end_date: date
    party_size: int
    created_at: datetime
    notification: BookingNotificationAcknowledgement
