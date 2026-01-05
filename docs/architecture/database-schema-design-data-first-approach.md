# Database Schema Design (Data-First Approach)

### Schema Overview

**Database:** PostgreSQL via Supabase (local instance)
**Schema:** `walltrack` (dedicated schema, not `public`)
**Approach:** Data-first - complete schema design upfront to minimize future migrations

### Entity Relationship Model

**Core Entities:**

1. **config** - System configuration (singleton)
2. **exit_strategies** - Reusable exit strategy templates
3. **wallets** - Watchlist wallets with mode (copy trading configuration)
4. **tokens** - Token metadata cache with safety analysis
5. **signals** - Raw signals from Helius webhooks (audit trail)
6. **orders** - Jupiter swap orders history (buy/sell transactions)
7. **positions** - Trading positions (open/closed) with PnL tracking
8. **performance** - Aggregated wallet performance metrics
9. **circuit_breaker_events** - Circuit breaker activation log

**Relationships:**
```
exit_strategies (1) → (N) wallets
wallets (1) → (N) signals
wallets (1) → (N) positions
wallets (1) → (N) orders
wallets (1) → (1) performance
tokens (1) → (N) signals
tokens (1) → (N) orders
positions (1) → (N) orders
signals (1) → (0-1) positions
orders (1) → (0-1) positions (entry/exit orders)
```

### Complete Table Definitions

**Note:** Full SQL schema is in migration files. This section provides architectural context and design decisions.

#### 1. config (System Configuration)

**📖 Design Guide:** [01-config.md](./database-design/01-config.md)
**🗄️ Migration SQL:** `001_config_table.sql`

**Purpose:** Global system configuration parameters (trading, risk, safety thresholds)

**Pattern:** Configuration Singleton - Only 1 row allowed (enforced by trigger)

