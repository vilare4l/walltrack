# Story 3.4: Wallet Decay Detection

**Status:** ready-for-dev
**Epic:** 3 - Wallet Discovery & Profiling
**Created:** 2025-12-30
**Sprint Artifacts:** docs/sprint-artifacts/epic-3/

---

## Story

**As an** operator,
**I want** to detect when wallets lose their edge,
**So that** I don't follow degraded wallets.

**FRs Covered:** FR7, FR8

**From Epic:** Epic 3 - Wallet Discovery & Profiling

---

## Acceptance Criteria

### AC1: Rolling Window Decay Detection

**Given** a wallet with 20+ completed trades
**When** decay check runs
**Then** system calculates win_rate over most recent 20 trades (rolling window)
**And** if win_rate < 40%, decay_status changes to "flagged" 🟡
**And** if win_rate >= 50% and currently flagged, decay_status changes to "ok" 🟢

**Note:** A "completed trade" = matched BUY+SELL pair via FIFO matching (reuse `match_trades()` from Story 3.2). Unpaired transactions (BUY without SELL or vice versa) are NOT counted.

### AC2: Consecutive Loss Detection

**Given** a wallet with recent trades
**When** 3 consecutive losses occur
**Then** decay_status changes to "downgraded" 🔴
**And** wallet score is reduced by 5% per additional loss
**And** downgrade persists until wallet has a winning trade

### AC3: Dormancy Detection

**Given** a wallet with no trading activity
**When** last_activity_date is 30+ days ago
**Then** decay_status changes to "dormant" ⚪
**And** dormancy persists until wallet makes a new trade

### AC4: Decay Events Logged

**Given** any decay status change
**When** status transitions (ok → flagged, flagged → ok, etc.)
**Then** event is logged to `decay_events` table
**And** event includes: wallet_address, event_type, rolling_win_rate, timestamp, score_before, score_after

### AC5: UI Badge Display

**Given** wallets with decay status
**When** I view Explorer → Wallets tab
**Then** Decay Status column shows correct badge:
  - 🟢 "OK" (green) - performing well
  - 🟡 "Flagged" (yellow) - win rate below threshold
  - 🔴 "Downgraded" (red) - consecutive losses
  - ⚪ "Dormant" (white) - no activity 30+ days

---

## Tasks / Subtasks

### Task 1: Database Schema for Decay Events (AC: 4)

