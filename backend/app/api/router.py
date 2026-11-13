"""Top-level API router."""

from fastapi import APIRouter

from app.api.routes.bookings import router as bookings_router
from app.api.routes.destinations import router as destinations_router
from app.api.routes.health import router as health_router


api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(destinations_router)
api_router.include_router(bookings_router)
