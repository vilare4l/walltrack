# Story 2.2: Token Surveillance Scheduler

**Status:** done
**Epic:** 2 - Token Discovery & Surveillance
**Created:** 2025-12-29
**Sprint Artifacts:** docs/sprint-artifacts/epic-2/

---

## Story

**As an** operator,
**I want** tokens to refresh automatically on a schedule,
**So that** I always have up-to-date token data.

**FRs Covered:** FR2 (System can refresh token data on a configurable schedule)

---

## Acceptance Criteria

### AC1: APScheduler Configuration
- [x] APScheduler is installed and configured
- [x] Scheduler runs in background with app lifecycle
- [x] Scheduler uses async job executor for non-blocking execution
- [x] Graceful shutdown on app termination

### AC2: Surveillance Job
- [x] Job `refresh_tokens` calls `TokenDiscoveryService.run_discovery()`
- [x] Job runs at configurable interval (default: 4 hours)
- [x] `last_checked` timestamp updated on each token refresh
- [x] Job logs execution start/end with structlog

### AC3: Config Page Schedule Settings
- [x] Discovery section shows "Surveillance Schedule" subsection
- [x] Dropdown with interval options: 1h, 2h, 4h, 8h
- [x] Shows next scheduled run time
- [x] Can enable/disable surveillance

### AC4: Status Bar Update
- [x] Status bar shows discovery status: "Discovery: Xh ago (next: Yh)"
- [x] Shows relative time since last discovery
- [x] Shows relative time until next scheduled run
- [x] Updates on 30s refresh cycle

### AC5: Interval Persistence
- [x] Interval setting stored in Supabase `config` table
- [x] Key: `surveillance_interval_hours`
- [x] Default: 4 hours
- [x] Changes take effect immediately (reschedule job)

---

## Tasks / Subtasks

### Task 1: APScheduler Setup (AC: 1)
- [x] 1.1 Verify `apscheduler>=3.10.0` is in pyproject.toml (already installed)
- [x] 1.2 Create `src/walltrack/scheduler/scheduler.py` with scheduler singleton
- [x] 1.3 Create `src/walltrack/scheduler/jobs.py` with job definitions
- [x] 1.4 Integrate scheduler start/stop in `main.py` lifespan
- [x] 1.5 Add unit tests for scheduler setup

### Task 2: Surveillance Job Implementation (AC: 2)
- [x] 2.1 Create `refresh_tokens_job()` async function
- [x] 2.2 Call `TokenDiscoveryService.run_discovery()` from job
- [x] 2.3 Update all tokens' `last_checked` timestamp
- [x] 2.4 Add structlog logging for job execution
- [x] 2.5 Add unit tests with mocked discovery service

### Task 3: Config Page UI (AC: 3, 5)
- [x] 3.1 Add "Surveillance Schedule" subsection to Discovery accordion
- [x] 3.2 Add interval dropdown (1h, 2h, 4h, 8h)
- [x] 3.3 Add enable/disable toggle
- [x] 3.4 Show next scheduled run time
- [x] 3.5 Wire save button to persist interval in config
- [x] 3.6 Trigger job reschedule on interval change

### Task 4: Status Bar Enhancement (AC: 4)
- [x] 4.1 Add `get_discovery_status()` function to status_bar.py
- [x] 4.2 Query last discovery time from tokens table
- [x] 4.3 Query next scheduled run from scheduler
- [x] 4.4 Format as "Discovery: Xh ago (next: Yh)"
- [x] 4.5 Update `render_status_html()` to include discovery status

### Task 5: Integration Test (AC: all)
- [x] 5.1 Test scheduler starts with app
- [x] 5.2 Test job executes at scheduled time (mock time)
- [x] 5.3 Test interval change reschedules job
- [x] 5.4 Test status bar shows correct times

---

## Dev Notes

### Architecture Pattern

```
Config Page UI
    │
    ├──► ConfigRepository (store interval)
    │
    └──► Scheduler (reschedule job)
            │
            └──► refresh_tokens_job()
                    │
                    └──► TokenDiscoveryService.run_discovery()
```

**Important:** Scheduler is infrastructure, not business logic.
- `scheduler/` = APScheduler setup + job registration
- `core/discovery/` = Business logic (TokenDiscoveryService)

### APScheduler Setup

**Documentation:** https://apscheduler.readthedocs.io/en/stable/