- [ ] **1.1** Create Supabase migration for decay_events table
  - Migration file: `src/walltrack/data/supabase/migrations/009_decay_events_table.sql`
  - Table: `walltrack.decay_events`
  - Columns:
    - `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`
    - `wallet_address TEXT NOT NULL REFERENCES walltrack.wallets(wallet_address) ON DELETE CASCADE`
    - `event_type TEXT NOT NULL CHECK (event_type IN ('decay_detected', 'recovery', 'consecutive_losses', 'dormancy'))`
    - `rolling_win_rate DECIMAL(5,2)` - Win rate at time of event (0.00 to 1.00)
    - `lifetime_win_rate DECIMAL(5,2)` - Overall win rate
    - `consecutive_losses INTEGER DEFAULT 0`
    - `score_before DECIMAL(5,4)` - Score before event
    - `score_after DECIMAL(5,4)` - Score after event
    - `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
  - Index: `CREATE INDEX idx_decay_events_wallet ON walltrack.decay_events(wallet_address, created_at DESC);`
  - Index: `CREATE INDEX idx_decay_events_type ON walltrack.decay_events(event_type, created_at DESC);`
  - Row Level Security enabled
- [ ] **1.2** Execute migration on Supabase
  - Connect to Supabase database
  - Run migration SQL
  - Verify table creation with `\d walltrack.decay_events`
- [ ] **1.3** Create `src/walltrack/data/models/decay_event.py` with Pydantic models
  - `DecayEvent` model matching database schema
  - `DecayEventCreate` model for insertion
  - Enum for event types: `DecayEventType` (DECAY_DETECTED, RECOVERY, CONSECUTIVE_LOSSES, DORMANCY)
- [ ] **1.4** Verify wallets table schema and add missing columns
  - Read migration `003_wallets_table.sql` to confirm existing columns
  - Required columns:
    - `decay_status TEXT DEFAULT 'ok'` - May exist from Story 3.1
    - `consecutive_losses INTEGER DEFAULT 0` - May exist from Story 3.1
    - `last_activity_date TIMESTAMPTZ` - **NOT in Story 3.1** (confirmed)
    - `rolling_win_rate DECIMAL(5,2)` - **NOT in Story 3.2** (confirmed)
    - `score DECIMAL(5,4) DEFAULT 0.5` - **NOT in any previous story** (required for decay adjustment)
  - If missing, add to migration `008_wallets_decay_columns.sql`
  - **IMPORTANT:** Do NOT assume columns exist - verify first

### Task 2: Decay Detector Service (AC: 1, 2, 3)

- [ ] **2.1** Create `src/walltrack/core/wallets/decay_detector.py`
  - Class: `DecayDetector`
  - **IMPORTANT:** Configuration is loaded from database (config table), NOT hardcoded
  - Create `DecayConfig` dataclass:
    ```python
    @dataclass
    class DecayConfig:
        rolling_window_size: int
        min_trades: int
        decay_threshold: float
        recovery_threshold: float
        consecutive_loss_threshold: int
        dormancy_days: int
        score_downgrade_decay: float
        score_downgrade_loss: float

        @classmethod
        async def from_db(cls, config_repo: ConfigRepository) -> "DecayConfig":
            """Load decay configuration from database."""
            config = await config_repo.get_config()
            return cls(
                rolling_window_size=config.decay_rolling_window_size,
                min_trades=config.decay_min_trades,
                decay_threshold=config.decay_threshold,
                recovery_threshold=config.decay_recovery_threshold,
                consecutive_loss_threshold=config.decay_consecutive_loss_threshold,
                dormancy_days=config.decay_dormancy_days,
                score_downgrade_decay=config.decay_score_downgrade_decay,
                score_downgrade_loss=config.decay_score_downgrade_loss,
            )
    ```
  - Constructor: `__init__(self, config: DecayConfig, wallet_repo: WalletRepository, helius_client: HeliusClient)`
  - Method: `check_wallet_decay(wallet_address: str) -> DecayEvent | None`
    - Fetch wallet from WalletRepository
    - Fetch last 20 completed trades from Helius transaction history (reuse logic from Story 3.2)
    - Calculate rolling win_rate
    - Check decay conditions (AC1, AC2, AC3)
    - Update wallet decay_status if changed
    - Return DecayEvent if status changed, None otherwise
- [ ] **2.2** Implement rolling window win rate calculation
  - **IMPORTANT:** "Completed trade" = matched BUY+SELL transaction pair (FIFO)
  - Fetch last 100 transactions via HeliusClient (to get ~20+ completed trades)
  - Reuse `match_trades()` function from Story 3.2 (FIFO pairing BUY→SELL)
  - Take most recent `config.rolling_window_size` completed trades (default 20, NOT 20 transactions)
  - Calculate PnL for each completed trade
  - Win rate = (profitable_trades / rolling_window_size)
  - Store in wallet.rolling_win_rate field (added in migration 008)
- [ ] **2.3** Implement consecutive loss counter
  - Iterate through trades from most recent to oldest
  - Count consecutive losing trades until first win
  - Update wallet.consecutive_losses field
  - Reset to 0 if latest trade is a win
- [ ] **2.4** Implement dormancy detection
  - Calculate days since last_activity_date
  - If >= 30 days, mark as dormant
  - Update wallet.last_activity_date after each trade
- [ ] **2.5** Implement status transition logic with explicit priority order
  - **CRITICAL:** When multiple conditions are true, apply in this priority order (highest to lowest):
    1. **DORMANT** (days_inactive >= config.dormancy_days) - Overrides all other conditions
    2. **DOWNGRADED** (consecutive_losses >= config.consecutive_loss_threshold) - Most severe
    3. **FLAGGED** (rolling_win_rate < config.decay_threshold) - Moderate warning
    4. **OK** (recovery: rolling_win_rate >= config.recovery_threshold AND currently flagged) - Only from flagged state
    5. **OK** (default) - No change or already ok
  - Implementation example:
    ```python
    def determine_decay_status(
        wallet: Wallet,
        rolling_win_rate: float,
        consecutive_losses: int,
        days_since_activity: int,
        config: DecayConfig
    ) -> str:
        """Determine decay status with explicit priority order."""
        # Priority 1: Dormancy (highest)
        if days_since_activity >= config.dormancy_days:
            return "dormant"

        # Priority 2: Consecutive losses (severe)
        if consecutive_losses >= config.consecutive_loss_threshold:
            return "downgraded"

        # Priority 3: Rolling window decay (moderate)
        if rolling_win_rate < config.decay_threshold:
            return "flagged"

        # Priority 4: Recovery (only if currently flagged)
        if wallet.decay_status == "flagged" and rolling_win_rate >= config.recovery_threshold:
            return "ok"

        # Priority 5: Default
        return wallet.decay_status or "ok"
    ```
- [ ] **2.6** Implement score adjustment on decay with bounds enforcement
  - Decay detected: `score *= config.score_downgrade_decay` (default 0.80 = 20% reduction)
  - Consecutive losses: `score *= config.score_downgrade_loss` per loss beyond threshold (default 0.95 = 5% per loss)
  - Recovery: `score *= 1.10` (10% increase - simple and predictable)
  - **Score bounds enforcement:**
    ```python
    MIN_SCORE = 0.1  # Never reduce below (wallet still viable)
    MAX_SCORE = 1.0  # Perfect score ceiling

    # Apply adjustment
    new_score = wallet.score * adjustment_factor

    # Enforce bounds
    new_score = max(MIN_SCORE, min(MAX_SCORE, new_score))

    # Special case: if current score is 0 or negative, reset to minimum
    if wallet.score <= 0:
        new_score = MIN_SCORE
    ```
- [ ] **2.7** Add unit tests for decay detector
  - Test: `test_decay_detected_below_threshold()` - win rate < 40%
  - Test: `test_recovery_above_threshold()` - win rate >= 50%
  - Test: `test_consecutive_losses()` - 3+ losses
  - Test: `test_dormancy_detection()` - 30+ days
  - Test: `test_score_downgrade_decay()` - score reduced correctly
  - Test: `test_score_downgrade_losses()` - 5% per loss
  - Test: `test_insufficient_trades()` - skip if < 20 trades
  - Mock WalletRepository, HeliusClient responses

### Task 3: Decay Event Repository (AC: 4)

- [ ] **3.1** Create `src/walltrack/data/supabase/repositories/decay_event_repo.py`
  - Class: `DecayEventRepository`
  - Method: `create(event: DecayEventCreate) -> DecayEvent`
    - Insert decay event to database
    - Return created event with ID
  - Method: `get_wallet_events(wallet_address: str, limit: int = 50) -> list[DecayEvent]`
    - Fetch decay events for a specific wallet
    - Order by created_at DESC
  - Method: `get_recent_events(event_type: str | None = None, limit: int = 100) -> list[DecayEvent]`
    - Fetch recent decay events across all wallets
    - Optional filter by event_type
  - Method: `count_by_type(event_type: str) -> int`
    - Count events by type
  - Async implementation following WalletRepository pattern
- [ ] **3.2** Add unit tests for decay event repository
  - Test: `test_create_decay_event()` - event stored successfully
  - Test: `test_get_wallet_events()` - fetch events for wallet
  - Test: `test_get_recent_events()` - fetch recent events
  - Test: `test_count_by_type()` - count by event type
  - Use real Supabase client (integration test pattern)

### Task 4: Batch Decay Check Orchestration (AC: 1, 2, 3, 4)

- [ ] **4.1** Create `src/walltrack/core/wallets/decay_orchestrator.py`
  - Function: `check_all_wallets(batch_size: int = 100) -> dict[str, int]`
  - Orchestration flow:
    1. Fetch all active wallets + flagged wallets from WalletRepository
    2. For each wallet: call `DecayDetector.check_wallet_decay()`
    3. If DecayEvent returned: call `DecayEventRepository.create()`
    4. Log summary of events
  - Return stats: `{"checked": N, "decay_detected": M, "recoveries": K, "consecutive_losses": L, "dormancy": P}`
  - Use `asyncio.gather()` with semaphore for parallel processing (limit concurrency to 20)
- [ ] **4.2** Add error handling with retry strategy
  - **HeliusAPIError (rate limit 429):**
    - Retry 3x with exponential backoff (1s, 2s, 4s)
    - After 3 failures: skip wallet, log warning, continue batch
  - **HeliusAPIError (other 4xx/5xx):**
    - Skip wallet immediately, log error, continue batch
  - **NetworkError (connection timeout):**
    - Skip wallet, log error, continue batch
  - **DatabaseError (Supabase):**
    - Log error with wallet_address context
    - Continue batch (don't fail entire operation)
  - Use structlog with bound context: `wallet_address`, `event_type`, `error_type`
  - Example implementation:
    ```python
    from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=4),
        retry=retry_if_exception_type(HeliusRateLimitError)
    )
    async def fetch_with_retry(wallet_address: str):
        return await helius_client.get_wallet_transactions(wallet_address)
    ```
- [ ] **4.3** Add integration tests for orchestration
  - Test: `test_check_all_wallets_end_to_end()` - full batch processing
  - Test: `test_parallel_processing()` - verify concurrency
  - Test: `test_error_handling()` - partial failures don't break batch
  - Mock HeliusClient, use real Supabase

### Task 5: Scheduler Integration (AC: 1, 2, 3)

- [ ] **5.1** Create `src/walltrack/scheduler/jobs/decay_check.py`
  - Function: `run_decay_check() -> dict[str, int]`
  - Calls `check_all_wallets()` orchestrator
  - Log results to structlog
  - Return summary stats
- [ ] **5.2** Add to scheduler configuration
  - File: `src/walltrack/scheduler/__init__.py` or `jobs.py`
  - Schedule decay check every 4 hours (configurable via Supabase config)
  - Use APScheduler (existing pattern from Epic 2)
  - Cron expression: `0 */4 * * *` (every 4 hours)
- [ ] **5.3** Add manual trigger button in UI Config page
  - File: `src/walltrack/ui/pages/config.py`
  - Button: "🔍 Check Wallet Decay"
  - Click handler: async wrapper around `check_all_wallets()`
  - Display result: "✅ Checked N wallets (M events)"

### Task 6: WalletRepository Extensions (AC: 1, 2, 3)

- [ ] **6.1** Extend `src/walltrack/data/supabase/repositories/wallet_repo.py`
  - Add unified update method: `update_decay_fields()`
    ```python
    async def update_decay_fields(
        self,
        wallet_address: str,
        decay_status: str | None = None,
        consecutive_losses: int | None = None,
        last_activity_date: datetime | None = None,
        rolling_win_rate: float | None = None,
        score: float | None = None
    ) -> None:
        """Update decay-related fields in single atomic query."""
        updates = {"updated_at": "now()"}

        if decay_status is not None:
            updates["decay_status"] = decay_status
        if consecutive_losses is not None:
            updates["consecutive_losses"] = consecutive_losses
        if last_activity_date is not None:
            updates["last_activity_date"] = last_activity_date.isoformat()
        if rolling_win_rate is not None:
            updates["rolling_win_rate"] = rolling_win_rate
        if score is not None:
            updates["score"] = score

        await self.client.table("wallets").update(updates).eq("wallet_address", wallet_address).execute()
    ```
  - **Benefits:** 1 DB query instead of 3, atomic updates, less code to maintain
  - Add method: `get_active_and_flagged() -> list[Wallet]`
    - Fetch wallets with decay_status in ('ok', 'flagged')
    - For batch decay check
- [ ] **6.2** Create comprehensive wallets decay columns migration
  - Migration file: `src/walltrack/data/supabase/migrations/008_wallets_decay_columns.sql`
  - **IMPORTANT:** This migration adds ALL decay-related columns (verified as missing from Stories 3.1-3.3)
  - SQL:
    ```sql
    -- Migration: 008_wallets_decay_columns.sql
    -- Date: 2025-12-30
    -- Story: 3.4 - Wallet Decay Detection
    -- Description: Add all decay tracking columns to wallets table

    -- Add decay status (if not exists from Story 3.1)
    ALTER TABLE walltrack.wallets ADD COLUMN IF NOT EXISTS decay_status TEXT DEFAULT 'ok'
      CHECK (decay_status IN ('ok', 'flagged', 'downgraded', 'dormant'));

    -- Add consecutive losses counter (if not exists from Story 3.1)
    ALTER TABLE walltrack.wallets ADD COLUMN IF NOT EXISTS consecutive_losses INTEGER DEFAULT 0
      CHECK (consecutive_losses >= 0);

    -- Add last activity tracking (confirmed NOT in Story 3.1)
    ALTER TABLE walltrack.wallets ADD COLUMN IF NOT EXISTS last_activity_date TIMESTAMPTZ DEFAULT now();

    -- Add rolling window win rate (confirmed NOT in Story 3.2)
    ALTER TABLE walltrack.wallets ADD COLUMN IF NOT EXISTS rolling_win_rate DECIMAL(5,2)
      CHECK (rolling_win_rate >= 0.0 AND rolling_win_rate <= 1.0);

    -- Add wallet score (NOT in any previous story)
    ALTER TABLE walltrack.wallets ADD COLUMN IF NOT EXISTS score DECIMAL(5,4) DEFAULT 0.5000
      CHECK (score >= 0.1 AND score <= 1.0);

    -- Add indexes
    CREATE INDEX IF NOT EXISTS idx_wallets_decay_status ON walltrack.wallets(decay_status);
    CREATE INDEX IF NOT EXISTS idx_wallets_last_activity ON walltrack.wallets(last_activity_date DESC);
    CREATE INDEX IF NOT EXISTS idx_wallets_score ON walltrack.wallets(score DESC);
    ```
- [ ] **6.3** Update Wallet Pydantic model
  - File: `src/walltrack/data/models/wallet.py`
  - Add fields (if not already present):
    - `rolling_win_rate: Decimal | None` - Win rate over last 20 trades
    - `last_activity_date: datetime | None` - Last trade timestamp
    - `score: Decimal = Decimal("0.5")` - Wallet quality score (0.1 to 1.0)
  - Add validator for score field:
    ```python
    @field_validator("score")
    def validate_score(cls, v):
        if v is not None and not (0.1 <= v <= 1.0):
            raise ValueError("Score must be between 0.1 and 1.0")
        return v
    ```
  - Ensure decay_status field exists (may be from Story 3.1)

### Task 7: UI Updates - Decay Badge Display (AC: 5)

- [ ] **7.1** Update Wallets table in Explorer
  - File: `src/walltrack/ui/pages/explorer.py`
  - Decay Status column already exists (from Story 3.1)
  - Update badge rendering function:
    - `render_decay_badge(status: str) -> str`
    - Mapping:
      - `'ok'` → 🟢 OK
      - `'flagged'` → 🟡 Flagged
      - `'downgraded'` → 🔴 Downgraded
      - `'dormant'` → ⚪ Dormant
  - Color coding with Gradio CSS classes
- [ ] **7.2** Add decay details to sidebar
  - File: `src/walltrack/ui/pages/explorer.py` (existing sidebar from Story 3.2)
  - Add "Decay Status" section to sidebar
  - Display:
    - Current status with badge
    - Rolling win rate (20 trades)
    - Consecutive losses count
    - Days since last activity
    - Last decay event (if any)
- [ ] **7.3** Add decay event history to sidebar
  - Display recent decay events for selected wallet
  - Show: event type, timestamp, score change
  - Fetch from `DecayEventRepository.get_wallet_events()`
  - Limit to 5 most recent events
- [ ] **7.4** Add E2E tests for decay UI
  - Test: `test_decay_badges_display()` - badges render correctly
  - Test: `test_sidebar_decay_details()` - sidebar shows decay info
  - Test: `test_decay_event_history()` - event history displays
  - Use Playwright (existing pattern from Epic 2)

### Task 8: Real-time Decay Check on Trade Completion (AC: 1, 2)

- [ ] **8.1** Add post-trade decay check hook
  - File: `src/walltrack/core/execution/` (trade executor)
  - **IMPORTANT:** Update last_activity_date BEFORE calling decay check
  - Execution sequence:
    1. Trade completes successfully
    2. Update `wallet.last_activity_date = now()` via `WalletRepository.update_decay_fields()`
    3. Call `DecayDetector.check_wallet_decay(wallet_address)`
    4. If DecayEvent returned: store event via `DecayEventRepository.create()`
  - **Rationale:** Decay check needs fresh timestamp for dormancy detection
  - **Note:** This ensures immediate decay detection after 3rd consecutive loss
- [ ] **8.2** Update WalletRepository to track last_activity
  - Method: `record_trade_activity(wallet_address: str) -> None`
  - Update last_activity_date to now()
  - Reset dormancy status if wallet was dormant
- [ ] **8.3** Add integration test for real-time decay
  - Test: `test_decay_detected_after_trade()` - immediate detection
  - Test: `test_consecutive_loss_triggers_downgrade()` - 3rd loss triggers
  - Test: `test_activity_resets_dormancy()` - trade clears dormant status

### Task 9: Integration & E2E Validation (AC: all)

- [ ] **9.1** Create end-to-end integration test
  - File: `tests/integration/test_wallet_decay_flow.py`
  - Test complete flow:
    1. Create test wallet with 20 trades (mock Helius)
    2. Set up trades with < 40% win rate
    3. Run `check_wallet_decay()`
    4. Verify decay_status changed to "flagged"
    5. Verify DecayEvent created
    6. Verify score reduced
  - Test recovery flow:
    1. Wallet with flagged status
    2. Add winning trades to push win rate > 50%
    3. Run decay check
    4. Verify status changed to "ok"
    5. Verify recovery event created
  - Test consecutive losses:
    1. Wallet with recent trades
    2. Add 3 consecutive losing trades
    3. Run decay check
    4. Verify status changed to "downgraded"
  - Test dormancy:
    1. Wallet with last_activity 35 days ago
    2. Run decay check
    3. Verify status changed to "dormant"
- [ ] **9.2** Create E2E test for full UI workflow
  - File: `tests/e2e/test_wallet_decay_e2e.py`
  - Navigate to Explorer → Wallets
  - Verify decay badges display correctly
  - Click wallet row
  - Verify sidebar shows decay details
  - Verify event history displays
  - Navigate to Config → Decay Check
  - Click "Check Wallet Decay" button
  - Wait for completion
  - Verify status bar updates
  - Verify table refreshes with new badges
- [ ] **9.3** Run full test suite
  - Unit tests: ~25-30 new tests
  - Integration tests: ~8-10 new tests
  - E2E tests: ~5-7 new tests
  - Expected total: ~40-47 new tests for Story 3.4
- [ ] **9.4** Update sprint-status.yaml
  - Mark Story 3.4 as `done`
  - Update test count

---

## Dev Notes

### Legacy Code Reference (Inspiration Only)

**IMPORTANT:** Legacy code in `legacy/src/walltrack/` is for **inspiration only**. Do NOT copy/paste. V2 rebuilds from scratch with simplified architecture.

**Key files to review for patterns:**

| Legacy File | Pattern to Learn |
|-------------|------------------|
| `legacy/src/walltrack/discovery/decay_detector.py` | DecayDetector class structure, rolling window logic, consecutive loss counting |
| `legacy/src/walltrack/scheduler/tasks/decay_check_task.py` | Batch processing with semaphore, async orchestration |
| `legacy/src/walltrack/data/supabase/repositories/decay_event_repo.py` | DecayEvent storage pattern |

**Configuration Constants (from legacy):**

**IMPORTANT:** In V2, these values are stored in `walltrack.config` table (configuration-driven design, NOT hardcoded).

Default values (from legacy):
```python
decay_rolling_window_size = 20          # Number of trades to analyze
decay_min_trades = 20                   # Minimum trades before decay detection
decay_threshold = 0.40                  # 40% win rate triggers flagged
decay_recovery_threshold = 0.50         # 50% win rate triggers recovery
decay_consecutive_loss_threshold = 3    # 3 consecutive losses triggers downgrade
decay_dormancy_days = 30                # 30 days without activity triggers dormant
decay_score_downgrade_decay = 0.80      # Reduce score by 20% on decay
decay_score_downgrade_loss = 0.95       # Reduce score by 5% per consecutive loss
```

These values are loaded from database via `DecayConfig.from_db()` (see Task 2.1).

**Patterns to preserve:**
- Rolling window analysis (20 trades)
- DecayEvent dataclass for event tracking
- Notification callback pattern for alerts
- Batch processing with concurrency limits (semaphore)
- Graceful error handling (skip wallet, continue batch)

**Patterns to simplify in V2:**
- ❌ V1 had separate `WalletStatus` enum - V2 uses simple `decay_status` TEXT field
- ❌ V1 had complex recovery logic - V2 simplifies to threshold-based
- ✅ V2 adds dormancy detection (not in V1)
- ✅ V2 integrates with Story 3.2 performance metrics (win_rate already calculated)

### Technical Decisions

**1. Rolling Window Analysis**

Use most recent N trades (configurable) for win rate calculation:

```python
async def calculate_rolling_win_rate(
    wallet_address: str,
    config: DecayConfig
) -> float:
    """Calculate win rate over last N trades (configured)."""
    # Reuse HeliusClient from Story 3.2
    transactions = await helius_client.get_wallet_transactions(wallet_address, limit=100)

    # Reuse match_trades() from Story 3.2
    trades = match_trades(transactions)

    # Take most recent N completed trades
    recent_trades = trades[:config.rolling_window_size]

    if len(recent_trades) < config.min_trades:
        return None  # Insufficient data

    wins = sum(1 for t in recent_trades if t.pnl > 0)
    return wins / config.rolling_window_size
