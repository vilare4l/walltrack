# Story 3.5: Auto Watchlist Management

**Status:** ready-for-dev
**Epic:** 3 - Wallet Intelligence & Watchlist Management
**Created:** 2025-12-30
**Sprint Artifacts:** docs/sprint-artifacts/epic-3/

---

## Story

**As an** operator,
**I want** wallets to be automatically evaluated against configurable criteria,
**So that** only high-quality wallets are monitored by expensive downstream operations (clustering, decay detection, signal scoring).

**FRs Covered:** FR10, FR11, FR12, FR13, FR14, FR15, FR16

**From Epic:** Epic 3 - Wallet Intelligence & Watchlist Management

**Key Change:** This story establishes the status-based filtering pattern for all downstream workers (clustering in Epic 4, decay detection in Story 3.4, signal scoring in Epic 5).

---

## Acceptance Criteria

### AC1: Wallet Status Lifecycle

**Given** a wallet exists in the database with status 'discovered' or 'profiled'
**When** watchlist evaluation runs
**Then** wallet status is updated to 'watchlisted' if ALL criteria met
**And** wallet status is updated to 'ignored' if ANY criteria not met
**And** wallet metadata is populated: watchlist_added_date, watchlist_score, watchlist_reason
**And** status transition is logged with timestamp and reason

### AC2: Configuration-Driven Criteria

**Given** watchlist criteria are configured in config table
**When** evaluation runs
**Then** system uses configurable parameters:
  - min_winrate (default: 0.70)
  - min_pnl (default: 5.0 SOL)
  - min_trades (default: 10)
  - max_decay_score (default: 0.3)
**And** criteria can be updated via Config page UI
**And** changes take effect on next evaluation

### AC3: Automatic Evaluation Trigger

**Given** Story 3.3 (Behavioral Profiling) completes successfully
**When** wallet.wallet_status transitions from 'discovered' to 'profiled'
**Then** watchlist evaluation is automatically triggered
**And** wallet status is updated to 'watchlisted' or 'ignored'
**And** no manual intervention required

### AC4: Manual Override Capabilities

**Given** I am viewing a wallet in Explorer
**When** I use manual controls
**Then** I can:
  - Manually add wallet to watchlist (status: profiled/ignored → watchlisted)
  - Manually remove wallet from watchlist (status: watchlisted → ignored)
  - Blacklist wallet permanently (status: any → blacklisted)
**And** manual actions override automatic evaluation
**And** manual actions are logged with user action timestamp

### AC5: UI Watchlist Status Display

**Given** wallets have been evaluated
**When** I navigate to Explorer → Wallets tab
**Then** Status column displays current wallet_status with color indicators:
  - 🟢 watchlisted (green)
  - ⚪ profiled (white)
  - 🔴 ignored (red)
  - ⚫ blacklisted (black)
**And** I can filter table by status
**And** Watchlist Score column displays watchlist_score (0.0-1.0)
**And** I can sort by Watchlist Score

### AC6: Performance Filtering Pattern Established

**Given** Story 3.5 is complete
**When** Epic 4 (Clustering) begins implementation
**Then** clustering queries use `WHERE wallet_status = 'watchlisted'`
**And** 20-100x performance gain vs clustering all wallets
**And** pattern is documented for future workers (decay detection, signal scoring)

---

## Tasks / Subtasks

### Task 1: Database Schema - Wallet Status & Metadata (AC: 1, 2, 5)

- [ ] **1.1** Create Supabase migration: `004_wallets_watchlist_status.sql`
  - Add wallet_status column:
    - `wallet_status TEXT NOT NULL DEFAULT 'discovered'`
    - `CHECK (wallet_status IN ('discovered', 'profiled', 'ignored', 'watchlisted', 'flagged', 'removed', 'blacklisted'))`
  - Add watchlist metadata columns:
    - `watchlist_added_date TIMESTAMPTZ` - Date added to watchlist
    - `watchlist_score NUMERIC(5,4)` - Composite criteria score (0.0000-1.0000)
    - `watchlist_reason TEXT` - Why watchlisted or ignored
    - `manual_override BOOLEAN DEFAULT FALSE` - Manually added/removed
  - Add index: `CREATE INDEX idx_wallets_status ON walltrack.wallets(wallet_status);`
  - Add index: `CREATE INDEX idx_wallets_watchlist_score ON walltrack.wallets(watchlist_score DESC) WHERE wallet_status = 'watchlisted';`
  - Update existing wallets: `UPDATE walltrack.wallets SET wallet_status = 'profiled' WHERE wallet_status IS NULL;`
