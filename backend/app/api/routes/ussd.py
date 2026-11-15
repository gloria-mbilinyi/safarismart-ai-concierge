"""Africa's Talking form-encoded USSD callback (read-only)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Form
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.services.destinations import list_destinations
from app.services.ussd import MAX_DESTINATIONS, MAX_USSD_INPUT_LENGTH, render_ussd


router = APIRouter(prefix="/v1/ussd", tags=["ussd"])



@router.post("", response_class=PlainTextResponse)
def ussd_callback(
    session_id: Annotated[str, Form(alias="sessionId", min_length=1, max_length=128)],
    service_code: Annotated[str, Form(alias="serviceCode", min_length=1, max_length=32)],
    phone_number: Annotated[str, Form(alias="phoneNumber", min_length=3, max_length=20)],
    session: Annotated[Session, Depends(get_db_session)],
    text: Annotated[str, Form(alias="text")] = "",
) -> PlainTextResponse:

    """Return an AT-compatible CON/END response without storing phone data.

    The cumulative input encodes selections, so a persistent session store is
    unnecessary for this read-only MVP. All pricing and booking actions are
    intentionally excluded; this callback must be publicly reachable via HTTPS.
    """

    destinations = []
    if len(text) <= MAX_USSD_INPUT_LENGTH and (
        text.startswith("1*1") or text.startswith("2*1")
    ):
        destinations, _ = list_destinations(session, limit=MAX_DESTINATIONS)

    return PlainTextResponse(render_ussd(text, destinations))