```

**2. Consecutive Loss Counting**

```python
def count_consecutive_losses(trades: list[Trade]) -> int:
    """Count consecutive losses from most recent trades."""
    consecutive = 0
    for trade in trades:  # trades already sorted by date desc
        if trade.pnl <= 0:
            consecutive += 1
        else:
            break  # Stop at first win
    return consecutive
```

**3. Dormancy Detection**

```python
from datetime import datetime, timezone

def is_dormant(wallet: Wallet, config: DecayConfig) -> bool:
    """Check if wallet is dormant (N+ days no activity, configurable)."""
    if not wallet.last_activity_date:
        return False

    # Use timezone-aware datetime to match TIMESTAMPTZ from DB
    now = datetime.now(timezone.utc)
    days_inactive = (now - wallet.last_activity_date).days
    return days_inactive >= config.dormancy_days
```

**4. Score Adjustment**

```python
def apply_decay_score_adjustment(
    wallet: Wallet,
    event_type: str,
    config: DecayConfig,
    consecutive_losses: int = 0
) -> float:
    """Adjust wallet score based on decay event with bounds enforcement."""
    MIN_SCORE = 0.1  # Never reduce below (wallet still viable)
    MAX_SCORE = 1.0  # Perfect score ceiling

    # Special case: if current score is 0 or negative, reset to minimum
    if wallet.score <= 0:
        return MIN_SCORE

    # Apply adjustment based on event type
    if event_type == "decay_detected":
        # Reduce by configured percentage (default 20%)
        new_score = wallet.score * config.score_downgrade_decay
    elif event_type == "consecutive_losses":
        # Reduce by configured percentage per loss beyond threshold (default 5% per loss)
        losses_beyond = max(consecutive_losses - config.consecutive_loss_threshold, 0)
        downgrade = config.score_downgrade_loss ** losses_beyond
        new_score = wallet.score * downgrade
    elif event_type == "recovery":
        # Increase by 10% (simple and predictable)
        new_score = wallet.score * 1.10
    else:
        new_score = wallet.score

    # Enforce bounds
    return max(MIN_SCORE, min(MAX_SCORE, new_score))
