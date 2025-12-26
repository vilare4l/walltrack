"""FastAPI application factory."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from walltrack.api.middleware.hmac_validation import HMACValidationMiddleware
from walltrack.api.routes import (
    clusters,
    config,
    discovery,
    health,
    risk,
    trades,
    wallets,
    webhooks,
)
from walltrack.config.logging import configure_logging
from walltrack.config.settings import get_settings
from walltrack.core.simulation.context import get_execution_mode, initialize_execution_mode
from walltrack.data.neo4j.client import close_neo4j_client, get_neo4j_client
from walltrack.data.supabase.client import close_supabase_client, get_supabase_client
from walltrack.scheduler.discovery_scheduler import get_discovery_scheduler

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    # Startup
    log.info("application_starting")
    configure_logging()

    # Initialize execution mode
    initialize_execution_mode()
    mode = get_execution_mode()
    log.info("execution_mode_initialized", mode=mode.value)

    # Connect to databases
    try:
        await get_neo4j_client()
    except Exception as e:
        log.warning("neo4j_connection_skipped", error=str(e))

    try:
        await get_supabase_client()
    except Exception as e:
        log.warning("supabase_connection_skipped", error=str(e))

    # Start discovery scheduler
    try:
        scheduler = await get_discovery_scheduler()
        await scheduler.start()
    except Exception as e:
        log.warning("discovery_scheduler_start_skipped", error=str(e))

    log.info("application_started")

    yield

    # Shutdown
    log.info("application_stopping")

    # Stop discovery scheduler
    try:
        scheduler = await get_discovery_scheduler()
        await scheduler.stop()
    except Exception as e:
        log.warning("discovery_scheduler_stop_error", error=str(e))

    await close_neo4j_client()
    await close_supabase_client()
    log.info("application_stopped")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="WallTrack",
        description="Autonomous Solana memecoin trading system",
        version="0.1.0",
        debug=settings.debug,
        lifespan=lifespan,
    )

    # Middleware
    app.add_middleware(HMACValidationMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.debug else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routes
    app.include_router(health.router)
    app.include_router(webhooks.router, prefix="/webhooks")
    app.include_router(wallets.router, prefix="/api/wallets")
    app.include_router(clusters.router, prefix="/api")
    app.include_router(trades.router, prefix="/api/trades")
    app.include_router(config.router, prefix="/api/config")
    app.include_router(risk.router, prefix="/api")
    app.include_router(discovery.router, prefix="/api")

    return app