- [ ] **1.2** Execute migration on Supabase
  - Connect to Supabase database
  - Run migration SQL
  - Verify columns added: `\d walltrack.wallets`
- [ ] **1.3** Update `src/walltrack/data/models/wallet.py` Pydantic model
  - Add fields: `wallet_status`, `watchlist_added_date`, `watchlist_score`, `watchlist_reason`, `manual_override`
  - Add Enum: `WalletStatus` with all 7 status values
  - Add validator for wallet_status (must be valid enum value)
  - Add validator for watchlist_score (0.0000 to 1.0000 range)

### Task 2: Configuration Table - Watchlist Criteria (AC: 2)

- [ ] **2.1** Create Supabase migration: `004b_config_watchlist_criteria.sql`
  - Insert watchlist configuration parameters into config table:
    ```sql
    INSERT INTO walltrack.config (category, key, value, description) VALUES
    ('watchlist', 'min_winrate', '0.70', 'Minimum win rate to qualify for watchlist (0.0-1.0)'),
    ('watchlist', 'min_pnl', '5.0', 'Minimum total PnL in SOL to qualify for watchlist'),
    ('watchlist', 'min_trades', '10', 'Minimum number of trades to qualify for watchlist'),
    ('watchlist', 'max_decay_score', '0.3', 'Maximum decay score to qualify for watchlist (0.0-1.0)');
    ```
  - Verify config.category column supports 'watchlist' (should already exist from Epic 2)
- [ ] **2.2** Execute migration on Supabase
  - Run migration SQL
  - Verify config rows inserted: `SELECT * FROM walltrack.config WHERE category = 'watchlist';`
- [ ] **2.3** Extend ConfigRepository to fetch watchlist criteria
  - File: `src/walltrack/data/supabase/repositories/config_repo.py`
  - Add method: `get_watchlist_criteria() -> dict[str, float]`
  - Return dict: `{"min_winrate": 0.70, "min_pnl": 5.0, "min_trades": 10, "max_decay_score": 0.3}`
  - Cache config for 5 minutes to reduce DB queries

### Task 3: Watchlist Evaluation Service (AC: 1, 2)

- [ ] **3.1** Create watchlist evaluation service
  - File: `src/walltrack/core/wallets/watchlist.py`
  - Class: `WatchlistEvaluator`
  - Method: `evaluate_wallet(wallet: Wallet) -> WatchlistDecision`
  - Logic:
    1. Fetch watchlist criteria from ConfigRepository
    2. Calculate composite score using weighted formula:
       - win_rate component: `(wallet.win_rate / min_winrate) * 0.40` (40% weight)
       - pnl component: `(wallet.pnl_total / min_pnl) * 0.30` (30% weight)
       - trades component: `(wallet.total_trades / min_trades) * 0.20` (20% weight)
       - decay component: `(1 - wallet.decay_score / max_decay_score) * 0.10` (10% weight)
    3. Check ALL criteria:
       - win_rate >= min_winrate
       - pnl_total >= min_pnl
       - total_trades >= min_trades
       - decay_score <= max_decay_score (if decay calculated, else skip)
    4. Decision:
       - ALL criteria met → status='watchlisted', score=composite_score, reason="Meets all criteria"
       - ANY criteria failed → status='ignored', score=composite_score, reason="Failed: [list of failed criteria]"
  - Return `WatchlistDecision` dataclass with status, score, reason
- [ ] **3.2** Create WatchlistDecision dataclass
  - File: `src/walltrack/data/models/wallet.py` (add to existing file)
  - Fields: `status` (WalletStatus enum), `score` (Decimal), `reason` (str), `timestamp` (datetime)
- [ ] **3.3** Unit tests for watchlist evaluator
  - File: `tests/unit/core/wallets/test_watchlist.py`
  - Test: `test_evaluate_wallet_all_criteria_met()` - wallet qualifies
  - Test: `test_evaluate_wallet_low_winrate()` - fails win rate
  - Test: `test_evaluate_wallet_low_pnl()` - fails PnL
  - Test: `test_evaluate_wallet_insufficient_trades()` - fails trade count
  - Test: `test_evaluate_wallet_high_decay()` - fails decay score
  - Test: `test_evaluate_wallet_composite_score_calculation()` - score formula
  - Test: `test_evaluate_wallet_missing_decay()` - handles missing decay gracefully

### Task 4: WalletRepository Extensions (AC: 1, 4)