```

**5. Configuration-Driven Design (Migration 007)**

All decay thresholds are stored in `walltrack.config` table for runtime configurability:

```sql
-- Migration: 007_config_decay_parameters.sql
-- Date: 2025-12-30
-- Story: 3.4 - Wallet Decay Detection
-- Description: Add decay configuration parameters to config table

ALTER TABLE walltrack.config ADD COLUMN IF NOT EXISTS decay_rolling_window_size INTEGER DEFAULT 20;
ALTER TABLE walltrack.config ADD COLUMN IF NOT EXISTS decay_min_trades INTEGER DEFAULT 20;
ALTER TABLE walltrack.config ADD COLUMN IF NOT EXISTS decay_threshold DECIMAL(3,2) DEFAULT 0.40;
ALTER TABLE walltrack.config ADD COLUMN IF NOT EXISTS decay_recovery_threshold DECIMAL(3,2) DEFAULT 0.50;
ALTER TABLE walltrack.config ADD COLUMN IF NOT EXISTS decay_consecutive_loss_threshold INTEGER DEFAULT 3;
ALTER TABLE walltrack.config ADD COLUMN IF NOT EXISTS decay_dormancy_days INTEGER DEFAULT 30;
ALTER TABLE walltrack.config ADD COLUMN IF NOT EXISTS decay_score_downgrade_decay DECIMAL(3,2) DEFAULT 0.80;
ALTER TABLE walltrack.config ADD COLUMN IF NOT EXISTS decay_score_downgrade_loss DECIMAL(3,2) DEFAULT 0.95;

