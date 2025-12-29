"""APScheduler singleton for WallTrack.

This module provides a centralized scheduler instance using the singleton pattern.
The AsyncIOScheduler is used for non-blocking async job execution.

Usage:
    from walltrack.scheduler.scheduler import get_scheduler, start_scheduler

    # In app lifespan startup
    await start_scheduler()

    # In app lifespan shutdown
    await shutdown_scheduler()
"""

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler

log = structlog.get_logger(__name__)

# Singleton scheduler instance
_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    """Get or create the scheduler singleton.

    Returns:
        The AsyncIOScheduler singleton instance.

    Note:
        Creates a new scheduler if one doesn't exist.
        The scheduler is not automatically started.
    """
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
        log.debug("scheduler_created")
    return _scheduler


async def start_scheduler() -> None:
    """Start the scheduler.

    Called from app lifespan on startup.
    Safe to call multiple times - will only start if not running.
    """
    scheduler = get_scheduler()
    if not scheduler.running:
        scheduler.start()
        log.info("scheduler_started")


async def shutdown_scheduler() -> None:
    """Shutdown the scheduler gracefully.

    Called from app lifespan on shutdown.
    Clears the singleton to allow clean restart.
    Safe to call when scheduler is not running.
    """
    global _scheduler
    if _scheduler is not None:
        if _scheduler.running:
            _scheduler.shutdown(wait=True)
            log.info("scheduler_shutdown")
        _scheduler = None
