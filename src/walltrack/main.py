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
from walltrack.workers.wallet_decay_worker import WalletDecayWorker
from walltrack.workers.wallet_discovery_worker import WalletDiscoveryWorker
from walltrack.workers.wallet_profiling_worker import WalletProfilingWorker

log = structlog.get_logger()

# Config keys for surveillance (shared with config.py)
_CONFIG_KEY_SURVEILLANCE_ENABLED = "surveillance_enabled"
_CONFIG_KEY_SURVEILLANCE_INTERVAL = "surveillance_interval_hours"

# Worker instances (Story 3.5.6 - accessible from status_bar.py for monitoring)
wallet_discovery_worker: WalletDiscoveryWorker | None = None
wallet_profiling_worker: WalletProfilingWorker | None = None
wallet_decay_worker: WalletDecayWorker | None = None


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

    # Configure global RPC rate limiter (Story 3.5.5 - RPC rate limiting)
    try:
        from walltrack.data.supabase.repositories.config_repo import (  # noqa: PLC0415
            ConfigRepository,
        )
        from walltrack.services.solana.rate_limiter import GlobalRateLimiter  # noqa: PLC0415

        client = await get_supabase_client()
        config_repo = ConfigRepository(client)

        # Load RPC delay from config (default: 1000ms = 1 req/sec)
        delay_ms_value = await config_repo.get_value("profiling_rpc_delay_ms")
        delay_ms = int(delay_ms_value) if delay_ms_value else 1000

        GlobalRateLimiter.configure(delay_ms)
        log.info(
            "global_rate_limiter_configured_from_db",
            delay_ms=delay_ms,
            max_rps=1000.0 / delay_ms,
        )
    except Exception as e:
        log.warning("rate_limiter_config_failed_using_default", error=str(e))

    # Start wallet discovery worker (Story 3.5.5 - autonomous wallet discovery)
    # Worker polls database every 120s for tokens with wallets_discovered=false
    # and discovers smart money wallets automatically
    import asyncio  # noqa: PLC0415

    global wallet_discovery_worker, wallet_profiling_worker, wallet_decay_worker

    wallet_discovery_worker = WalletDiscoveryWorker(poll_interval=120)
    discovery_worker_task = asyncio.create_task(wallet_discovery_worker.run())
    log.info("wallet_discovery_worker_started", poll_interval=120)

    # Start wallet profiling worker (Stories 3.2 + 3.3 + 3.5)
    # Worker polls database every 60s for wallets with status='discovered'
    # and processes them automatically (performance + behavioral + watchlist)
    wallet_profiling_worker = WalletProfilingWorker(poll_interval=60)
    wallet_worker_task = asyncio.create_task(wallet_profiling_worker.run())
    log.info("wallet_profiling_worker_started", poll_interval=60)

    # Start wallet decay worker (Story 3.4 - autonomous decay detection)
    # Worker polls database every 4 hours for wallets with status='profiled' or 'watchlisted'
    # and checks for performance degradation automatically
    wallet_decay_worker = WalletDecayWorker(poll_interval=14400)  # 4 hours
    decay_worker_task = asyncio.create_task(wallet_decay_worker.run())
    log.info("wallet_decay_worker_started", poll_interval=14400)

    yield

    # Shutdown
    log.info("shutdown_initiated")

    # Stop wallet decay worker
    if wallet_decay_worker:
        await wallet_decay_worker.stop()
        decay_worker_task.cancel()
        try:
            await decay_worker_task
        except asyncio.CancelledError:
            pass
        log.info("wallet_decay_worker_stopped")

    # Stop wallet profiling worker
    if wallet_profiling_worker:
        await wallet_profiling_worker.stop()
        wallet_worker_task.cancel()
        try:
            await wallet_worker_task
        except asyncio.CancelledError:
            pass
        log.info("wallet_profiling_worker_stopped")

    # Stop wallet discovery worker
    if wallet_discovery_worker:
        await wallet_discovery_worker.stop()
        discovery_worker_task.cancel()
        try:
            await discovery_worker_task
        except asyncio.CancelledError:
            pass
        log.info("wallet_discovery_worker_stopped")

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