-- Rollback (commented):
-- ALTER TABLE walltrack.config DROP COLUMN IF EXISTS decay_rolling_window_size;
-- ALTER TABLE walltrack.config DROP COLUMN IF EXISTS decay_min_trades;
-- ALTER TABLE walltrack.config DROP COLUMN IF EXISTS decay_threshold;
-- ALTER TABLE walltrack.config DROP COLUMN IF EXISTS decay_recovery_threshold;
-- ALTER TABLE walltrack.config DROP COLUMN IF EXISTS decay_consecutive_loss_threshold;
-- ALTER TABLE walltrack.config DROP COLUMN IF EXISTS decay_dormancy_days;
-- ALTER TABLE walltrack.config DROP COLUMN IF EXISTS decay_score_downgrade_decay;
-- ALTER TABLE walltrack.config DROP COLUMN IF EXISTS decay_score_downgrade_loss;
```

**6. Initial Score Calculation**

When a wallet is first discovered, its score is calculated based on performance metrics:

```python
def calculate_initial_score(wallet: Wallet) -> float:
    """
    Calculate initial wallet score based on performance metrics.

    Formula: score = win_rate * 0.7 + normalized_pnl * 0.3
    Where:
    - win_rate: from Story 3.2 performance analysis (0.0 to 1.0)
    - normalized_pnl: pnl_total clamped to [-10, 10] SOL, then normalized to [0, 1]

    Default score for new wallets (< 10 trades): 0.5 (neutral)
    """
    if wallet.total_trades < 10:
        return 0.5  # Neutral score for new wallets

    # Normalize PnL to [0, 1] range (clamp to ±10 SOL)
    pnl_clamped = max(-10, min(10, wallet.pnl_total))
    pnl_normalized = (pnl_clamped + 10) / 20  # Maps [-10, 10] to [0, 1]

    # Weighted combination: 70% win rate, 30% PnL
    score = wallet.win_rate * 0.7 + pnl_normalized * 0.3

    # Enforce bounds [0.1, 1.0]
    return max(0.1, min(1.0, score))
