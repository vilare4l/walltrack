# Story 9.3: Configurable Discovery Scheduler

## Story Info
- **Epic**: Epic 9 - Discovery Management & Scheduling
- **Status**: ready
- **Priority**: High
- **Depends on**: Story 9.1, Story 9.2

## User Story

**As an** operator,
**I want** to configure the discovery scheduler from the UI,
**So that** I can control when and how often discovery runs automatically.

## Acceptance Criteria

### AC 1: Enable/Disable Scheduler
**Given** the scheduler config
**When** I toggle the enabled switch
**Then** automatic discovery is enabled/disabled
**And** next scheduled run is shown/hidden
**And** change is persisted

### AC 2: Configure Frequency
**Given** scheduler is enabled
**When** I change the frequency setting
**Then** schedule is updated
**And** next run time is recalculated
**And** change takes effect immediately

### AC 3: Configure Parameters
**Given** scheduler config
**When** I update discovery parameters
**Then** next run uses new parameters
**And** parameters are validated
**And** invalid values show error

### AC 4: Show Schedule Status
**Given** scheduler is running
**When** I view the config
**Then** I see enabled/disabled state
**And** I see next scheduled run time
**And** I see last run time and result

### AC 5: Persist Configuration
**Given** configuration changes
**When** changes are saved
**Then** configuration is stored in database
**And** survives application restart
**And** is loaded on startup

## Technical Specifications

### Database Schema

```sql
-- Discovery configuration table
CREATE TABLE IF NOT EXISTS discovery_config (
    id INTEGER PRIMARY KEY DEFAULT 1,
    enabled BOOLEAN DEFAULT TRUE,
    schedule_hours INTEGER DEFAULT 6,

    -- Default parameters
    min_price_change_pct DECIMAL(5,2) DEFAULT 100.0,
    min_volume_usd DECIMAL(15,2) DEFAULT 50000.0,
    max_token_age_hours INTEGER DEFAULT 72,
    early_window_minutes INTEGER DEFAULT 30,
    min_profit_pct DECIMAL(5,2) DEFAULT 50.0,
    max_tokens INTEGER DEFAULT 20,
    profile_immediately BOOLEAN DEFAULT TRUE,

    updated_at TIMESTAMPTZ DEFAULT NOW(),
    updated_by VARCHAR(100),

    CONSTRAINT single_row CHECK (id = 1)
);

-- Insert default config
INSERT INTO discovery_config (id) VALUES (1) ON CONFLICT DO NOTHING;
```

### Scheduler Service

**src/walltrack/scheduler/discovery_scheduler.py:**
```python
"""Discovery scheduler service."""

import asyncio
from datetime import datetime, timedelta, UTC
from typing import Optional

import structlog

from walltrack.data.supabase.client import get_supabase_client
from walltrack.data.supabase.repositories.discovery_repo import DiscoveryRepository
from walltrack.discovery.models import DiscoveryRunParams, TriggerType
from walltrack.scheduler.tasks.discovery_task import run_discovery_task

log = structlog.get_logger()


class DiscoveryScheduler:
    """Manages scheduled discovery runs."""

    def __init__(self) -> None:
        self._enabled: bool = True
        self._schedule_hours: int = 6
        self._params: DiscoveryRunParams = DiscoveryRunParams()
        self._next_run: Optional[datetime] = None
        self._last_run: Optional[datetime] = None
        self._running: bool = False
        self._task: Optional[asyncio.Task] = None

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
                min_price_change_pct=config.get("min_price_change_pct", 100.0),
                min_volume_usd=config.get("min_volume_usd", 50000.0),
                max_token_age_hours=config.get("max_token_age_hours", 72),
                early_window_minutes=config.get("early_window_minutes", 30),
                min_profit_pct=config.get("min_profit_pct", 50.0),
                max_tokens=config.get("max_tokens", 20),
            )

        self._calculate_next_run()
        log.info(
            "scheduler_config_loaded",
            enabled=self._enabled,
            schedule_hours=self._schedule_hours,
            next_run=self._next_run,
        )

    async def save_config(
        self,
        enabled: Optional[bool] = None,
        schedule_hours: Optional[int] = None,
        params: Optional[DiscoveryRunParams] = None,
        updated_by: Optional[str] = None,
    ) -> None:
        """Save configuration to database."""
        supabase = await get_supabase_client()

        update_data = {"updated_at": datetime.now(UTC).isoformat()}

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
        log.info("scheduler_config_saved", **update_data)

    def _calculate_next_run(self) -> None:
        """Calculate next scheduled run time."""
        if not self._enabled:
            self._next_run = None
            return

        base_time = self._last_run or datetime.now(UTC)
        self._next_run = base_time + timedelta(hours=self._schedule_hours)

    async def start(self) -> None:
        """Start the scheduler loop."""
        if self._running:
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
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        log.info("discovery_scheduler_stopped")

    async def _run_loop(self) -> None:
        """Main scheduler loop."""
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

        import time
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
                new_wallets=result["new_wallets"],
                next_run=self._next_run,
            )

        except Exception as e:
            await repo.fail_run(run.id, str(e))
            log.error("scheduled_discovery_failed", error=str(e))

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def schedule_hours(self) -> int:
        return self._schedule_hours

    @property
    def params(self) -> DiscoveryRunParams:
        return self._params

    @property
    def next_run(self) -> Optional[datetime]:
        return self._next_run

    @property
    def last_run(self) -> Optional[datetime]:
        return self._last_run


# Singleton
_scheduler: Optional[DiscoveryScheduler] = None


async def get_discovery_scheduler() -> DiscoveryScheduler:
    """Get discovery scheduler singleton."""
    global _scheduler
    if _scheduler is None:
        _scheduler = DiscoveryScheduler()
    return _scheduler
```

## Implementation Tasks

- [x] Create discovery_config database table
- [x] Implement DiscoveryScheduler class
- [x] Add config load/save methods
- [x] Implement scheduler loop
- [x] Integrate with app startup/shutdown
- [x] Update API endpoints to use scheduler
- [x] Write tests

## Definition of Done

- [x] Scheduler loads config on startup
- [x] Config changes are persisted
- [x] Scheduler runs discovery at configured intervals
- [x] Enable/disable works correctly
- [x] Frequency changes take effect
- [x] Tests pass

## Dev Agent Record

### Implementation Notes (2024-12-24)
- Created migration `020_discovery_config.sql` with singleton pattern
- Implemented `DiscoveryScheduler` class with full lifecycle management
- Added config persistence via `save_config` method
- Scheduler loop runs every minute checking for due runs
- Integrated with FastAPI lifespan (start on startup, stop on shutdown)
- Updated discovery API endpoints to use scheduler for config
- Added 21 unit tests (all passing)

## File List

### New Files
- `src/walltrack/scheduler/discovery_scheduler.py` - Scheduler service with singleton
- `src/walltrack/data/supabase/migrations/020_discovery_config.sql` - Schema
- `tests/unit/scheduler/test_discovery_scheduler.py` - 21 tests

### Modified Files
- `src/walltrack/api/routes/discovery.py` - Use scheduler for config endpoints
- `src/walltrack/api/app.py` - Start/stop scheduler in lifespan
