"""Discovery scheduler service.

Manages scheduled automatic discovery runs based on configuration.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import structlog

from walltrack.data.supabase.client import get_supabase_client
from walltrack.data.supabase.repositories.discovery_repo import DiscoveryRepository
from walltrack.discovery.models import DiscoveryRunParams, TriggerType
from walltrack.scheduler.tasks.discovery_task import run_discovery_task

if TYPE_CHECKING:
    from walltrack.data.supabase.client import SupabaseClient

log = structlog.get_logger()


class DiscoveryScheduler:
    """Manages scheduled discovery runs.

    The scheduler runs in the background and executes discovery tasks
    at configured intervals. Configuration is persisted in the database.
    """

    def __init__(self) -> None:
        """Initialize scheduler with default values."""
        self._enabled: bool = True
        self._schedule_hours: int = 6
        self._params: DiscoveryRunParams = DiscoveryRunParams()
        self._next_run: datetime | None = None
        self._last_run: datetime | None = None
        self._running: bool = False
        self._task: asyncio.Task[None] | None = None
        self._config_loaded: bool = False

    async def load_config(self) -> None:
        """Load configuration from database."""
        supabase = await get_supabase_client()

        result = await supabase.select(
            "discovery_config",
            filters={"id": 1},
        )

        if result:
            config = result[0]
            self._enabled = config.get("enabled", True)
            self._schedule_hours = config.get("schedule_hours", 6)
            self._params = DiscoveryRunParams(
                min_price_change_pct=float(config.get("min_price_change_pct", 100.0)),
                min_volume_usd=float(config.get("min_volume_usd", 50000.0)),
                max_token_age_hours=int(config.get("max_token_age_hours", 72)),
                early_window_minutes=int(config.get("early_window_minutes", 30)),
                min_profit_pct=float(config.get("min_profit_pct", 50.0)),
                max_tokens=int(config.get("max_tokens", 20)),
            )

        # Get last run time from discovery runs
        await self._load_last_run_time(supabase)

        self._calculate_next_run()
        self._config_loaded = True

        log.info(
            "scheduler_config_loaded",
            enabled=self._enabled,
            schedule_hours=self._schedule_hours,
            next_run=self._next_run.isoformat() if self._next_run else None,
        )

    async def _load_last_run_time(self, supabase: SupabaseClient) -> None:
        """Load the last scheduled run time from database."""
        result = await supabase.select(
            "discovery_runs",
            columns=["started_at"],
            filters={"trigger_type": "scheduled", "status": "completed"},
            order_by="started_at",
            order_desc=True,
            limit=1,
        )

        if result:
            started_at = result[0].get("started_at")
            if started_at:
                if isinstance(started_at, str):
                    self._last_run = datetime.fromisoformat(
                        started_at.replace("Z", "+00:00")
                    )
                else:
                    self._last_run = started_at

    async def save_config(
        self,
        enabled: bool | None = None,
        schedule_hours: int | None = None,
        params: DiscoveryRunParams | None = None,
        updated_by: str | None = None,
    ) -> None:
        """Save configuration to database.

        Args:
            enabled: Whether scheduler is enabled.
            schedule_hours: Hours between runs.
            params: Discovery parameters.
            updated_by: User/system that made the change.
        """
        supabase = await get_supabase_client()

        update_data: dict[str, object] = {
            "updated_at": datetime.now(UTC).isoformat(),
        }

        if enabled is not None:
            self._enabled = enabled
            update_data["enabled"] = enabled

        if schedule_hours is not None:
            self._schedule_hours = schedule_hours
            update_data["schedule_hours"] = schedule_hours

        if params is not None:
            self._params = params
            update_data.update(params.model_dump())

        if updated_by:
            update_data["updated_by"] = updated_by

        await supabase.update(
            "discovery_config",
            {"id": 1},
            update_data,
        )

        self._calculate_next_run()

        log.info(
            "scheduler_config_saved",
            enabled=self._enabled,
            schedule_hours=self._schedule_hours,
            next_run=self._next_run.isoformat() if self._next_run else None,
        )

    def _calculate_next_run(self) -> None:
        """Calculate next scheduled run time."""
        if not self._enabled:
            self._next_run = None
            return

        base_time = self._last_run or datetime.now(UTC)
        self._next_run = base_time + timedelta(hours=self._schedule_hours)

        # If next run is in the past, schedule for now + interval
        if self._next_run <= datetime.now(UTC):
            self._next_run = datetime.now(UTC) + timedelta(hours=self._schedule_hours)

    async def start(self) -> None:
        """Start the scheduler loop."""
        if self._running:
            log.warning("scheduler_already_running")
            return

        await self.load_config()
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        log.info("discovery_scheduler_started")

    async def stop(self) -> None:
        """Stop the scheduler loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        log.info("discovery_scheduler_stopped")

    async def _run_loop(self) -> None:
        """Main scheduler loop.

        Checks every minute if a scheduled run is due.
        """
        while self._running:
            try:
                if self._enabled and self._next_run:
                    now = datetime.now(UTC)
                    if now >= self._next_run:
                        await self._execute_scheduled_run()

                # Check every minute
                await asyncio.sleep(60)

            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("scheduler_loop_error", error=str(e))
                await asyncio.sleep(60)

    async def _execute_scheduled_run(self) -> None:
        """Execute a scheduled discovery run."""
        log.info("scheduled_discovery_starting")

        supabase = await get_supabase_client()
        repo = DiscoveryRepository(supabase)

        # Create run record
        run = await repo.create_run(
            trigger_type=TriggerType.SCHEDULED,
            params=self._params.model_dump(),
            triggered_by="scheduler",
        )

        start = time.time()

        try:
            result = await run_discovery_task(
                min_price_change_pct=self._params.min_price_change_pct,
                min_volume_usd=self._params.min_volume_usd,
                max_token_age_hours=self._params.max_token_age_hours,
                early_window_minutes=self._params.early_window_minutes,
                min_profit_pct=self._params.min_profit_pct,
                max_tokens=self._params.max_tokens,
                profile_immediately=True,
                trigger_type=TriggerType.SCHEDULED,
                triggered_by="scheduler",
                track_run=False,  # We already created the run record
            )

            await repo.complete_run(
                run_id=run.id,
                tokens_analyzed=result["tokens_analyzed"],
                new_wallets=result["new_wallets"],
                updated_wallets=result["updated_wallets"],
                profiled_wallets=result.get("profiled_wallets", 0),
                duration_seconds=time.time() - start,
                errors=result.get("errors", []),
            )

            self._last_run = datetime.now(UTC)
            self._calculate_next_run()

            log.info(
                "scheduled_discovery_completed",
                run_id=str(run.id),
                new_wallets=result["new_wallets"],
                next_run=self._next_run.isoformat() if self._next_run else None,
            )

        except Exception as e:
            await repo.fail_run(run.id, str(e))
            self._last_run = datetime.now(UTC)
            self._calculate_next_run()
            log.error("scheduled_discovery_failed", error=str(e))

    @property
    def enabled(self) -> bool:
        """Whether scheduler is enabled."""
        return self._enabled

    @property
    def schedule_hours(self) -> int:
        """Hours between scheduled runs."""
        return self._schedule_hours

    @property
    def params(self) -> DiscoveryRunParams:
        """Discovery parameters for scheduled runs."""
        return self._params

    @property
    def next_run(self) -> datetime | None:
        """Next scheduled run time."""
        return self._next_run

    @property
    def last_run(self) -> datetime | None:
        """Last completed run time."""
        return self._last_run

    @property
    def is_running(self) -> bool:
        """Whether scheduler loop is running."""
        return self._running


# Singleton instance
_scheduler: DiscoveryScheduler | None = None


async def get_discovery_scheduler() -> DiscoveryScheduler:
    """Get discovery scheduler singleton.

    Returns:
        The global DiscoveryScheduler instance.
    """
    global _scheduler
    if _scheduler is None:
        _scheduler = DiscoveryScheduler()
    return _scheduler


async def reset_scheduler() -> None:
    """Reset scheduler singleton (for testing)."""
    global _scheduler
    if _scheduler and _scheduler.is_running:
        await _scheduler.stop()
    _scheduler = None