```python
# src/walltrack/scheduler/scheduler.py

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
import structlog

log = structlog.get_logger(__name__)

# Singleton scheduler instance
_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    """Get or create the scheduler singleton."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


async def start_scheduler() -> None:
    """Start the scheduler (called from app lifespan)."""
    scheduler = get_scheduler()
    if not scheduler.running:
        scheduler.start()
        log.info("scheduler_started")


async def shutdown_scheduler() -> None:
    """Shutdown the scheduler gracefully."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=True)
        log.info("scheduler_shutdown")
        _scheduler = None
```

### Surveillance Job

```python
# src/walltrack/scheduler/jobs.py

import structlog
from apscheduler.triggers.interval import IntervalTrigger

from walltrack.scheduler.scheduler import get_scheduler

log = structlog.get_logger(__name__)

JOB_ID_SURVEILLANCE = "token_surveillance"


async def refresh_tokens_job() -> None:
    """Scheduled job to refresh token data from DexScreener."""
    log.info("surveillance_job_started")

    try:
        from walltrack.core.discovery.token_discovery import TokenDiscoveryService
        from walltrack.data.supabase.client import get_supabase_client
        from walltrack.services.dexscreener.client import DexScreenerClient

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
    """
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
```

### Main.py Lifespan Integration

```python
# In src/walltrack/main.py

from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown."""
    # Startup
    from walltrack.scheduler.scheduler import start_scheduler, shutdown_scheduler
    from walltrack.scheduler.jobs import schedule_surveillance_job

    await start_scheduler()

    # Load interval from config (default 4h)
    # schedule_surveillance_job(interval_hours=4)  # Will be loaded from config

    yield

    # Shutdown
    await shutdown_scheduler()


app = FastAPI(lifespan=lifespan)
```

### Config Page UI Pattern

**CRITICAL:** Gradio event handlers MUST be synchronous. Use `asyncio.run()` wrappers.

```python
# In config.py Discovery section

INTERVAL_CHOICES = [
    ("1 hour", 1),
    ("2 hours", 2),
    ("4 hours (recommended)", 4),
    ("8 hours", 8),
]


def _get_surveillance_interval() -> int:
    """Get current surveillance interval from config."""
    try:
        from walltrack.data.supabase.client import get_supabase_client
        from walltrack.data.supabase.repositories.config_repo import ConfigRepository

        async def _async():
            client = await get_supabase_client()
            repo = ConfigRepository(client)
            value = await repo.get_value("surveillance_interval_hours")
            return int(value) if value else 4

        return asyncio.run(_async())
    except Exception:
        return 4  # Default


def _set_surveillance_interval(hours: int) -> str:
    """Set surveillance interval and reschedule job."""
    try:
        from walltrack.data.supabase.client import get_supabase_client
        from walltrack.data.supabase.repositories.config_repo import ConfigRepository
        from walltrack.scheduler.jobs import schedule_surveillance_job

        async def _async():
            client = await get_supabase_client()
            repo = ConfigRepository(client)
            await repo.set_value("surveillance_interval_hours", str(hours))

        asyncio.run(_async())

        # Reschedule with new interval
        schedule_surveillance_job(interval_hours=hours)

        return f"Interval set to {hours}h. Job rescheduled."
    except Exception as e:
        return f"Error: {e}"


def _get_next_run_display() -> str:
    """Get next scheduled run time for display."""
    from walltrack.scheduler.jobs import get_next_run_time
    from walltrack.ui.components.status_bar import get_relative_time
    from datetime import datetime, UTC

    next_run = get_next_run_time()
    if next_run:
        # Parse ISO datetime and get relative time
        dt = datetime.fromisoformat(next_run.replace("Z", "+00:00"))
        now = datetime.now(UTC)
        diff = dt - now

        if diff.total_seconds() > 0:
            hours = int(diff.total_seconds() / 3600)
            minutes = int((diff.total_seconds() % 3600) / 60)
            if hours > 0:
                return f"in {hours}h {minutes}m"
            return f"in {minutes}m"
    return "Not scheduled"


# In render() function, inside Discovery accordion:
with gr.Accordion("Discovery Settings", open=True):
    gr.Markdown("### Token Discovery")

    # ... existing Run Discovery button ...

    gr.Markdown("---")
    gr.Markdown("### Surveillance Schedule")

    current_interval = _get_surveillance_interval()

    interval_dropdown = gr.Dropdown(
        choices=[(label, val) for label, val in INTERVAL_CHOICES],
        value=current_interval,
        label="Refresh Interval",
    )

    next_run_display = gr.Textbox(
        value=_get_next_run_display,
        label="Next Scheduled Run",
        interactive=False,
        every=30,  # Update every 30s
    )

    interval_status = gr.Textbox(
        value="",
        label="Status",
        interactive=False,
    )

    interval_dropdown.change(
        fn=_set_surveillance_interval,
        inputs=[interval_dropdown],
        outputs=[interval_status],
    )
```

