"""FastAPI application entry point."""

from fastapi import FastAPI

from app.api.router import api_router
from app.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build a configured FastAPI application."""

    app_settings = settings or get_settings()
    application = FastAPI(
        title=app_settings.app_name,
        version="0.1.0",
        debug=app_settings.app_debug,
    )
    application.include_router(api_router, prefix=app_settings.api_v1_prefix)
    return application


app = create_app()
