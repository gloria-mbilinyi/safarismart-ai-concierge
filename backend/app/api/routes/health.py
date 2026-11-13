"""Service health endpoint."""

from fastapi import APIRouter, status

from app.schemas.health import HealthResponse


router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Check service health",
)
async def health_check() -> HealthResponse:
    """Report whether the API process is available."""

    return HealthResponse(status="ok")
