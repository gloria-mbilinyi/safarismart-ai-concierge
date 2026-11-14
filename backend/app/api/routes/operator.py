"""Authenticated operator identity endpoint."""

from fastapi import APIRouter

from app.api.dependencies.auth import CurrentOperatorUser
from app.schemas.operator import CurrentOperatorResponse, OperatorOrganizationResponse


router = APIRouter(prefix="/v1/operator", tags=["operator-management"])


@router.get("/me", response_model=CurrentOperatorResponse)
def get_current_operator(user: CurrentOperatorUser) -> CurrentOperatorResponse:
    """Return the authenticated user without password or token metadata."""

    return CurrentOperatorResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        operator=OperatorOrganizationResponse.model_validate(user.operator),
    )
