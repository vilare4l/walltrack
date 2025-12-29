"""Scheduled jobs for WallTrack.

This module defines the jobs that run on a schedule:
- Token surveillance: Refreshes token data from DexScreener

Usage:
    from walltrack.scheduler.jobs import schedule_surveillance_job

    # Schedule with 4-hour interval
    schedule_surveillance_job(interval_hours=4)
"""

import structlog
from apscheduler.triggers.interval import IntervalTrigger

from walltrack.scheduler.scheduler import get_scheduler

log = structlog.get_logger(__name__)

# Job ID constants
JOB_ID_SURVEILLANCE = "token_surveillance"

# Valid interval options (hours)
VALID_INTERVALS = frozenset({1, 2, 4, 8})


async def refresh_tokens_job() -> None:
    """Scheduled job to refresh token data from DexScreener.

    Calls TokenDiscoveryService.run_discovery() to fetch and update
    token data in the database.

    Note:
        Handles all errors internally to prevent job crashes.
        Logs success/failure for monitoring.
    """
    log.info("surveillance_job_started")

    try:
        from walltrack.core.discovery.token_discovery import (  # noqa: PLC0415
            TokenDiscoveryService,
        )
        from walltrack.data.supabase.client import get_supabase_client  # noqa: PLC0415
        from walltrack.services.dexscreener.client import DexScreenerClient  # noqa: PLC0415

        supabase = await get_supabase_client()
        dex_client = DexScreenerClient()

        try:
            service = TokenDiscoveryService(supabase, dex_client)
            result = await service.run_discovery()

            log.info(
                "surveillance_job_completed",
                tokens_found=result.tokens_found,
                new_tokens=result.new_tokens,
                updated_tokens=result.updated_tokens,
            )
        finally:
            await dex_client.close()

    except Exception as e:
        log.error("surveillance_job_failed", error=str(e))


def schedule_surveillance_job(interval_hours: int = 4) -> None:
    """Schedule or reschedule the surveillance job.

    Args:
        interval_hours: Hours between runs (1, 2, 4, or 8).

    Raises:
        ValueError: If interval_hours is not a valid option.

    Note:
        If the job already exists, it will be removed first
        and then re-added with the new interval.
    """
    if interval_hours not in VALID_INTERVALS:
        raise ValueError(
            f"Invalid interval: {interval_hours}. Must be one of {sorted(VALID_INTERVALS)}"
        )

    scheduler = get_scheduler()

    # Remove existing job if present
    if scheduler.get_job(JOB_ID_SURVEILLANCE):
        scheduler.remove_job(JOB_ID_SURVEILLANCE)
        log.info("surveillance_job_removed", job_id=JOB_ID_SURVEILLANCE)

    # Add job with new interval
    scheduler.add_job(
        refresh_tokens_job,
        trigger=IntervalTrigger(hours=interval_hours),
        id=JOB_ID_SURVEILLANCE,
        name="Token Surveillance",
        replace_existing=True,
    )

    log.info(
        "surveillance_job_scheduled",
        job_id=JOB_ID_SURVEILLANCE,
        interval_hours=interval_hours,
    )


def unschedule_surveillance_job() -> None:
    """Remove the surveillance job from scheduler.

    Safe to call when job is not scheduled.
    """
    scheduler = get_scheduler()
    if scheduler.get_job(JOB_ID_SURVEILLANCE):
        scheduler.remove_job(JOB_ID_SURVEILLANCE)
        log.info("surveillance_job_unscheduled", job_id=JOB_ID_SURVEILLANCE)


def get_next_run_time() -> str | None:
    """Get the next scheduled run time for surveillance job.

    Returns:
        ISO format datetime string or None if not scheduled.
    """
    scheduler = get_scheduler()
    job = scheduler.get_job(JOB_ID_SURVEILLANCE)

    if job and job.next_run_time:
        return job.next_run_time.isoformat()
    return None
