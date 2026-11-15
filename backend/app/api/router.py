"""Top-level API router."""

from fastapi import APIRouter

from app.api.routes.auth import router as auth_router
from app.api.routes.bookings import router as bookings_router
from app.api.routes.destinations import router as destinations_router
from app.api.routes.health import router as health_router
from app.api.routes.operator import router as operator_router
from app.api.routes.operator_bookings import router as operator_bookings_router
from app.api.routes.ussd import router as ussd_router


api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(destinations_router)
api_router.include_router(bookings_router)
api_router.include_router(operator_router)
api_router.include_router(operator_bookings_router)
api_router.include_router(ussd_router)