### Enable/Disable Toggle Implementation

**Config Keys:**
```python
CONFIG_KEY_SURVEILLANCE_ENABLED = "surveillance_enabled"
CONFIG_KEY_SURVEILLANCE_INTERVAL = "surveillance_interval_hours"
```

**Toggle Function (add to config.py):**
```python
def _toggle_surveillance(enabled: bool) -> str:
    """Enable or disable surveillance scheduler."""
    try:
        from walltrack.scheduler.jobs import (
            schedule_surveillance_job,
            unschedule_surveillance_job,
        )
        from walltrack.data.supabase.client import get_supabase_client
        from walltrack.data.supabase.repositories.config_repo import ConfigRepository

        async def _async():
            client = await get_supabase_client()
            repo = ConfigRepository(client)
            await repo.set_value(CONFIG_KEY_SURVEILLANCE_ENABLED, str(enabled).lower())

        asyncio.run(_async())

        if enabled:
            interval = _get_surveillance_interval()
            schedule_surveillance_job(interval_hours=interval)
            return "✅ Surveillance enabled"
        else:
            unschedule_surveillance_job()
            return "⏸️ Surveillance disabled"

    except Exception as e:
        return f"Error: {e}"


def _get_surveillance_enabled() -> bool:
    """Check if surveillance is enabled."""
    try:
        from walltrack.data.supabase.client import get_supabase_client
        from walltrack.data.supabase.repositories.config_repo import ConfigRepository

        async def _async():
            client = await get_supabase_client()
            repo = ConfigRepository(client)
            value = await repo.get_value(CONFIG_KEY_SURVEILLANCE_ENABLED)
            return value == "true" if value else True  # Default enabled

        return asyncio.run(_async())
    except Exception:
        return True  # Default enabled
```

**Unschedule Function (add to jobs.py):**
```python
def unschedule_surveillance_job() -> None:
    """Remove the surveillance job from scheduler."""
    scheduler = get_scheduler()
    if scheduler.get_job(JOB_ID_SURVEILLANCE):
        scheduler.remove_job(JOB_ID_SURVEILLANCE)
        log.info("surveillance_job_unscheduled", job_id=JOB_ID_SURVEILLANCE)
```

**UI Toggle (add to Discovery accordion):**
```python
# After interval_dropdown
surveillance_enabled = gr.Checkbox(
    value=_get_surveillance_enabled,
    label="Enable Surveillance",
)

toggle_status = gr.Textbox(
    value="",
    label="",
    interactive=False,
)

surveillance_enabled.change(
    fn=_toggle_surveillance,
    inputs=[surveillance_enabled],
    outputs=[toggle_status],
)
```

### Status Bar Enhancement

```python
# Add to status_bar.py

def get_discovery_status() -> tuple[str, str]:
    """Get discovery status for status bar.

    Returns:
        Tuple of (last_discovery_relative, next_run_relative).
    """
    try:
        from walltrack.data.supabase.client import get_supabase_client
        from walltrack.scheduler.jobs import get_next_run_time
        from datetime import datetime, UTC

        async def _get_last_checked():
            client = await get_supabase_client()
            # Get most recent last_checked from tokens
            result = await client.table("tokens").select("last_checked").order("last_checked", desc=True).limit(1).execute()
            if result.data and result.data[0].get("last_checked"):
                return result.data[0]["last_checked"]
            return None

        last_checked = asyncio.run(_get_last_checked())

        # Format last discovery time
        if last_checked:
            dt = datetime.fromisoformat(last_checked.replace("Z", "+00:00"))
            last_str = get_relative_time(dt)
        else:
            last_str = "never"

        # Format next run time
        next_run = get_next_run_time()
        if next_run:
            dt = datetime.fromisoformat(next_run.replace("Z", "+00:00"))
            now = datetime.now(UTC)
            diff = dt - now
            if diff.total_seconds() > 0:
                hours = int(diff.total_seconds() / 3600)
                if hours > 0:
                    next_str = f"{hours}h"
                else:
                    minutes = int(diff.total_seconds() / 60)
                    next_str = f"{minutes}m"
            else:
                next_str = "soon"
        else:
            next_str = "--"

        return (last_str, next_str)

    except Exception as e:
        log.debug("discovery_status_failed", error=str(e))
        return ("--", "--")


# Update render_status_html() to include:
def render_status_html() -> str:
    # ... existing code ...

    last_discovery, next_run = get_discovery_status()

    # Replace the hardcoded discovery line with:
    # <span>🟢 Discovery: {last_discovery} (next: {next_run})</span>
```

