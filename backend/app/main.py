"""FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config import Settings, get_settings
from app.db.session import Database
from app.integrations.concierge_provider import build_ranking_provider
from app.services.rate_limit import SlidingWindowRateLimiter


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build a configured FastAPI application."""

    app_settings = settings or get_settings()
    database = Database(app_settings.database_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        """Release database resources when the application stops."""

        try:
            yield
        finally:
            database.dispose()

    application = FastAPI(
        title=app_settings.app_name,
        version="0.1.0",
        debug=app_settings.app_debug,
        lifespan=lifespan,
    )
    application.state.database = database
    application.state.settings = app_settings
    application.state.concierge_provider = build_ranking_provider(app_settings)
    application.state.ussd_rate_limiter = SlidingWindowRateLimiter(
        app_settings.ussd_rate_limit_per_minute,
        max_tracked_keys=app_settings.ussd_rate_limit_max_sessions,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.allowed_frontend_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
    )
    application.include_router(api_router, prefix=app_settings.api_v1_prefix)
    return application


app = create_app()