**Key Field Groups:**
- **Trading Parameters**: capital, risk_per_trade_percent, position_sizing_mode
- **Risk Management**: stop_loss, trailing_stop, max_drawdown, circuit breaker thresholds
- **Safety Analysis**: token safety score threshold (default 0.60), liquidity/holder/age checks
- **Helius Webhook**: Global webhook config ([ADR-001](./database-design/README.md#adr-001) - ONE webhook for all wallets)
- **System Status**: circuit_breaker_active, webhook_last_signal_at

**Relations:** None (singleton, no FK)

#### 2. exit_strategies (Reusable Exit Strategy Templates)

**📖 Design Guide:** [02-exit-strategies.md](./database-design/02-exit-strategies.md)
**🗄️ Migration SQL:** `002_exit_strategies_table.sql`

**Purpose:** Catalog of reusable exit strategies (DRY pattern - avoid duplicating config across wallets)

**Pattern:** Catalog Pattern - Shared templates with 1:N relationship to wallets

**Key Field Groups:**
- **Stop Loss**: stop_loss_percent (e.g., 20% default)
- **Trailing Stop**: trailing_stop_enabled, trailing_stop_percent, activation_threshold
- **Scaling Out**: 3 levels (sell 50% at 2x, 25% at 3x, 25% ride forever)
- **Mirror Exit**: mirror_exit_enabled (exit when source wallet sells)
- **Usage**: is_default (UNIQUE constraint), is_active

**Key Decisions:**
- **NOT at wallet level**: Strategies are templates, overrides go in `positions.exit_strategy_override` ([ADR-002](./database-design/README.md#adr-002))
- **Default data**: 3 strategies pre-populated (Default, Conservative, Aggressive)

**Relations:**
- `1:N` → wallets (wallets.exit_strategy_id)
- `1:N` → positions (positions.exit_strategy_id)

#### 3. wallets (Watchlist / Copy Trading Configuration)

**📖 Design Guide:** [03-wallets.md](./database-design/03-wallets.md)
**🗄️ Migration SQL:** `003_wallets_table.sql`

**Purpose:** Registry of Solana wallets to monitor (copy-trading sources)

**Pattern:** Registry Pattern - Watchlist configuration with Helius sync tracking

**Key Field Groups:**
- **Identity**: address (Solana base58, 32-44 chars), label (human-readable)
- **Mode**: simulation | live (per-wallet toggle for progressive risk)
- **Exit Strategy**: exit_strategy_id (FK → exit_strategies, required)
- **Discovery Context**: discovery_source (twitter/telegram/scanner/manual), discovery_date, discovery_notes
- **Initial Performance**: initial_win_rate_percent, initial_trades_observed (validation before live mode)
- **Helius Sync**: helius_synced_at, helius_sync_status (pending/synced/error)
- **Status**: is_active (inactive wallets excluded from webhook sync)

**Key Decisions:**
- **ONE global Helius webhook** ([ADR-001](./database-design/README.md#adr-001)) - Batch sync every 5 min updates webhook with all active addresses
- **Strategy overrides at position level** ([ADR-002](./database-design/README.md#adr-002)) - NOT at wallet level, keeps wallet config simple
- **Address validation**: Solana base58 regex constraint (`^[1-9A-HJ-NP-Za-km-z]{32,44}$`)

**Relations:**
- `N:1` → exit_strategies (default strategy for this wallet)
- `1:N` → signals, positions, orders, performance

#### 4. tokens (Token Metadata Cache)

**📖 Design Guide:** [04-tokens.md](./database-design/04-tokens.md)
**🗄️ Migration SQL:** `004_tokens_table.sql`

**Purpose:** Cache token metadata and safety analysis (TTL 1h, avoid re-analyzing)

**Pattern:** Read-Through Cache - Fetch-on-miss, store results, respect TTL

**Key Field Groups:**
- **Identity**: address (unique), symbol, name
- **Safety Score**: safety_score (0.00-1.00), liquidity_usd, holder_distribution_top_10_percent, age_hours
- **Individual Checks**: liquidity_check_passed, holder_check_passed, contract_check_passed, age_check_passed
- **Cache Metadata**: last_analyzed_at (TTL 1h), analysis_source (rugcheck/dexscreener)
- **DEX Info**: dex_name, pair_address

**Key Decisions:**
- **TTL 1h**: Cache invalidation after 1h → re-analyze on next signal
- **Multi-source fallback**: RugCheck primary, DexScreener fallback
- **Safety booleans**: Individual checks stored for debugging/forensics

**Relations:**
- `1:N` → signals, positions, orders

#### 5. signals (Webhook Events Log)

**📖 Design Guide:** [05-signals.md](./database-design/05-signals.md)
**🗄️ Migration SQL:** `005_signals_table.sql`

**Purpose:** Immutable audit trail of all webhook events from Helius (BUY/SELL signals)

**Pattern:** Event Sourcing - Append-only log, never UPDATE, only INSERT

**Key Field Groups:**
- **Identity**: wallet_id (FK → wallets), token_address, transaction_signature (UNIQUE, idempotency)
- **Signal Type**: signal_type (BUY | SELL)
- **Transaction Details**: token_in, token_out, amount_in, amount_out, price
- **Processing**: filtered (boolean), filter_reason (safety_check_failed/circuit_breaker/duplicate)
- **Position Link**: position_created (boolean), position_id (FK → positions, NULL until created)
- **Webhook Metadata**: webhook_received_at, processed_at, processing_duration_ms
- **Raw Data**: raw_payload (JSONB, full Helius webhook for debugging)

**Key Decisions:**
- **Immutable**: Never UPDATE signals, only INSERT new ones
- **Idempotency**: transaction_signature UNIQUE prevents duplicates
- **Processing queue**: filtered=false AND position_created=false → ready for processing

**Relations:**
- `N:1` → wallets, tokens
- `1:0-1` → positions (signal may be filtered, no position created)

#### 6. orders (Jupiter Swap Orders History)

**📖 Design Guide:** [06-orders.md](./database-design/06-orders.md)
**🗄️ Migration SQL:** `006_orders_table.sql`

**Purpose:** Command log of all Jupiter swap orders (buy/sell transactions) with retry mechanism

**Pattern:** Command Log - Track requests/retries, execution details, slippage

**Key Field Groups:**
- **Identity**: wallet_id, token_id, position_id (FK → positions), signal_id
- **Order Type**: order_type (entry | exit_stop_loss | exit_trailing_stop | exit_scaling | exit_mirror | exit_manual)
- **Mode**: mode (simulation | live)
- **Swap Details**: token_in, token_out, amount_in, amount_out_expected, amount_out (actual)
- **Slippage**: slippage_requested_percent (default 3%), slippage_actual_percent (auto-calculated)
- **Status**: status (pending | submitted | executed | failed | cancelled)
- **Execution** (live only): jupiter_quote_id, tx_signature, block_number, priority_fee_lamports
- **Timing**: requested_at, submitted_at, executed_at, execution_duration_ms (auto-calculated trigger)
- **Retry**: retry_count (default 0), max_retries (default 3), error_code, error_message
- **Scaling Context**: scaling_level (1/2/3), scaling_percent

**Key Decisions:**
- **1 position → N orders**: Position can have multiple orders (entry + multiple exits for scaling)
- **Idempotency**: tx_signature for live orders (on-chain tx)
- **Retry logic**: Partial index `idx_orders_pending_retry` for worker queue
- **Auto-calculated fields**: execution_duration_ms via trigger

**Relations:**
- `N:1` → wallets, tokens, positions, signals

#### 7. positions (Trading Positions)

**📖 Design Guide:** [07-positions.md](./database-design/07-positions.md)
**🗄️ Migration SQL:** `007_positions_table.sql`

**Purpose:** Aggregate root tracking position lifecycle (entry → price updates → partial/full exits → PnL)

**Pattern:** Aggregate Root - Central entity for trading positions with PnL tracking (realized/unrealized separation)

**Key Field Groups:**
- **Identity**: wallet_id, token_id, signal_id, mode (simulation | live)
- **Entry**: entry_price, entry_amount, entry_value_usd, entry_timestamp, entry_tx_signature (live only)
- **Current State**: current_amount (decremented on partial exits), current_price, current_pnl_usd, peak_price (trailing stop)
- **PnL Breakdown**:
  - **unrealized_pnl_usd**: PnL of current_amount (still open)
  - **realized_pnl_usd**: PnL from exits already executed (accumulated from orders)
  - **current_pnl_usd**: Total = realized + unrealized
- **Exit**: exit_price (weighted avg), exit_amount (sum of exits), exit_reason (stop_loss/trailing_stop/scaling/mirror/manual)
- **Exit Strategy**: exit_strategy_id (FK → exit_strategies), exit_strategy_override (JSONB, [ADR-002](./database-design/README.md#adr-002))
- **Status**: status (open | closed | error)

**Key Decisions:**
- **Partial exits supported**: current_amount decremented, realized_pnl accumulated
- **Strategy override at position level** ([ADR-002](./database-design/README.md#adr-002)): `exit_strategy_override` JSONB merges with template
- **Partial index on open positions**: `WHERE status = 'open'` for price monitor worker

**Relations:**
- `N:1` → wallets, tokens, signals, exit_strategies
- `1:N` → orders (entry + multiple exit orders)

#### 8. performance (Aggregated Wallet Metrics)

**📖 Design Guide:** [08-performance.md](./database-design/08-performance.md)
**🗄️ Migration SQL:** `008_performance_table.sql`

**Purpose:** Pre-calculated wallet performance metrics (batch refresh daily at 00:00 UTC)

**Pattern:** Materialized View - Avoid expensive real-time aggregations, dashboard reads pre-calculated values

**Key Field Groups:**
- **Win Rate**: total_positions, winning_positions, losing_positions, win_rate (%)
- **PnL**: total_pnl_usd, total_pnl_percent, average_win_usd, average_loss_usd, profit_ratio (avg_win / avg_loss)
- **Rolling Windows**: signal_count_30d/7d/24h, positions_30d/7d/24h (recalculated daily)
- **Best/Worst**: best_trade_pnl_usd/percent, worst_trade_pnl_usd/percent
- **Streaks**: current_win_streak, current_loss_streak, max_win_streak, max_loss_streak
- **Metadata**: last_calculated_at (batch job timestamp)

**Key Decisions:**
- **Daily batch refresh** ([ADR-003](./database-design/README.md#adr-003)): Performance Aggregator Worker runs at 00:00 UTC
- **1:1 with wallets**: wallet_id UNIQUE constraint
- **Fast dashboard queries**: No JOINs, pre-calculated values

**Relations:**
- `1:1` → wallets (wallet_id UNIQUE)

#### 9. circuit_breaker_events (Circuit Breaker Log)

**📖 Design Guide:** [09-circuit-breaker-events.md](./database-design/09-circuit-breaker-events.md)
**🗄️ Migration SQL:** `009_circuit_breaker_events_table.sql`

**Purpose:** Immutable audit trail of circuit breaker activations/deactivations (compliance & forensics)

**Pattern:** Event Sourcing - Event pairs (activated → deactivated), snapshots of metrics/thresholds at trigger time

**Key Field Groups:**
- **Event**: event_type (activated | deactivated)
- **Trigger**: trigger_reason (max_drawdown | min_win_rate | consecutive_losses | manual)
- **Metrics Snapshot**: current_drawdown_percent, current_win_rate, consecutive_losses (at activation moment)
- **Thresholds Snapshot**: max_drawdown_threshold, min_win_rate_threshold, consecutive_loss_threshold (config at activation)
- **Impact**: new_positions_blocked (counter), open_positions_at_activation (snapshot)
- **Metadata**: created_at, deactivated_at (NULL if still active)

**Key Decisions:**
- **Circuit breaker does NOT close existing positions** ([ADR-004](./database-design/README.md#adr-004)): Blocks NEW positions only, existing continue exit strategies
- **Immutable events**: Never UPDATE, only INSERT pairs (activated → deactivated)
- **Snapshots for forensics**: Thresholds + metrics at trigger time (validate calibration)

### Data Retention Strategy

**Approach:** Keep all data in main tables with optimized indexes

**Design Decision:** No archive tables for MVP
- Simpler schema and maintenance
- Partial indexes on recent data for performance
- Can add partitioning later if needed

**Performance Optimization:**
```sql
-- Index for recent signals (last 90 days) - faster queries
CREATE INDEX idx_signals_recent ON walltrack.signals(created_at DESC)
    WHERE created_at > NOW() - INTERVAL '90 days';

-- Index for recent orders (last 90 days)
CREATE INDEX idx_orders_recent ON walltrack.orders(created_at DESC)
    WHERE created_at > NOW() - INTERVAL '90 days';

-- Index for recently closed positions (last 90 days)
CREATE INDEX idx_positions_recent_closed ON walltrack.positions(closed_at DESC)
    WHERE status = 'closed' AND closed_at > NOW() - INTERVAL '90 days';
```

**Future Migration Path (if performance degrades):**
- Option A: Add table partitioning (PostgreSQL 10+)
- Option B: Implement archive tables with monthly job
- Option C: Use TimescaleDB for time-series data

### Migration Files

**Location:** `src/walltrack/data/supabase/migrations/`

**Execution Order:**
1. `000_helper_functions.sql` - Schema + triggers (update_updated_at)
2. `001_config_table.sql` - System configuration (singleton)
3. `002_exit_strategies_table.sql` - Exit strategies catalog + default data
4. `003_wallets_table.sql` - Watchlist registry
5. `004_tokens_table.sql` - Token metadata cache
6. `005_signals_table.sql` - Webhook events log
7. `006_orders_table.sql` - Jupiter swap orders
8. `007_positions_table.sql` - Trading positions
9. `008_performance_table.sql` - Aggregated metrics
10. `009_circuit_breaker_events_table.sql` - Circuit breaker audit trail

**See also:** [Database Design Guides](./database-design/README.md) for rationale and patterns

### Key Design Decisions (Summary)

**Major Architecture Decision Records (ADRs):**
- **[ADR-001](./database-design/README.md#adr-001)**: Helius Global Webhook - ONE webhook for all wallets (not 1 per wallet)
- **[ADR-002](./database-design/README.md#adr-002)**: Exit Strategy Override at Position Level (not wallet level)
- **[ADR-003](./database-design/README.md#adr-003)**: Performance Materialized View (batch refresh daily at 00:00 UTC)
- **[ADR-004](./database-design/README.md#adr-004)**: Circuit Breaker Non-Closing (blocks NEW positions, existing continue)

**Design Patterns Applied:**
1. **Configuration Singleton** (config) - 1 row max, trigger enforcement
2. **Catalog Pattern** (exit_strategies) - Reusable templates, DRY
3. **Registry Pattern** (wallets) - Watchlist configuration
4. **Read-Through Cache** (tokens) - TTL 1h, fetch-on-miss
5. **Event Sourcing** (signals, circuit_breaker_events) - Immutable append-only logs
6. **Command Log** (orders) - Retry mechanism, execution tracking
7. **Aggregate Root** (positions) - PnL tracking, realized/unrealized separation
8. **Materialized View** (performance) - Pre-calculated metrics, batch refresh

**Technical Decisions:**
- **Separation of concerns**: orders (transactions) vs positions (high-level trades)
- **Partial indexes**: `WHERE status = 'open'` for performance (price monitor queries)
- **Timestamps everywhere**: `created_at`, `updated_at` (auto-updated via triggers)
- **UUIDs as PKs**: Distributed-friendly, no auto-increment conflicts
- **CHECK constraints**: Enforce enums at DB level (mode, status, order_type)
- **Cascade deletes**: Delete wallet → cascade delete signals, positions, performance (referential integrity)
