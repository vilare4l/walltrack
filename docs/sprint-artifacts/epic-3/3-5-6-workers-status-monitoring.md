# Story 3.5.6: Workers Status Monitoring in Status Bar

**Epic:** 3 - Smart Money Wallet Analysis
**Story Points:** 2
**Priority:** Medium
**Status:** ready-for-dev
**Created:** 2026-01-01

---

## Context & Problem

With Story 3.5.5 implementing autonomous workers (Discovery, Profiling, Decay), the system now runs multiple background processes continuously. Currently, there is **no visibility** into whether these workers are running, when they last processed data, or if they encountered errors.

**Current situation:**
- ❌ No way to know if workers are running or crashed
- ❌ No visibility into last processing time
- ❌ No indication of worker errors or backlogs
- ❌ User must check logs to troubleshoot worker issues

**User pain points:**
1. "Are wallets being discovered automatically?" → Unknown
2. "Is profiling worker stuck?" → No visual feedback
3. "When did decay check last run?" → Must check logs
4. "Why are wallets not appearing?" → No error indicators

**Existing Status Bar** (Story 1.4) shows:
- ✅ Token Discovery status (last run, next run, count)
- ✅ Wallet count
- ✅ System health (DB connections)
- ❌ **Missing:** Workers status (Discovery, Profiling, Decay)

---

## Solution

Extend the Status Bar to display **autonomous workers status** with compact, real-time information.

**Design principles:**
- **Compact:** Use icons + condensed text to avoid Status Bar overflow
- **Real-time:** 30-second auto-refresh (existing pattern)
- **Actionable:** Show errors/warnings prominently
- **Consistent:** Follow existing Status Bar style (icons + text)

**Status Bar additions:**
```
[Current Status Bar items...]
🔄 Discovery Worker: 5m ago (12 wallets)
🔄 Profiling Worker: 2m ago (8 wallets)
🔄 Decay Check: Next 3h
```

**Worker states:**
- 🟢 Running normally (green circle)
- 🟡 Idle / No work (yellow circle)
- 🔴 Stopped / Errored (red circle)

---

## Acceptance Criteria

### AC1: Workers Expose Status Interface

- [x] `WalletDiscoveryWorker` exposes `.get_status()` method
- [x] `WalletProfilingWorker` exposes `.get_status()` method
- [x] `DecayCheckScheduler` exposes status via APScheduler job info
- [x] Status includes: `running`, `last_run`, `processed_count`, `error_count`, `current_state`

**Status structure:**
```python
{
    'running': bool,           # Is worker currently running?
    'last_run': datetime,      # Last successful run (or None)
    'processed_count': int,    # Items processed in last run
    'error_count': int,        # Errors in last run
    'current_state': str,      # 'idle' | 'processing' | 'stopped' | 'error'
}
```

### AC2: Status Bar Displays Workers Status

- [x] Status Bar shows 3 new items: Discovery Worker, Profiling Worker, Decay Check
- [x] Each item shows: Icon (state), Last run time (relative), Count (processed items)
- [x] Auto-refreshes every 30 seconds (existing pattern)
- [x] Compact format fits on single line (< 50 chars per worker)

**Display format:**
```
🟢 Discovery: 5m ago (12 new)    ← Running normally, processed 12 wallets
🟡 Profiling: idle               ← Idle (no wallets to profile)
🔴 Decay: error (see logs)       ← Error occurred
```

### AC3: Icon Color Reflects Worker Health

- [x] 🟢 Green: Worker running, last run < poll_interval × 2
- [x] 🟡 Yellow: Worker idle (no work) OR last run > poll_interval × 2 but < poll_interval × 5
- [x] 🔴 Red: Worker stopped OR last run > poll_interval × 5 OR error_count > 0

