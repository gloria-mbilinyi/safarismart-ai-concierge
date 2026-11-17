"""FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.config import Settings, get_settings
from app.db.session import Database
from app.integrations.concierge_provider import build_ranking_provider


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
    application.include_router(api_router, prefix=app_settings.api_v1_prefix)
    return application


app = create_app()