```

**7. Priority Order for Decay Checks**

When multiple decay conditions are true, apply in this priority order:

1. **DORMANT** (days_inactive >= config.dormancy_days) - Overrides all other conditions
2. **DOWNGRADED** (consecutive_losses >= config.consecutive_loss_threshold) - Most severe
3. **FLAGGED** (rolling_win_rate < config.decay_threshold) - Moderate warning
4. **OK** (recovery: rolling_win_rate >= config.recovery_threshold AND currently flagged) - Only from flagged state
5. **OK** (default) - No change or already ok

**Example:** Wallet with win_rate=35%, consecutive_losses=4, days_inactive=5
→ Status = **DOWNGRADED** (priority 2 wins over priority 3)

**8. Database Schema - decay_events table**

```sql
-- Migration: 009_decay_events_table.sql
CREATE TABLE IF NOT EXISTS walltrack.decay_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    wallet_address TEXT NOT NULL REFERENCES walltrack.wallets(wallet_address) ON DELETE CASCADE,
    event_type TEXT NOT NULL CHECK (event_type IN ('decay_detected', 'recovery', 'consecutive_losses', 'dormancy')),
    rolling_win_rate DECIMAL(5,2),
    lifetime_win_rate DECIMAL(5,2),
    consecutive_losses INTEGER DEFAULT 0,
    score_before DECIMAL(5,4),
    score_after DECIMAL(5,4),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_decay_events_wallet ON walltrack.decay_events(wallet_address, created_at DESC);