**Health logic:**
```python
# Discovery Worker (poll_interval = 120s)
last_run = 3 minutes ago  → 🟢 Green (< 240s)
last_run = 6 minutes ago  → 🟡 Yellow (< 600s)
last_run = 12 minutes ago → 🔴 Red (> 600s - likely crashed)
error_count > 0           → 🔴 Red
```

### AC4: Graceful Handling of Worker Not Started

- [x] If worker not started yet (app startup), show: `🟡 Starting...`
- [x] If worker task cancelled/crashed, show: `🔴 Stopped`
- [x] No exceptions thrown if workers not accessible

### AC5: Decay Scheduler Shows Next Run

- [x] Decay Check displays "Next: Xh" instead of "Last: X ago"
- [x] Pulls next run time from APScheduler job info
- [x] Shows 🟢 if next run scheduled, 🔴 if not scheduled

### AC6: Status Helper Functions Reusable

- [x] Create `get_workers_status()` helper in `status_bar.py`
- [x] Returns dict with all 3 workers' status
- [x] Can be reused for future monitoring UI (Config page, API endpoint)

---

## Tasks

### Task 1: Add Status Interface to Workers

**1.1** Add status tracking to `WalletDiscoveryWorker`
- File: `src/walltrack/workers/wallet_discovery_worker.py` (to be created in Story 3.5.5)
- Add instance variables:
  ```python
  self._last_run: datetime | None = None
  self._processed_last_run: int = 0
  self._errors_last_run: int = 0
  self._current_state: str = "idle"  # idle | processing | stopped | error
  ```
- Add method:
  ```python
  def get_status(self) -> dict:
      """Get worker status for monitoring."""
      return {
          'running': self.running,
          'last_run': self._last_run,
          'processed_count': self._processed_last_run,
          'error_count': self._errors_last_run,
          'current_state': self._current_state,
      }
  ```
- Update `run()` loop to track metrics:
  ```python
  async def run(self):
      while self.running:
          self._current_state = "processing"
          try:
              wallets = await self._discover_wallets()
              self._processed_last_run = len(wallets)
              self._errors_last_run = 0
              self._last_run = datetime.now(UTC)
              self._current_state = "idle"
          except Exception as e:
              self._errors_last_run += 1
              self._current_state = "error"
              # ... existing error handling ...
  ```

**1.2** Add status tracking to `WalletProfilingWorker`
- File: `src/walltrack/workers/wallet_profiling_worker.py`
- Same structure as 1.1 (already partially exists - update to match interface)

**1.3** Create helper to get DecayCheckScheduler status
- File: `src/walltrack/scheduler/jobs.py`
- Add function:
  ```python
  def get_decay_scheduler_status() -> dict:
      """Get decay scheduler status from APScheduler.

      Returns:
          Status dict with next_run, running state.
      """
      from walltrack.scheduler.scheduler import scheduler

      job = scheduler.get_job('decay_check')
      if not job:
          return {
              'running': False,
              'next_run': None,
              'current_state': 'stopped'
          }

      return {
          'running': True,
          'next_run': job.next_run_time,
          'current_state': 'scheduled'
      }
  ```

### Task 2: Extend Status Bar Component

**2.1** Add `get_workers_status()` helper function
- File: `src/walltrack/ui/components/status_bar.py`
- Function:
  ```python
  def get_workers_status() -> dict:
      """Get autonomous workers status for monitoring.

      Returns:
          Dict with 'discovery', 'profiling', 'decay' keys.
          Each contains: running, last_run, processed_count, error_count, current_state.
      """
      try:
          # Import main module to access worker instances
          from walltrack.main import wallet_discovery_worker, wallet_profiling_worker
          from walltrack.scheduler.jobs import get_decay_scheduler_status

          discovery_status = (
              wallet_discovery_worker.get_status()
              if wallet_discovery_worker else None
          )
          profiling_status = (
              wallet_profiling_worker.get_status()
              if wallet_profiling_worker else None
          )
          decay_status = get_decay_scheduler_status()

          return {
              'discovery': discovery_status or {'current_state': 'stopped'},
              'profiling': profiling_status or {'current_state': 'stopped'},
              'decay': decay_status or {'current_state': 'stopped'},
          }
      except Exception as e:
          log.debug("workers_status_fetch_failed", error=str(e))
          return {
              'discovery': {'current_state': 'unknown'},
              'profiling': {'current_state': 'unknown'},
              'decay': {'current_state': 'unknown'},
          }
  ```

