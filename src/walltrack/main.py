"""WallTrack V2 - Main application entry point."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import gradio as gr
import structlog
import uvicorn
from fastapi import FastAPI

from walltrack.api.routes import health
from walltrack.config import get_settings
from walltrack.core.exceptions import DatabaseConnectionError
from walltrack.data.neo4j.client import close_neo4j_client, get_neo4j_client
from walltrack.data.supabase.client import close_supabase_client, get_supabase_client
from walltrack.scheduler.scheduler import shutdown_scheduler, start_scheduler
from walltrack.ui.app import create_dashboard

log = structlog.get_logger()

# Config keys for surveillance (shared with config.py)
_CONFIG_KEY_SURVEILLANCE_ENABLED = "surveillance_enabled"
_CONFIG_KEY_SURVEILLANCE_INTERVAL = "surveillance_interval_hours"


async def _restore_surveillance_job() -> None:
    """Restore surveillance job from config on startup.

    Loads surveillance settings from config and schedules the job
    if surveillance is enabled. This ensures the job persists across
    app restarts.
    """
    try:
        from walltrack.data.supabase.repositories.config_repo import (  # noqa: PLC0415
            ConfigRepository,
        )
        from walltrack.scheduler.jobs import schedule_surveillance_job  # noqa: PLC0415

        client = await get_supabase_client()
        repo = ConfigRepository(client)

        # Check if surveillance is enabled (default: True)
        enabled_value = await repo.get_value(_CONFIG_KEY_SURVEILLANCE_ENABLED)
        enabled = enabled_value != "false"  # Default True if not set or "true"

        if enabled:
            # Get interval (default: 4 hours)
            interval_value = await repo.get_value(_CONFIG_KEY_SURVEILLANCE_INTERVAL)
            interval_hours = int(interval_value) if interval_value else 4

            schedule_surveillance_job(interval_hours=interval_hours)
            log.info(
                "surveillance_job_restored",
                interval_hours=interval_hours,
            )
        else:
            log.info("surveillance_disabled_on_startup")

    except Exception as e:
        log.warning("surveillance_restore_failed", error=str(e))


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifecycle.

    On startup: Connect to databases (gracefully handle failures).
    On shutdown: Close all database connections.
    """
    # Startup
    try:
        await get_supabase_client()
        log.info("startup_supabase_connected")
    except DatabaseConnectionError as e:
        log.warning("startup_supabase_failed", error=str(e))

    try:
        await get_neo4j_client()
        log.info("startup_neo4j_connected")
    except DatabaseConnectionError as e:
        log.warning("startup_neo4j_failed", error=str(e))

    # Start scheduler (Story 2.2)
    await start_scheduler()

    # Restore surveillance job if enabled (Story 2.2 - code review fix)
    await _restore_surveillance_job()

    yield

    # Shutdown
    await shutdown_scheduler()
    await close_supabase_client()
    await close_neo4j_client()
    log.info("shutdown_complete")


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance.
    """
    settings = get_settings()

    application = FastAPI(
        title=settings.app_name,
        description="Autonomous Trading Intelligence for Solana Memecoins",
        version=settings.app_version,
        lifespan=lifespan,
    )

    # Register API routes
    application.include_router(health.router, prefix="/api")

    # Mount Gradio dashboard
    # Must be mounted AFTER registering API routes
    dashboard = create_dashboard()
    application = gr.mount_gradio_app(
        app=application,
        blocks=dashboard,
        path="/dashboard",
    )
    log.info("dashboard_mounted", path="/dashboard")

    return application  # type: ignore[no-any-return]


# Create the app instance
app = create_app()


def main() -> None:
    """Run the application with uvicorn."""
    settings = get_settings()
    uvicorn.run(
        "walltrack.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    main()