- [ ] **4.1** Extend `src/walltrack/data/supabase/repositories/wallet_repo.py`
  - Add method: `update_watchlist_status(wallet_address: str, decision: WatchlistDecision, manual: bool = False) -> None`
  - Update wallets table:
    - Set `wallet_status = decision.status`
    - Set `watchlist_score = decision.score`
    - Set `watchlist_reason = decision.reason`
    - Set `watchlist_added_date = now()` (if status='watchlisted')
    - Set `manual_override = manual`
  - Add method: `get_wallets_by_status(status: WalletStatus) -> list[Wallet]`
  - Add method: `get_watchlist_count() -> int` (count wallets where status='watchlisted')
  - Add method: `blacklist_wallet(wallet_address: str, reason: str) -> None`
  - Handle errors gracefully (log + raise custom exception)
- [ ] **4.2** Update Neo4j wallet node properties
  - File: `src/walltrack/data/neo4j/services/wallet_sync.py`
  - Add `wallet_status` property to Wallet nodes
  - Update Cypher: `MERGE (w:Wallet {wallet_address: $addr}) SET w.wallet_status = $status, w.watchlist_score = $score`
  - Best effort sync (non-fatal if fails)
- [ ] **4.3** Unit tests for repository extensions
  - File: `tests/unit/data/supabase/test_wallet_repo_watchlist.py`
  - Test: `test_update_watchlist_status_watchlisted()` - status updated correctly
  - Test: `test_update_watchlist_status_ignored()` - ignored status set
  - Test: `test_update_watchlist_status_manual_override()` - manual flag set
  - Test: `test_get_wallets_by_status()` - filter by status works
  - Test: `test_get_watchlist_count()` - count correct
  - Test: `test_blacklist_wallet()` - blacklist applied

### Task 5: Integration with Story 3.3 (AC: 3)