CREATE INDEX idx_decay_events_type ON walltrack.decay_events(event_type, created_at DESC);

-- Enable RLS
ALTER TABLE walltrack.decay_events ENABLE ROW LEVEL SECURITY;

-- Grant permissions
GRANT SELECT, INSERT ON walltrack.decay_events TO anon;
GRANT ALL ON walltrack.decay_events TO service_role;
```

**6. DecayEvent Pydantic Model**

```python
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field

class DecayEventType(str, Enum):
    DECAY_DETECTED = "decay_detected"
    RECOVERY = "recovery"
    CONSECUTIVE_LOSSES = "consecutive_losses"
    DORMANCY = "dormancy"

class DecayEventCreate(BaseModel):
    wallet_address: str = Field(..., min_length=32, max_length=44)
    event_type: DecayEventType
    rolling_win_rate: float | None = Field(None, ge=0.0, le=1.0)
    lifetime_win_rate: float | None = Field(None, ge=0.0, le=1.0)
    consecutive_losses: int = Field(0, ge=0)
    score_before: float = Field(..., ge=0.0, le=1.0)
    score_after: float = Field(..., ge=0.0, le=1.0)

class DecayEvent(DecayEventCreate):
    id: str
    created_at: datetime
```

### Architecture Compliance

**Naming Conventions:**
- Files: `decay_detector.py`, `decay_event_repo.py` (snake_case)
- Classes: `DecayDetector`, `DecayEventRepository` (PascalCase)
- Functions: `check_wallet_decay`, `count_consecutive_losses` (snake_case)
- Supabase table: `decay_events` (snake_case plural)
- Supabase columns: `wallet_address`, `event_type`, `created_at` (snake_case)

**Layer Boundaries:**
- `core/wallets/` = Business logic (decay detection, score adjustment)
- `data/supabase/repositories/` = Database access (decay events)
- `scheduler/jobs/` = Scheduled tasks (batch decay check)
- Never call `data/` directly from `api/` (go through `core/`)

**Error Handling:**
- All exceptions inherit from `WallTrackError`
- Custom exception: `DecayDetectionError`
- Never bare `raise Exception`

**Logging:**
- Use structlog with bound context
- Format: `log.info("decay_detected", wallet_address=addr, rolling_win_rate=rate)`
- Never string formatting in log calls

### Dependencies

**Prerequisites:**
- ✅ Story 3.1 completed (wallets table with decay_status column)
- ✅ Story 3.2 completed (performance metrics, win_rate calculation)
- ✅ HeliusClient exists (transaction history fetching)
- ✅ WalletRepository exists (wallet CRUD)

**Reused Components:**
- `HeliusClient.get_wallet_transactions()` (Story 3.2)
- `TransactionParser` (Story 3.2)
- `WalletRepository` (Story 3.1)

**New Components:**
- `DecayDetector` class
- `DecayEventRepository`
- `decay_check` scheduler job
- UI decay badge rendering

### Testing Strategy

**Unit Tests (~25-30 tests):**
- DecayDetector (10 tests)
- DecayEventRepository (5 tests)
- Score adjustment logic (5 tests)
- Rolling window calculation (5 tests)

**Integration Tests (~8-10 tests):**
- Full decay detection flow (3 tests)
- Batch processing (2 tests)
- Real-time post-trade check (2 tests)
- Database sync (2 tests)

**E2E Tests (~5-7 tests):**
- UI badge display (2 tests)
- Sidebar decay details (2 tests)
- Manual trigger button (2 tests)

**Mock Strategy:**
- Mock HeliusClient for transaction history
- Real Supabase for integration tests
- Playwright for E2E tests

### Performance Considerations

**Batch Processing:**
- Limit concurrency to 20 wallets (asyncio.Semaphore)
- Process in batches of 100 wallets
- Expected time: ~5-10 minutes for 1000 wallets

**Database Queries:**
- Index on `decay_events.wallet_address` for fast lookup
- Index on `wallets.last_activity_date` for dormancy detection
- Index on `wallets.decay_status` for batch fetching

**Scheduler Frequency:**
- Run every 4 hours (configurable)
- Cron: `0 */4 * * *`
- Avoid overlap with surveillance scheduler (every 2 hours)

### Edge Cases to Handle

1. **Wallet with < 20 trades:** Skip decay check, return None
2. **All trades are wins:** decay_status = "ok", no event
3. **All trades are losses:** decay_status = "downgraded", consecutive_losses = 20
4. **Wallet was dormant, makes new trade:** Reset to "ok", create recovery event
5. **Score already at minimum (0.1):** Don't reduce further
6. **Database connection error:** Log error, skip wallet, continue batch
7. **Helius API error:** Log error, skip wallet, continue batch

---

## Acceptance Criteria Checklist

- [ ] AC1: Rolling window decay detection (win rate < 40% → flagged)
- [ ] AC2: Consecutive loss detection (3+ losses → downgraded)
- [ ] AC3: Dormancy detection (30+ days → dormant)
- [ ] AC4: Decay events logged to database
- [ ] AC5: UI badges display correctly (🟢🟡🔴⚪)

---

## Definition of Done

- [ ] All tasks completed
- [ ] All acceptance criteria met
- [ ] Unit tests passing (~25-30 new tests)
- [ ] Integration tests passing (~8-10 new tests)
- [ ] E2E tests passing (~5-7 new tests)
- [ ] Code review completed
- [ ] Documentation updated (this file)
- [ ] No regressions in existing tests
- [ ] Story marked as `done` in sprint-status.yaml

---

**Estimated Test Count:** ~40-47 new tests for Story 3.4

**Dependencies:**
- Story 3.1 (Wallet Discovery) must be completed
- Story 3.2 (Wallet Performance Analysis) must be completed
- HeliusClient with transaction history API

**Next Story:** 3.5 - Wallet Blacklist & Watchlist Management

---

## Dev Agent Record

### Context Reference

**Story Context Created By:** Workflow execution - 2025-12-30

**Source Documents Analyzed:**
- docs/epics.md (Epic 3 complete breakdown, Story 3.4 requirements)
- docs/sprint-artifacts/sprint-status.yaml (Epic 3 progress)
- docs/sprint-artifacts/epic-3/3-1-wallet-discovery-from-tokens.md (Wallet schema reference)
- docs/sprint-artifacts/epic-3/3-2-wallet-performance-analysis.md (Performance metrics reference)
- src/walltrack/data/supabase/migrations/006_wallets_behavioral_profiling.sql (Existing migrations)

**Legacy Code References:**
- `legacy/src/walltrack/discovery/decay_detector.py` - DecayDetector class, rolling window logic, score adjustment
- `legacy/src/walltrack/scheduler/tasks/decay_check_task.py` - Batch processing pattern, async orchestration
- `legacy/src/walltrack/data/supabase/repositories/decay_event_repo.py` - DecayEvent repository pattern

**Key Patterns Extracted from Legacy:**
- Rolling window analysis (20 trades)
- Configuration constants (DECAY_THRESHOLD = 0.40, RECOVERY_THRESHOLD = 0.50)
- DecayEvent dataclass for event tracking
- Batch processing with semaphore (concurrency limit)
- Score downgrade factors (0.80 for decay, 0.95 per consecutive loss)
- Notification callback pattern

### Agent Model Used

Claude Sonnet 4.5 (claude-sonnet-4-5-20250929)

### Implementation Approach

**V2 Simplifications:**
1. Use existing `decay_status` TEXT field (from Story 3.1) instead of V1's WalletStatus enum
2. Reuse performance metrics from Story 3.2 (win_rate, pnl_total)
3. Add dormancy detection (not in V1)
4. Simplified recovery logic (threshold-based, not complex state machine)

**V2 Additions:**
1. Dormancy detection (30+ days no activity)
2. Real-time decay check after each trade
3. last_activity_date tracking
4. UI integration with existing sidebar (Story 3.2)

**Critical Dependencies:**
- Story 3.1: wallets table schema, decay_status column
- Story 3.2: HeliusClient, TransactionParser, performance metrics
- Epic 2: Scheduler infrastructure (APScheduler)

### File List

**New Files to Create:**

Database Migrations:
- `src/walltrack/data/supabase/migrations/007_config_decay_parameters.sql` - Decay configuration parameters in config table
- `src/walltrack/data/supabase/migrations/008_wallets_decay_columns.sql` - Add decay tracking columns to wallets (decay_status, consecutive_losses, last_activity_date, rolling_win_rate, score)
- `src/walltrack/data/supabase/migrations/009_decay_events_table.sql` - DecayEvent table for logging decay status changes

Core Logic:
- `src/walltrack/core/wallets/decay_detector.py` - DecayDetector service (rolling window, consecutive loss, dormancy)
- `src/walltrack/core/wallets/decay_orchestrator.py` - Batch processing orchestration

Data Models:
- `src/walltrack/data/models/decay_event.py` - DecayEvent, DecayEventCreate Pydantic models

Repositories:
- `src/walltrack/data/supabase/repositories/decay_event_repo.py` - DecayEventRepository

Scheduler:
- `src/walltrack/scheduler/jobs/decay_check.py` - Scheduled decay check job

Tests:
- `tests/unit/core/wallets/test_decay_detector.py` - DecayDetector unit tests
- `tests/unit/data/supabase/test_decay_event_repo.py` - Repository unit tests
- `tests/integration/test_wallet_decay_flow.py` - End-to-end integration tests
- `tests/e2e/test_wallet_decay_e2e.py` - E2E UI tests

**Modified Files:**

Repositories:
- `src/walltrack/data/supabase/repositories/wallet_repo.py` - Add decay-related methods (update_decay_status, update_consecutive_losses, update_last_activity, get_active_and_flagged)
- `src/walltrack/data/models/wallet.py` - Add rolling_win_rate, last_activity_date fields (if not present)

UI:
- `src/walltrack/ui/pages/explorer.py` - Update decay badge rendering, add decay details to sidebar
- `src/walltrack/ui/pages/config.py` - Add manual decay check trigger button

Scheduler:
- `src/walltrack/scheduler/__init__.py` or `jobs.py` - Register decay_check job

Trade Execution:
- `src/walltrack/core/execution/` (trade executor) - Add post-trade decay check hook

Documentation:
- `docs/sprint-artifacts/sprint-status.yaml` - Update story status to done

**Total:** ~11 new files (3 migrations + 8 source/test files) + 7 modified files = 18 files

---

_Story context generated by Workflow execution - 2025-12-30_
