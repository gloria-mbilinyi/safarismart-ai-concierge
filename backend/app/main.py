"""FastAPI application entry point."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.config import Settings, get_settings
from app.db.session import Database
from app.integrations.concierge_provider import build_concierge_provider
from app.services.notification_delivery import build_notification_delivery_services
from app.services.rate_limit import SlidingWindowRateLimiter
from app.workers.sms_outbox import BoundedNotificationRunner


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build a configured FastAPI application."""

    app_settings = settings or get_settings()
    database = Database(app_settings.database_url)
    notification_runner = BoundedNotificationRunner(
        database.session_factory,
        build_notification_delivery_services(app_settings),
        max_messages=app_settings.notification_dispatch_batch_size,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        """Release database resources when the application stops."""

        stop_dispatch = asyncio.Event()

        async def dispatch_while_active() -> None:
            """Drain bounded batches without keeping a sleeping host awake."""

            await asyncio.to_thread(notification_runner.drain_safely)
            while True:
                try:
                    await asyncio.wait_for(
                        stop_dispatch.wait(),
                        timeout=app_settings.notification_dispatch_interval_seconds,
                    )
                    return
                except TimeoutError:
                    await asyncio.to_thread(notification_runner.drain_safely)

        dispatch_task = (
            asyncio.create_task(dispatch_while_active())
            if notification_runner.configured_channels
            else None
        )
        try:
            yield
        finally:
            if dispatch_task is not None:
                stop_dispatch.set()
                await dispatch_task
            database.dispose()

    application = FastAPI(
        title=app_settings.app_name,
        version="0.1.0",
        debug=app_settings.app_debug,
        lifespan=lifespan,
    )
    application.state.database = database
    application.state.settings = app_settings
    application.state.concierge_provider = build_concierge_provider(app_settings)
    application.state.notification_runner = notification_runner
    application.state.ussd_rate_limiter = SlidingWindowRateLimiter(
        app_settings.ussd_rate_limit_per_minute,
        max_tracked_keys=app_settings.ussd_rate_limit_max_sessions,
    )
    application.state.booking_rate_limiter = SlidingWindowRateLimiter(
        app_settings.booking_rate_limit_per_minute,
        max_tracked_keys=app_settings.booking_rate_limit_max_clients,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.allowed_frontend_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
    )
    application.include_router(api_router, prefix=app_settings.api_v1_prefix)
    if app_settings.frontend_dist_path is not None:
        frontend_root = Path(app_settings.frontend_dist_path).resolve()
        index_path = frontend_root / "index.html"
        assets_path = frontend_root / "assets"
        if not index_path.is_file() or not assets_path.is_dir():
            raise RuntimeError(
                "FRONTEND_DIST_PATH must contain a built Vite application"
            )
        application.mount(
            "/assets",
            StaticFiles(directory=assets_path),
            name="frontend-assets",
        )

        @application.get("/{full_path:path}", include_in_schema=False)
        def serve_frontend(full_path: str) -> FileResponse:
            """Serve safe root files or the SPA shell without shadowing API 404s."""

            api_path = app_settings.api_v1_prefix.lstrip("/")
            if full_path == api_path or full_path.startswith(f"{api_path}/"):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
            candidate = (frontend_root / full_path).resolve()
            if candidate.is_relative_to(frontend_root) and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(index_path)
    return application


app = create_app()