**2.2** Add helper to determine worker health icon
- File: `src/walltrack/ui/components/status_bar.py`
- Function:
  ```python
  def get_worker_health_icon(status: dict, poll_interval_seconds: int) -> str:
      """Determine health icon for worker based on status.

      Args:
          status: Worker status dict from get_status()
          poll_interval_seconds: Expected poll interval (e.g., 120 for discovery)

      Returns:
          Icon string: "🟢" (healthy) | "🟡" (warning) | "🔴" (error)
      """
      state = status.get('current_state', 'unknown')

      # Red: Stopped, error, or unknown
      if state in ('stopped', 'error', 'unknown'):
          return "🔴"

      # Red: Has errors in last run
      if status.get('error_count', 0) > 0:
          return "🔴"

      # Check last run time
      last_run = status.get('last_run')
      if last_run:
          now = datetime.now(UTC)
          seconds_since = (now - last_run).total_seconds()

          # Green: Last run within 2× poll interval
          if seconds_since < poll_interval_seconds * 2:
              return "🟢"

          # Yellow: Last run within 5× poll interval
          if seconds_since < poll_interval_seconds * 5:
              return "🟡"

          # Red: Last run > 5× poll interval (likely crashed)
          return "🔴"

      # Yellow: No last run yet (starting or idle)
      return "🟡"
  ```

**2.3** Add helper to format worker status text
- File: `src/walltrack/ui/components/status_bar.py`
- Function:
  ```python
  def format_worker_status(status: dict, worker_name: str) -> str:
      """Format worker status for display in Status Bar.

      Args:
          status: Worker status dict
          worker_name: "Discovery" | "Profiling" | "Decay"

      Returns:
          Compact status string (e.g., "5m ago (12 wallets)")
      """
      state = status.get('current_state', 'unknown')

      # Handle special states
      if state == 'stopped':
          return "stopped"
      if state == 'error':
          error_count = status.get('error_count', 0)
          return f"error ({error_count} failures)"
      if state == 'unknown':
          return "unavailable"
      if state == 'processing':
          return "running..."

      # For decay scheduler, show next run instead of last run
      if worker_name == "Decay":
          next_run = status.get('next_run')
          if next_run:
              now = datetime.now(UTC)
              diff = next_run - now
              hours = int(diff.total_seconds() / 3600)
              if hours > 0:
                  return f"next {hours}h"
              minutes = int(diff.total_seconds() / 60)
              return f"next {minutes}m"
          return "not scheduled"

      # For discovery/profiling workers, show last run + processed count
      last_run = status.get('last_run')
      if last_run:
          relative = get_relative_time(last_run)
          processed = status.get('processed_count', 0)
          if processed > 0:
              return f"{relative} ({processed} items)"
          return f"{relative} (idle)"

      return "idle"
  ```

**2.4** Update `render_status_html()` to include workers
- File: `src/walltrack/ui/components/status_bar.py`
- Add after existing wallet count section (line ~228):
  ```python
  # Workers status (Story 3.5.6)
  workers = get_workers_status()

  discovery_icon = get_worker_health_icon(workers['discovery'], poll_interval_seconds=120)
  discovery_text = format_worker_status(workers['discovery'], "Discovery")

  profiling_icon = get_worker_health_icon(workers['profiling'], poll_interval_seconds=60)
  profiling_text = format_worker_status(workers['profiling'], "Profiling")

  decay_icon = get_worker_health_icon(workers['decay'], poll_interval_seconds=14400)
  decay_text = format_worker_status(workers['decay'], "Decay")
  ```