- [ ] **5.1** Update behavioral profiling orchestrator
  - File: `src/walltrack/core/wallets/behavioral_profiler.py` (from Story 3.3)
  - After profiling completes:
    1. Update wallet.wallet_status from 'discovered' to 'profiled'
    2. Trigger watchlist evaluation: `WatchlistEvaluator.evaluate_wallet(wallet)`
    3. Update wallet with decision: `WalletRepository.update_watchlist_status(wallet.wallet_address, decision)`
    4. Log transition: `wallet.wallet_address profiled → {decision.status} (score={decision.score})`
  - Error handling: If watchlist evaluation fails, still mark as 'profiled' (don't block profiling)
- [ ] **5.2** Add integration test for automatic trigger
  - File: `tests/integration/test_watchlist_auto_trigger.py`
  - Test: `test_profiling_triggers_watchlist_evaluation()`
    1. Create wallet with status='discovered'
    2. Run behavioral profiling
    3. Verify wallet.wallet_status updated to 'watchlisted' or 'ignored'
    4. Verify watchlist metadata populated
  - Use real databases (Supabase + Neo4j)

### Task 6: Config Page UI - Watchlist Criteria (AC: 2)

- [ ] **6.1** Add "Watchlist Criteria" section to Config page
  - File: `src/walltrack/ui/pages/config.py`
  - New accordion: "Watchlist Criteria"
  - Input fields:
    - Minimum Win Rate: `gr.Slider(minimum=0.0, maximum=1.0, value=0.70, step=0.05, label="Min Win Rate")`
    - Minimum PnL (SOL): `gr.Number(value=5.0, label="Min PnL (SOL)")`
    - Minimum Trades: `gr.Number(value=10, label="Min Trades", precision=0)`
    - Maximum Decay Score: `gr.Slider(minimum=0.0, maximum=1.0, value=0.3, step=0.05, label="Max Decay Score")`
  - Save button: "Update Watchlist Criteria"
  - Click handler: `update_watchlist_criteria()` → writes to config table
  - Display current values on page load
- [ ] **6.2** Implement save handler
  - Function: `update_watchlist_criteria(min_winrate, min_pnl, min_trades, max_decay) -> str`
  - Update config table via ConfigRepository
  - Clear config cache (force reload on next evaluation)
  - Return status: "✅ Watchlist criteria updated"
- [ ] **6.3** E2E test for config update
  - File: `tests/e2e/test_config_watchlist_criteria.py`
  - Navigate to Config → Watchlist Criteria
  - Change min_winrate slider
  - Click "Update Watchlist Criteria"
  - Verify success message
  - Verify config table updated

### Task 7: Explorer Page UI - Status Display & Filters (AC: 5)

- [ ] **7.1** Update Wallets table columns
  - File: `src/walltrack/ui/pages/explorer.py`
  - Add Status column (after Address column): displays wallet_status with emoji indicator
    - 🟢 watchlisted (green text)
    - ⚪ profiled (white text)
    - 🔴 ignored (red text)
    - ⚫ blacklisted (black text)
    - 🟡 flagged (yellow text)
    - 🟤 removed (brown text)
  - Add Watchlist Score column (after Status): displays watchlist_score as `f"{score:.4f}"` or "N/A"
  - Reorder columns: ["Address", "Status", "Watchlist Score", "Win Rate", "Decay Status", "Signals", "Cluster"]
- [ ] **7.2** Add status filter dropdown
  - Above Wallets table: `gr.Dropdown(choices=["All", "Watchlisted", "Profiled", "Ignored", "Blacklisted"], value="All", label="Filter by Status")`
  - On change: filter table rows by wallet_status
  - Default: "All" (show all wallets)
- [ ] **7.3** Update table data fetcher
  - Function: `get_wallets_table_data(status_filter: str = "All") -> pd.DataFrame`
  - If status_filter != "All": `WHERE wallet_status = status_filter.lower()`
  - Fetch wallets with watchlist metadata
  - Format Status column with emoji
  - Format Watchlist Score with 4 decimal places
- [ ] **7.4** E2E test for status display and filter
  - File: `tests/e2e/test_explorer_wallets_watchlist.py`
  - Navigate to Explorer → Wallets
  - Verify Status column displays emoji indicators
  - Verify Watchlist Score column shows values
  - Change status filter to "Watchlisted"
  - Verify table only shows watchlisted wallets
  - Change filter to "Ignored"
  - Verify table only shows ignored wallets

### Task 8: Manual Override Controls (AC: 4)

- [ ] **8.1** Add manual control buttons to wallet detail sidebar
  - File: `src/walltrack/ui/pages/explorer.py` (wallet detail sidebar)
  - Add buttons:
    - "Add to Watchlist" (visible if status != 'watchlisted')
    - "Remove from Watchlist" (visible if status == 'watchlisted')
    - "Blacklist Wallet" (always visible, requires confirmation)
  - Click handlers:
    - `add_to_watchlist(wallet_address)` → update status to 'watchlisted', set manual_override=True
    - `remove_from_watchlist(wallet_address)` → update status to 'ignored', set manual_override=True
    - `blacklist_wallet(wallet_address)` → update status to 'blacklisted', set manual_override=True
  - Confirmation dialog for blacklist (Gradio modal)
- [ ] **8.2** Implement manual override handlers
  - Function: `add_to_watchlist(wallet_address: str) -> str`
    - Call `WalletRepository.update_watchlist_status(wallet_address, decision, manual=True)`
    - decision.status = 'watchlisted', decision.reason = "Manually added"
    - Return status: "✅ Wallet added to watchlist"
  - Function: `remove_from_watchlist(wallet_address: str) -> str`
    - Update status to 'ignored', manual=True
    - Return status: "✅ Wallet removed from watchlist"
  - Function: `blacklist_wallet(wallet_address: str, reason: str) -> str`
    - Call `WalletRepository.blacklist_wallet(wallet_address, reason)`
    - Return status: "✅ Wallet blacklisted"
- [ ] **8.3** E2E test for manual controls
  - File: `tests/e2e/test_explorer_wallets_manual_controls.py`
  - Click wallet row to open sidebar
  - Click "Add to Watchlist" button
  - Verify success message
  - Verify Status column updated to 🟢 watchlisted
  - Click "Remove from Watchlist"
  - Verify Status column updated to 🔴 ignored
  - Click "Blacklist Wallet"
  - Confirm dialog
  - Verify Status column updated to ⚫ blacklisted

### Task 9: Integration & E2E Validation (AC: all)

- [ ] **9.1** Create end-to-end integration test
  - File: `tests/integration/test_watchlist_full_flow.py`
  - Test complete watchlist flow:
    1. Create wallet with metrics (from Story 3.2)
    2. Run behavioral profiling (from Story 3.3) → triggers watchlist evaluation
    3. Verify wallet status updated to 'watchlisted' or 'ignored'
    4. Verify watchlist metadata populated
    5. Verify Neo4j node updated
    6. Manual override: add/remove from watchlist
    7. Verify blacklist works
- [ ] **9.2** Create E2E test for full user workflow
  - File: `tests/e2e/test_epic3_watchlist_e2e.py`
  - Navigate to Config → Watchlist Criteria
  - Update criteria (e.g., min_winrate = 0.80)
  - Navigate to Explorer → Wallets
  - Verify Status column displays correct values
  - Filter by "Watchlisted"
  - Click wallet row
  - Verify sidebar shows watchlist metadata
  - Manual override: remove from watchlist
  - Verify Status updated in table
- [ ] **9.3** Verify Epic 4 filtering pattern
  - File: `tests/integration/test_watchlist_clustering_filter.py`
  - Create 100 wallets (50 watchlisted, 50 ignored)
  - Run clustering query with `WHERE wallet_status = 'watchlisted'`
  - Verify only 50 wallets processed
  - Measure query time vs no filter
  - Document performance gain (expected 20-100x)
- [ ] **9.4** Run full test suite
  - Unit tests: `uv run pytest tests/unit -v`
  - Integration tests: `uv run pytest tests/integration -v`
  - E2E tests: `uv run pytest tests/e2e -v` (separately)
  - Expected total: ~340-360 tests (40-50 new for Story 3.5)
- [ ] **9.5** Update sprint-status.yaml
  - Mark Story 3.5 as `done`
  - Update Epic 3 progress (100% complete)
  - Update test count

---

## Dev Notes

### Architecture Pattern: Status-Based Filtering

**Core Principle:** Expensive operations (clustering, decay detection, signal scoring) filter on `wallet_status = 'watchlisted'` to achieve 20-100x performance gain.

**Status Lifecycle:**

```
discovered → profiled → watchlisted/ignored → flagged → removed/blacklisted
     ↓           ↓              ↓                ↓
  (Story 3.1)  (Story 3.3)  (Story 3.5)    (Story 3.4)
```

**Worker Pattern Example:**

```python
# Clustering Worker (Epic 4)
async def run_clustering_job():
    """Worker qui clustérise uniquement les wallets watchlistés."""
    wallets = await wallet_repo.get_all(
        where={'wallet_status': 'watchlisted'}
    )
    for wallet in wallets:
        await cluster_service.analyze_relationships(wallet.id)

# Decay Detection Worker (Story 3.4)
async def run_decay_detection_job():
    """Worker qui surveille uniquement les wallets watchlistés."""
    wallets = await wallet_repo.get_all(
        where={'wallet_status': 'watchlisted'}
    )
    for wallet in wallets:
        decay_score = await calculate_decay_score(wallet.id)
        if decay_score > threshold:
            wallet.wallet_status = 'flagged'
            await wallet_repo.update(wallet)
```

**Performance Impact:**

| Operation | Without Filter | With Filter | Gain |
|-----------|----------------|-------------|------|
| Clustering | 10,000 wallets | 500 wallets | 20x |
| Decay Detection | 10,000 wallets | 500 wallets | 20x |
| Signal Scoring | 10,000 wallets | 100 wallets | 100x |

**Assumptions:**
- Total wallets: ~10,000 (discovered from tokens)
- Profiled wallets: ~5,000 (50% pass profiling)
- Watchlisted wallets: ~500 (10% pass watchlist criteria)
- High-quality wallets for signals: ~100 (1% of total)

### Watchlist Score Calculation

**Weighted Formula:**

```python
def calculate_watchlist_score(wallet: Wallet, criteria: dict) -> float:
    """Calculate composite watchlist score (0.0-1.0)."""
    # Normalize each component (0.0-1.0)
    win_rate_component = min(wallet.win_rate / criteria['min_winrate'], 1.0)
    pnl_component = min(wallet.pnl_total / criteria['min_pnl'], 1.0)
    trades_component = min(wallet.total_trades / criteria['min_trades'], 1.0)
    decay_component = 1.0 - (wallet.decay_score / criteria['max_decay_score']) if wallet.decay_score else 1.0

    # Apply weights (must sum to 1.0)
    score = (
        win_rate_component * 0.40 +  # 40% weight
        pnl_component * 0.30 +        # 30% weight
        trades_component * 0.20 +     # 20% weight
        decay_component * 0.10        # 10% weight
    )

    return round(score, 4)  # 4 decimal places
```

**Example:**
- Wallet: win_rate=0.75, pnl_total=10.0 SOL, total_trades=20, decay_score=0.2
- Criteria: min_winrate=0.70, min_pnl=5.0, min_trades=10, max_decay_score=0.3

Components:
- win_rate: 0.75 / 0.70 = 1.071 → capped at 1.0
- pnl: 10.0 / 5.0 = 2.0 → capped at 1.0
- trades: 20 / 10 = 2.0 → capped at 1.0
- decay: 1 - (0.2 / 0.3) = 0.333

Score = (1.0 × 0.40) + (1.0 × 0.30) + (1.0 × 0.20) + (0.333 × 0.10) = 0.9333

**Decision:** All criteria met → status='watchlisted', score=0.9333

### Database Schema

**wallets table extensions:**

```sql
-- Migration: 004_wallets_watchlist_status.sql
ALTER TABLE walltrack.wallets
  ADD COLUMN IF NOT EXISTS wallet_status TEXT NOT NULL DEFAULT 'discovered'
  CHECK (wallet_status IN ('discovered', 'profiled', 'ignored', 'watchlisted', 'flagged', 'removed', 'blacklisted'));

ALTER TABLE walltrack.wallets ADD COLUMN IF NOT EXISTS watchlist_added_date TIMESTAMPTZ;
ALTER TABLE walltrack.wallets ADD COLUMN IF NOT EXISTS watchlist_score NUMERIC(5,4);
ALTER TABLE walltrack.wallets ADD COLUMN IF NOT EXISTS watchlist_reason TEXT;
ALTER TABLE walltrack.wallets ADD COLUMN IF NOT EXISTS manual_override BOOLEAN DEFAULT FALSE;

CREATE INDEX idx_wallets_status ON walltrack.wallets(wallet_status);
CREATE INDEX idx_wallets_watchlist_score ON walltrack.wallets(watchlist_score DESC) WHERE wallet_status = 'watchlisted';

-- Update existing wallets to 'profiled' status
UPDATE walltrack.wallets SET wallet_status = 'profiled' WHERE wallet_status IS NULL;
```

**config table entries:**

```sql
-- Migration: 004b_config_watchlist_criteria.sql
INSERT INTO walltrack.config (category, key, value, description) VALUES
('watchlist', 'min_winrate', '0.70', 'Minimum win rate to qualify for watchlist (0.0-1.0)'),
('watchlist', 'min_pnl', '5.0', 'Minimum total PnL in SOL to qualify for watchlist'),
('watchlist', 'min_trades', '10', 'Minimum number of trades to qualify for watchlist'),
('watchlist', 'max_decay_score', '0.3', 'Maximum decay score to qualify for watchlist (0.0-1.0)');
```

### WalletStatus Enum

```python
# src/walltrack/data/models/wallet.py

from enum import Enum

class WalletStatus(str, Enum):
    DISCOVERED = "discovered"      # Story 3.1: Just discovered from token
    PROFILED = "profiled"          # Story 3.2-3.3: Metrics calculated
    IGNORED = "ignored"            # Story 3.5: Failed watchlist criteria
    WATCHLISTED = "watchlisted"    # Story 3.5: Passed watchlist criteria
    FLAGGED = "flagged"            # Story 3.4: Decay detected
    REMOVED = "removed"            # Manual: Removed from system
    BLACKLISTED = "blacklisted"    # Manual: Permanently excluded
```

### Configuration Caching

**Problem:** Fetching config on every evaluation is slow (N database queries for N wallets).

**Solution:** Cache config for 5 minutes:

```python
# src/walltrack/data/supabase/repositories/config_repo.py

from functools import lru_cache
from datetime import datetime, timedelta

class ConfigRepository:
    _cache: dict[str, tuple[dict, datetime]] = {}

    async def get_watchlist_criteria(self) -> dict[str, float]:
        """Fetch watchlist criteria with 5-minute cache."""
        cache_key = "watchlist_criteria"

        # Check cache
        if cache_key in self._cache:
            data, timestamp = self._cache[cache_key]
            if datetime.utcnow() - timestamp < timedelta(minutes=5):
                return data

        # Fetch from database
        config = await self.get_by_category("watchlist")
        criteria = {
            "min_winrate": float(config["min_winrate"]),
            "min_pnl": float(config["min_pnl"]),
            "min_trades": int(config["min_trades"]),
            "max_decay_score": float(config["max_decay_score"]),
        }

        # Update cache
        self._cache[cache_key] = (criteria, datetime.utcnow())
        return criteria

    def clear_cache(self):
        """Clear cache when config updated."""
        self._cache.clear()
```

### Testing Strategy

**Unit Tests (~25-30 tests):**
- WatchlistEvaluator (8 tests)
- WalletRepository extensions (6 tests)
- ConfigRepository caching (3 tests)
- UI formatters (5 tests)
- Score calculation (5 tests)

**Integration Tests (~10-12 tests):**
- Full evaluation flow (3 tests)
- Automatic trigger from profiling (2 tests)
- Manual overrides (3 tests)
- Database sync (Supabase + Neo4j) (2 tests)
- Clustering filter performance (2 tests)

**E2E Tests (~8-10 tests):**
- Config page criteria update (2 tests)
- Explorer table status display (2 tests)
- Status filter functionality (2 tests)
- Manual controls (3 tests)
- Full workflow (1 test)

**Expected Total:** ~340-360 tests (40-50 new for Story 3.5)

### Gradio UI Patterns

**Status Column with Emoji Indicators:**

```python
def format_status(status: str) -> str:
    """Format wallet status with emoji indicator."""
    emoji_map = {
        "watchlisted": "🟢",
        "profiled": "⚪",
        "ignored": "🔴",
        "blacklisted": "⚫",
        "flagged": "🟡",
        "removed": "🟤",
        "discovered": "🔵"
    }
    emoji = emoji_map.get(status, "⚪")
    return f"{emoji} {status.capitalize()}"
```

**Filter Dropdown Implementation:**

```python
with gr.Accordion("Wallets", open=True):
    status_filter = gr.Dropdown(
        choices=["All", "Watchlisted", "Profiled", "Ignored", "Blacklisted"],
        value="All",
        label="Filter by Status"
    )

    wallets_table = gr.Dataframe(
        headers=["Address", "Status", "Watchlist Score", "Win Rate", "Decay Status", "Signals", "Cluster"],
        interactive=False
    )

    # Event handler
    status_filter.change(
        fn=get_wallets_table_data,
        inputs=[status_filter],
        outputs=[wallets_table]
    )
```

**Manual Control Buttons:**

```python
with gr.Column(visible=False) as sidebar:
    gr.Markdown("### Wallet Actions")

    add_to_watchlist_btn = gr.Button("Add to Watchlist", visible=True)
    remove_from_watchlist_btn = gr.Button("Remove from Watchlist", visible=False)
    blacklist_btn = gr.Button("Blacklist Wallet", variant="stop")

    action_status = gr.Textbox(label="Status", interactive=False)

    # Event handlers
    add_to_watchlist_btn.click(
        fn=add_to_watchlist,
        inputs=[wallet_address_state],
        outputs=[action_status, wallets_table, sidebar]
    )
```

### Error Handling

**Evaluation Errors:**
- Missing profiling metrics: Skip wallet, log warning
- Invalid criteria: Use defaults, log error
- Database error during update: Raise exception (critical)

**Manual Override Errors:**
- Wallet not found: Display error message "Wallet not found"
- Invalid status transition: Display error "Cannot perform action"
- Database error: Display error "Failed to update wallet"

**Config Update Errors:**
- Invalid value (e.g., min_winrate > 1.0): Display validation error
- Database error: Display error "Failed to update config"

### Patterns from Previous Stories

✅ **Config UI Pattern** (Epic 2 Story 2.2)
- Accordion section with input fields
- Save button with async handler
- Status message display

✅ **Status Filter** (Epic 2 Story 2.3)
- Dropdown with choices
- Change event triggers table refresh
- Filters data fetcher query

✅ **Repository Extensions** (Stories 3.1, 3.2)
- Add methods to existing repository
- Follow async pattern
- Error handling with custom exceptions

✅ **Database Migrations** (All stories)
- Sequential numbering (004, 004b)
- Include rollback comments
- Verify execution with `\d table_name`

### Dependencies

**Prerequisites:**
- ✅ Story 3.1 completed (wallets exist)
- ✅ Story 3.2 completed (performance metrics calculated)
- ✅ Story 3.3 completed (behavioral profiling done)
- ✅ Config table exists (Epic 2)

**External Dependencies:**
- None (all internal logic)

**New Components:**
- WatchlistEvaluator
- WalletStatus enum
- Config caching logic
- Manual override handlers

### Performance Considerations

**Batch Evaluation:**

For initial watchlist population (5,000 wallets):
- Fetch criteria once (cached)
- Process in batches of 100 (avoid memory issues)
- Use asyncio.gather() for parallel updates
- Expected time: ~30-60 seconds

**Incremental Evaluation:**

For new wallets (triggered by profiling):
- Single wallet evaluation: <100ms
- No batch processing needed
- Real-time updates

**Query Optimization:**

Clustering query before filtering:
```sql
SELECT * FROM walltrack.wallets;  -- 10,000 rows
```

Clustering query with filtering:
```sql
SELECT * FROM walltrack.wallets WHERE wallet_status = 'watchlisted';  -- 500 rows
```

Performance gain: **20x faster** (10,000 → 500 rows)

### Integration Points

**Story 3.3 (Behavioral Profiling) Integration:**

```python
# src/walltrack/core/wallets/behavioral_profiler.py

async def analyze_wallet_behavior(wallet_address: str):
    """Analyze wallet behavior and trigger watchlist evaluation."""
    # 1. Calculate behavioral metrics (existing logic)
    metrics = await calculate_behavioral_metrics(wallet_address)

    # 2. Update wallet with metrics
    await wallet_repo.update_behavioral_metrics(wallet_address, metrics)

    # 3. Update status to 'profiled'
    await wallet_repo.update(wallet_address, {"wallet_status": "profiled"})

    # 4. TRIGGER WATCHLIST EVALUATION (NEW)
    wallet = await wallet_repo.get_by_address(wallet_address)
    decision = await watchlist_evaluator.evaluate_wallet(wallet)
    await wallet_repo.update_watchlist_status(wallet_address, decision)

    log.info("wallet_profiled_and_evaluated",
             wallet_address=wallet_address,
             status=decision.status,
             score=decision.score)
```

**Epic 4 (Clustering) Integration:**

```python
# src/walltrack/core/cluster/clustering_service.py

async def run_clustering():
    """Cluster wallets - ONLY watchlisted wallets."""
    # FILTER: wallet_status = 'watchlisted'
    wallets = await wallet_repo.get_wallets_by_status(WalletStatus.WATCHLISTED)

    log.info("clustering_started", wallet_count=len(wallets))

    for wallet in wallets:
        await analyze_wallet_relationships(wallet.wallet_address)

    log.info("clustering_completed", wallet_count=len(wallets))
```

---

## Acceptance Criteria Checklist

- [ ] AC1: Wallet status lifecycle works (discovered → profiled → watchlisted/ignored)
- [ ] AC2: Configuration-driven criteria (min_winrate, min_pnl, min_trades, max_decay_score)
- [ ] AC3: Automatic evaluation trigger from Story 3.3 profiling
- [ ] AC4: Manual override capabilities (add/remove/blacklist)
- [ ] AC5: UI displays watchlist status with filters and scores
- [ ] AC6: Performance filtering pattern documented for Epic 4

---

## Definition of Done

- [ ] All tasks completed
- [ ] All acceptance criteria met
- [ ] Unit tests passing (~25-30 new tests)
- [ ] Integration tests passing (~10-12 new tests)
- [ ] E2E tests passing (~8-10 new tests)
- [ ] Database migrations executed (004, 004b)
- [ ] Code review completed
- [ ] Documentation updated (this file)
- [ ] No regressions in existing tests
- [ ] Story marked as `done` in sprint-status.yaml
- [ ] Epic 3 marked as 100% complete

---

## References

**Story Context:**
- **Epic:** docs/epics.md - Epic 3, Story 3.5
- **PRD:** docs/prd.md - FR10-FR16 (lines 337-343)
- **Architecture:** docs/architecture.md - Watchlist Management & Worker Pattern
- **Sprint Change Proposal:** docs/sprint-artifacts/sprint-change-proposal-watchlist.md

**Previous Stories:**
- **Story 3.1:** Wallet Discovery - Created wallets table
- **Story 3.2:** Wallet Performance Analysis - Calculated win_rate, pnl_total
- **Story 3.3:** Wallet Behavioral Profiling - Calculated behavioral metrics
- **Story 2.2:** Config Management - Established config table pattern

**Technical References:**
- Supabase PostgreSQL CHECK constraints
- Gradio dropdown and filter patterns
- Pydantic Enum validation
- asyncio batch processing

---

**Estimated Test Count:** ~340-360 total tests (40-50 new for Story 3.5)

**Dependencies:**
- Story 3.1, 3.2, 3.3 must be completed first
- Config table from Epic 2 required

**Next Steps After Story 3.5:**
- Epic 3 is complete (100%)
- Epic 4 (Cluster Analysis) begins, using `WHERE wallet_status = 'watchlisted'` pattern
- Story 3.4 (Decay Detection) updated to filter watchlisted wallets only

---

_Story context created by SM Agent (Bob) - 2025-12-30_
_Status: ready-for-dev_