### ConfigRepository Methods

**NOTE:** `ConfigRepository` already has `get_value()` and `set_value()` methods (from Story 1.5).
No extension needed - use existing methods directly.

```python
# Usage pattern (methods already exist in config_repo.py):
from walltrack.data.supabase.repositories.config_repo import ConfigRepository

async def example():
    client = await get_supabase_client()
    repo = ConfigRepository(client)

    # Get value
    value = await repo.get_value("surveillance_interval_hours")

    # Set value
    await repo.set_value("surveillance_interval_hours", "4")
```

**Client Pattern Note:** ConfigRepository uses `self._client.client.table()` internally (double `.client`).
You don't need to worry about this - just use the repository methods.

---

## Project Structure Notes

### Files to Create

```
src/walltrack/
├── scheduler/
│   ├── __init__.py        # EXISTS (empty)
│   ├── scheduler.py       # NEW - scheduler singleton
│   └── jobs.py            # NEW - job definitions
```

### Files to Modify

- `src/walltrack/main.py` - Add lifespan for scheduler
- `src/walltrack/ui/pages/config.py` - Add surveillance settings
- `src/walltrack/ui/components/status_bar.py` - Add discovery status
- `src/walltrack/data/supabase/repositories/config_repo.py` - Add get/set methods if missing

---

## Legacy Reference

### APScheduler Pattern (V1)
**Source:** `legacy/src/walltrack/scheduler/` (if exists)

**Key patterns to reproduce:**
- AsyncIOScheduler for async job execution
- Singleton pattern for scheduler instance
- Job IDs for management (reschedule, remove)
- Graceful shutdown on app termination

### V1 Anti-patterns to Avoid
- V1 may have had blocking jobs - V2 uses async throughout
- V1 may have had hardcoded intervals - V2 stores in config

---

## Previous Story Intelligence

### From Story 2.1 (Token Discovery Trigger)
- `TokenDiscoveryService` exists in `core/discovery/token_discovery.py`
- `TokenRepository` has `upsert_tokens()` method
- `DexScreenerClient` fetches from DexScreener API
- Discovery updates `tokens` table including `last_checked`
- Gradio sync wrapper pattern established

### From Story 1.5 (Trading Wallet Connection)
- `ConfigRepository` pattern for storing settings
- Gradio async wrapper pattern (`asyncio.run()`)

### From Story 1.4 (Status Bar)
- Status bar has 30s auto-refresh
- `get_relative_time()` utility function exists
- HTML rendering pattern established

---

## Testing Strategy

### Unit Tests

```python
# tests/unit/scheduler/test_scheduler.py

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from walltrack.scheduler.scheduler import get_scheduler, start_scheduler, shutdown_scheduler


@pytest.mark.asyncio
async def test_scheduler_singleton():
    """Scheduler should be singleton."""
    s1 = get_scheduler()
    s2 = get_scheduler()
    assert s1 is s2


@pytest.mark.asyncio
async def test_scheduler_starts():
    """Scheduler should start successfully."""
    with patch("walltrack.scheduler.scheduler._scheduler", None):
        await start_scheduler()
        scheduler = get_scheduler()
        assert scheduler.running


@pytest.mark.asyncio
async def test_scheduler_shutdown():
    """Scheduler should shutdown gracefully."""
    await start_scheduler()
    await shutdown_scheduler()
    # Scheduler singleton should be cleared
```