- Add to HTML return (after wallets line):
  ```python
  <span>{discovery_icon} Discovery: {discovery_text}</span>
  <span>{profiling_icon} Profiling: {profiling_text}</span>
  <span>{decay_icon} Decay: {decay_text}</span>
  ```

### Task 3: Expose Worker Instances in main.py

**3.1** Store worker instances as module-level variables
- File: `src/walltrack/main.py`
- After line 18, add:
  ```python
  # Global worker instances for status monitoring (Story 3.5.6)
  wallet_discovery_worker: WalletDiscoveryWorker | None = None
  wallet_profiling_worker: WalletProfilingWorker | None = None
  ```
- In `lifespan()` function, assign to global:
  ```python
  global wallet_discovery_worker, wallet_profiling_worker

  wallet_discovery_worker = WalletDiscoveryWorker(poll_interval=120)
  wallet_profiling_worker = WalletProfilingWorker(poll_interval=60)
  ```

### Task 4: Testing

**4.1** Unit tests for status helpers
- File: `tests/unit/ui/components/test_status_bar.py`
- Tests:
  ```python
  def test_get_worker_health_icon_green():
      """Test green icon for healthy worker."""
      status = {
          'current_state': 'idle',
          'last_run': datetime.now(UTC) - timedelta(seconds=60),
          'error_count': 0,
      }
      icon = get_worker_health_icon(status, poll_interval_seconds=120)
      assert icon == "🟢"

  def test_get_worker_health_icon_yellow_old_run():
      """Test yellow icon for stale but not crashed worker."""
      status = {
          'current_state': 'idle',
          'last_run': datetime.now(UTC) - timedelta(seconds=300),
          'error_count': 0,
      }
      icon = get_worker_health_icon(status, poll_interval_seconds=120)
      assert icon == "🟡"

  def test_get_worker_health_icon_red_crashed():
      """Test red icon for crashed worker."""
      status = {
          'current_state': 'idle',
          'last_run': datetime.now(UTC) - timedelta(seconds=700),
          'error_count': 0,
      }
      icon = get_worker_health_icon(status, poll_interval_seconds=120)
      assert icon == "🔴"

  def test_format_worker_status_discovery():
      """Test discovery worker status formatting."""
      status = {
          'current_state': 'idle',
          'last_run': datetime.now(UTC) - timedelta(minutes=5),
          'processed_count': 12,
      }
      text = format_worker_status(status, "Discovery")
      assert "5m ago" in text
      assert "12 items" in text

  def test_format_worker_status_decay():
      """Test decay scheduler status formatting."""
      status = {
          'current_state': 'scheduled',
          'next_run': datetime.now(UTC) + timedelta(hours=3),
      }
      text = format_worker_status(status, "Decay")
      assert "next 3h" in text
  ```

**4.2** Integration test - Workers visible in Status Bar
- File: `tests/integration/test_workers_status_bar.py`
- Test:
  ```python
  async def test_workers_status_in_status_bar():
      """Test that workers status appears in Status Bar."""
      from walltrack.ui.components.status_bar import render_status_html

      html = render_status_html()

      # Should contain worker status items
      assert "Discovery:" in html
      assert "Profiling:" in html
      assert "Decay:" in html

      # Should contain health icons
      assert "🟢" in html or "🟡" in html or "🔴" in html
  ```

**4.3** Manual E2E verification
- Start app: `uv run walltrack`
- Navigate to dashboard
- Verify Status Bar shows 3 worker items
- Wait 30 seconds, verify auto-refresh updates times
- Stop app, restart, verify workers show "Starting..." then transition to normal state

---

## Dev Notes

### Worker Status Access Pattern

**Problem:** Workers run in asyncio tasks, Status Bar runs in Gradio sync context.

**Solution:** Store worker instances as module-level variables in `main.py`:
```python
# main.py
wallet_discovery_worker: WalletDiscoveryWorker | None = None
wallet_profiling_worker: WalletProfilingWorker | None = None

@asynccontextmanager
async def lifespan(_app: FastAPI):
    global wallet_discovery_worker, wallet_profiling_worker

    wallet_discovery_worker = WalletDiscoveryWorker(poll_interval=120)
    wallet_profiling_worker = WalletProfilingWorker(poll_interval=60)

    # ... start workers ...
```

Status Bar can import and access:
```python
from walltrack.main import wallet_discovery_worker
status = wallet_discovery_worker.get_status() if wallet_discovery_worker else None
```

### Poll Interval Constants

Workers have different poll intervals:
- **Discovery Worker:** 120s (2 minutes) - Story 3.5.5
- **Profiling Worker:** 60s (1 minute) - Story 3.5.5
- **Decay Scheduler:** 14,400s (4 hours) - Story 3.4

Health thresholds scale based on poll interval:
- Green: `last_run < poll_interval × 2`
- Yellow: `last_run < poll_interval × 5`
- Red: `last_run >= poll_interval × 5`

### Status Bar Length Consideration

Current Status Bar has ~7 items. Adding 3 workers = 10 items total.

**Mitigation:**
- Use compact format: "5m ago (12)" instead of "5 minutes ago (12 wallets processed)"
- Icons provide color-coded health at a glance
- If too long, consider collapsing to: `🔄 Workers: 🟢 3/3 running` (expandable on click in future story)

### Future Enhancement Ideas

**Not in this story, but possible later:**
- Click worker item → Modal with detailed logs/metrics
- Worker error alerts (toast notifications)
- Historical metrics (uptime %, avg processing time)
- Config page accordion with full worker dashboard

---

## Acceptance Testing

### Scenario 1: Healthy Workers

**Given:** All 3 workers running normally
**When:** User opens dashboard
**Then:**
- Status Bar shows 3 worker items
- All have 🟢 green icons
- Discovery shows "Xm ago (Y wallets)"
- Profiling shows "Xm ago (Y wallets)"
- Decay shows "next Xh"

### Scenario 2: Worker Error

**Given:** Profiling worker encounters RPC timeout error
**When:** User views Status Bar after error
**Then:**
- Profiling item shows 🔴 red icon
- Text shows "error (1 failures)"
- Other workers remain green (isolated failure)

### Scenario 3: App Startup

**Given:** App just started, workers initializing
**When:** User opens dashboard within first 30s
**Then:**
- Workers show 🟡 yellow icons
- Text shows "idle" or "starting..."
- After first successful run, transitions to 🟢 green

### Scenario 4: Worker Crash (Simulated)

**Given:** Discovery worker task cancelled (simulated crash)
**When:** User views Status Bar after 10 minutes
**Then:**
- Discovery item shows 🔴 red icon
- Text shows "stopped" or "last run 10m ago" (red due to > 5× poll interval)
- User knows to check logs or restart app

---

## Dependencies

- **Requires:** Story 3.5.5 (WalletDiscoveryWorker, WalletProfilingWorker)
- **Requires:** Story 3.4 (DecayCheckScheduler via APScheduler)
- **Requires:** Story 1.4 (Status Bar component exists)

---

## Estimated Effort

**Development:** 3-4 hours
- Task 1: 1.5h (add status tracking to workers)
- Task 2: 1.5h (extend Status Bar component)
- Task 3: 0.5h (expose worker instances)
- Task 4: 0.5h (testing)

**Testing:** 1 hour
- Unit tests for helpers
- Integration test
- Manual E2E verification

**Total:** ~4-5 hours

---

## Success Metrics

- ✅ Status Bar displays 3 worker items with correct health icons
- ✅ Auto-refresh every 30s updates worker status
- ✅ User can visually identify worker issues (red icons)
- ✅ No exceptions thrown if workers not started
- ✅ Compact format fits on single Status Bar line