```python
# tests/unit/scheduler/test_jobs.py

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from walltrack.scheduler.jobs import (
    refresh_tokens_job,
    schedule_surveillance_job,
    get_next_run_time,
    JOB_ID_SURVEILLANCE,
)


@pytest.mark.asyncio
async def test_refresh_tokens_job_calls_discovery(mocker):
    """Job should call TokenDiscoveryService."""
    mock_service = MagicMock()
    mock_service.run_discovery = AsyncMock(return_value=MagicMock(
        tokens_found=5,
        new_tokens=2,
        updated_tokens=3,
    ))

    mock_client = AsyncMock()
    mock_dex = MagicMock()
    mock_dex.close = AsyncMock()

    mocker.patch(
        "walltrack.scheduler.jobs.get_supabase_client",
        return_value=mock_client
    )
    mocker.patch(
        "walltrack.scheduler.jobs.DexScreenerClient",
        return_value=mock_dex
    )
    mocker.patch(
        "walltrack.scheduler.jobs.TokenDiscoveryService",
        return_value=mock_service
    )

    await refresh_tokens_job()

    mock_service.run_discovery.assert_called_once()
    mock_dex.close.assert_called_once()


def test_schedule_surveillance_job(mocker):
    """Should schedule job with correct interval."""
    mock_scheduler = MagicMock()
    mock_scheduler.get_job.return_value = None

    mocker.patch(
        "walltrack.scheduler.jobs.get_scheduler",
        return_value=mock_scheduler
    )

    schedule_surveillance_job(interval_hours=2)

    mock_scheduler.add_job.assert_called_once()
    call_kwargs = mock_scheduler.add_job.call_args.kwargs
    assert call_kwargs["id"] == JOB_ID_SURVEILLANCE
```

### Integration Tests

```python
# tests/integration/test_scheduler_integration.py

@pytest.mark.asyncio
async def test_scheduler_lifecycle():
    """Test scheduler start, job execution, and shutdown."""
    # Start scheduler
    # Schedule job with short interval
    # Verify job runs
    # Shutdown scheduler
```

---

## Success Criteria

**Story DONE when:**
1. APScheduler configured and starts with app
2. Surveillance job calls `TokenDiscoveryService.run_discovery()`
3. Job runs at configurable interval (1h, 2h, 4h, 8h)
4. Interval stored in Supabase `config` table
5. Config page shows interval dropdown and next run time
6. Changing interval reschedules job immediately
7. Status bar shows "Discovery: Xh ago (next: Yh)"
8. Scheduler shuts down gracefully on app termination
9. All unit tests passing
10. Integration test validates job execution

---

## Dependencies

### Story Dependencies
- Story 2.1: Token Discovery Trigger (TokenDiscoveryService) - **REQUIRED**
- Story 1.2: Database Connections (SupabaseClient) - **DONE**
- Story 1.4: Gradio Base App (Status Bar) - **DONE**
- Story 1.5: Trading Wallet Connection (ConfigRepository) - **DONE**

### External Dependencies
- APScheduler library (`uv add apscheduler`)
- DexScreener API (via Story 2.1)

---

## Dev Agent Record

### Context Reference

<!-- Path(s) to story context XML will be added here by context workflow -->

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

None

### Completion Notes List

- APScheduler configured with AsyncIOScheduler for non-blocking async job execution
- Scheduler singleton pattern with graceful shutdown on app termination
- Surveillance job calls TokenDiscoveryService.run_discovery() and updates tokens
- Config page has interval dropdown (1h, 2h, 4h, 8h) and enable/disable toggle
- Status bar shows "Discovery: Xh ago (next: Yh)" with 30s refresh
- All unit tests passing (15 scheduler tests)
- All integration tests passing (10 scheduler tests)
- Total test suite: 253 tests passing

**Code Review Fixes Applied:**
- Added surveillance job restoration on app startup (`main.py:_restore_surveillance_job()`)
- Refactored status_bar.py to use TokenRepository instead of direct table access
- Added `get_latest_checked_time()` method to TokenRepository
- Added interval validation in `schedule_surveillance_job()` (ValueError for invalid intervals)
- Added test cleanup in unit tests (scheduler.shutdown() after start tests)
- Added unit test for interval validation

### File List

**New Files:**
- `src/walltrack/scheduler/scheduler.py` - Scheduler singleton with start/shutdown lifecycle
- `src/walltrack/scheduler/jobs.py` - Surveillance job and scheduling functions
- `tests/unit/scheduler/test_scheduler.py` - Unit tests for scheduler singleton (6 tests)
- `tests/unit/scheduler/test_jobs.py` - Unit tests for jobs module (8 tests)
- `tests/integration/test_scheduler.py` - Integration tests for scheduler (10 tests)

**Modified Files:**
- `src/walltrack/main.py` - Added scheduler lifecycle to FastAPI lifespan
- `src/walltrack/ui/pages/config.py` - Added surveillance schedule UI controls
- `src/walltrack/ui/components/status_bar.py` - Added get_discovery_status() and discovery status display

### Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-12-29 | Story implemented - all 5 tasks completed | Claude Opus 4.5 |

---

_Story generated by SM Agent (Bob) - 2025-12-29_
_Mode: YOLO - Ultimate context engine analysis completed_
