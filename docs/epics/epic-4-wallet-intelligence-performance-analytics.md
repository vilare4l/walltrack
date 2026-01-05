# Epic 4: Wallet Intelligence & Performance Analytics

Operator can monitor source wallet activity for mirror-exit triggers, track performance per wallet (win rate, PnL, signal counts all/30d/7d/24h), and make data-driven curation decisions (remove underperformers, promote high-performers to live mode).

### Story 4.1: Source Wallet Sell Detection for Mirror-Exit

As an operator,
I want to detect when source wallets sell tokens I'm holding,
So that I can automatically exit positions via mirror-exit strategy.

**Acceptance Criteria:**

**Given** Helius webhook is monitoring all active wallets (configured in Epic 2)
**When** a monitored wallet executes a SELL transaction (swap from token to SOL/USDC)
**Then** the webhook handler receives the transaction with: wallet address, token_mint (input token being sold), amount, timestamp, signature

**Given** a source wallet sell signal is received
**When** the signal processing pipeline executes
**Then** the system queries the `positions` table for open positions matching: source_wallet_id = wallet AND token_id = sold_token AND status='open'
**And** if matching positions exist, the system checks each position's exit strategy for mirror_exit_enabled=true

**Given** a matching position has mirror-exit enabled
**When** the mirror-exit logic evaluates the position
**Then** the system triggers a 100% exit with exit_reason='mirror_exit'
**And** mirror-exit takes priority over trailing-stop and scaling-out strategies (but NOT over stop-loss - capital protection has highest priority)
**And** an exit order is created in the `orders` table with type='exit', amount_tokens=remaining_amount_tokens, price_usd (current market price), status='pending', retry_count=0

**Given** mirror-exit is triggered for a live position
**When** the exit order is processed
**Then** a Jupiter API swap is executed immediately: input_mint=token_mint, output_mint=SOL/USDC, amount=remaining_amount_tokens
**And** if Jupiter API succeeds, the order status is updated to 'filled', tx_signature is stored, slippage_percent is calculated and stored
**And** the position is closed with status='closed', closed_at=NOW(), exit_reason='mirror_exit', realized_pnl_usd=(exit_price - entry_price) * amount_tokens
**And** the exit is logged with structured logging (level: INFO, event: mirror_exit_triggered, source_wallet: address, token: mint, tx_signature: value)

**Given** a Jupiter API call fails during mirror-exit execution
**When** the exit order worker encounters the error
**Then** the worker retries the API call up to 3 times with exponential backoff (5s, 15s, 30s)
**And** the order's retry_count is incremented with each attempt
**And** if all retries fail, the order status is set to 'failed', last_error is stored
**And** the position remains 'open' (exit did not complete)
**And** the failure is logged with structured logging (level: ERROR, event: mirror_exit_failed, position_id: value, error: message)

**Given** mirror-exit is triggered for a simulation position
**When** the exit order is processed
**Then** the order is marked as 'simulated' (no API call)
**And** the position is closed with the simulated exit price (current market price at time of trigger)

**Given** I am viewing the Dashboard sidebar for a closed position
**When** the position was closed via mirror-exit
**Then** the sidebar displays: Exit Reason="Mirror-Exit (Source wallet sold)", Exit Price, Exit Date
**And** I can see the source wallet's sell transaction signature in the transaction history

**Given** multiple positions match a source wallet sell signal
**When** the mirror-exit logic processes all matching positions
**Then** all positions with mirror_exit_enabled=true are closed simultaneously
**And** each exit is logged independently
**And** if any exit fails (Jupiter API error), it is retried independently without affecting other exits

### Story 4.2: Performance Metrics Calculation - Win Rate, PnL, Signal Counts

As an operator,
I want to track win rate, PnL, and signal counts per wallet,
So that I can evaluate which wallets generate profitable signals.

**Acceptance Criteria:**

**Given** Epic 4 Story 4.2 is being implemented
**When** the performance tracking feature is initialized
**Then** the `performance` table is created in the database with schema: wallet_id (FK to wallets), win_rate_percent (DECIMAL), total_pnl_usd (DECIMAL), total_trades (INTEGER), signals_all (INTEGER), signals_30d (INTEGER), signals_7d (INTEGER), signals_24h (INTEGER), last_updated_at (TIMESTAMP)
**And** the table has COMMENT ON TABLE documenting its architectural pattern (Materialized View for pre-calculated metrics)
**And** all necessary indexes are created (wallet_id primary key, last_updated_at for refresh queries)

**Given** positions have been opened and closed for a wallet
**When** the performance calculation worker runs (triggered on position close or daily batch)
**Then** the worker queries all closed positions for the wallet from the `positions` table
**And** the worker calculates: total_trades = COUNT(closed positions), winning_trades = COUNT(positions WHERE realized_pnl_usd > 0), win_rate = (winning_trades / total_trades) * 100

**Given** the win rate calculation is complete
**When** the worker updates the `performance` table
**Then** the worker inserts or updates the record for the wallet with: wallet_id (FK), win_rate_percent (calculated), last_updated_at=NOW()

**Given** positions have PnL data
**When** the performance calculation worker aggregates PnL
**Then** the worker calculates: total_pnl_usd = SUM(realized_pnl_usd) for all closed positions
**And** the worker updates the `performance` table with: total_pnl_usd (aggregated value)

**Given** signals have been received for a wallet
**When** the performance calculation worker counts signals
**Then** the worker queries the `signals` table for all signals WHERE source_wallet_id = wallet
**And** the worker calculates signal counts with time windows:
- signals_all = COUNT(all signals)
- signals_30d = COUNT(signals WHERE detected_at >= NOW() - INTERVAL '30 days')
- signals_7d = COUNT(signals WHERE detected_at >= NOW() - INTERVAL '7 days')
- signals_24h = COUNT(signals WHERE detected_at >= NOW() - INTERVAL '24 hours')
**And** the worker updates the `performance` table with all signal count fields

**Given** I am viewing the Watchlist tab
**When** the wallets table loads
**Then** the table displays performance metrics for each wallet: Win Rate (e.g., "68.5%"), PnL (e.g., "+$1,250.00" in green), Signals (e.g., "127 signals")
**And** the metrics update after each position close (near real-time) or at least daily

**Given** I click on a wallet row in the Watchlist tab
**When** the wallet sidebar opens
**Then** the sidebar displays detailed performance breakdown:
- Current Performance: Win Rate, Total PnL, Total Trades
- Signal Counts: All-time, 30d, 7d, 24h
- Comparison: Initial metrics (from discovery) vs Current metrics

### Story 4.3: Performance Materialized View - Daily Batch Refresh

As an operator,
I want performance metrics to be pre-calculated daily for fast dashboard loading,
So that I can view analytics without waiting for real-time calculations.

**Acceptance Criteria:**

**Given** the system has accumulated position and signal data
**When** the daily batch refresh worker runs (scheduled at 00:00 UTC)
**Then** the worker recalculates ALL performance metrics for ALL wallets from scratch
**And** the worker uses the same logic as Story 4.2 (win rate, PnL, signal counts)
**And** the worker updates the `performance` table with refreshed data for all wallets
**And** the refresh is logged with structured logging (level: INFO, event: performance_refresh_complete, wallets_updated: count, duration_ms: value)

**Given** the batch refresh is running
**When** individual position closes occur during the refresh
**Then** the real-time update logic (from Story 4.2) is temporarily suspended
**And** the batch refresh completes without conflicts (uses transaction isolation or locking)
**And** after batch completion, real-time updates resume for new position closes

**Given** the batch refresh completes
**When** I view the Watchlist tab or Dashboard tab
**Then** all performance metrics reflect the refreshed data (up to midnight UTC)
**And** the Dashboard loads in <2 seconds (NFR-1: performance target)

**Given** the batch refresh fails (database error, timeout)
**When** the worker encounters the error
**Then** the error is logged with structured logging (level: ERROR, event: performance_refresh_failed, error: message)
**And** the worker retries the refresh after 1 hour
**And** the previous day's performance data remains visible (stale but available)

**Given** I want to manually trigger a performance refresh (for testing or debugging)
**When** I access the Config tab (future enhancement: manual refresh button)
**Then** a [Refresh Performance] button is available
**And** clicking it triggers an immediate batch refresh
**And** a progress indicator shows the refresh status

### Story 4.4: Wallet Promotion & Demotion - Mode Switching

As an operator,
I want to promote high-performing simulation wallets to live mode and demote underperformers,
So that I can gradually scale my capital to proven winners.

**Acceptance Criteria:**

**Given** I am viewing the Watchlist tab wallet sidebar
**When** I click on a wallet row for a simulation wallet
**Then** the sidebar displays a [Promote to Live] button
**And** the button is enabled if the wallet has sufficient track record (e.g., ≥10 closed trades, win_rate ≥ 60%)

**Given** I click the [Promote to Live] button
**When** the promotion action executes
**Then** a confirmation dialog appears: "Promote [Wallet Label] to Live mode? Future positions will execute real trades."
**And** the dialog has [Confirm] and [Cancel] buttons

**Given** I confirm the promotion
**When** the update executes
**Then** the wallet's mode is updated in the `wallets` table: mode='live'
**And** the wallets table refreshes showing the updated mode (🟠 Amber badge)
**And** a success message displays: "Wallet promoted to Live mode"
**And** the promotion is logged with structured logging (level: INFO, event: wallet_promoted, wallet_id: value)

**Given** I am viewing a live wallet in the sidebar
**When** the wallet is underperforming (e.g., win_rate < 50% after 20 trades)
**Then** the sidebar displays a [Demote to Simulation] button
**And** the button is always enabled (operator can demote at any time)

**Given** I click the [Demote to Simulation] button and confirm
**When** the demotion executes
**Then** the wallet's mode is updated: mode='simulation'
**And** the wallets table refreshes showing the updated mode (🔵 Blue badge)
**And** a success message displays: "Wallet demoted to Simulation mode"
**And** the demotion is logged with structured logging (level: INFO, event: wallet_demoted, wallet_id: value)

**Given** a wallet's mode is changed (promotion or demotion)
**When** new signals are received for that wallet
**Then** new positions are created in the updated mode (simulation or live)
**And** existing open positions remain in their original mode (no retroactive changes)

**Given** I have multiple wallets with different performance levels
**When** I view the Watchlist tab
**Then** I can sort by Win Rate or PnL to identify top performers and underperformers
**And** the sidebar provides clear action buttons based on current mode and performance

### Story 4.5: Fake Wallet Detection & Curation Insights

As an operator,
I want to detect fake wallets (wash trading) by comparing initial vs actual performance,
So that I can remove wallets that were inflated during discovery.

**Acceptance Criteria:**

**Given** a wallet was added with initial discovery metrics (initial_win_rate_percent, initial_trades_observed, initial_pnl_usd)
**When** the wallet has 30+ days of tracked activity (created_at ≥ NOW() - INTERVAL '30 days')
**Then** the performance analysis worker compares: initial_win_rate_percent vs performance.win_rate_percent

**Given** the performance comparison reveals significant degradation
**When** the worker detects: (initial_win_rate - current_win_rate) ≥ 20% (e.g., 80% initial → 55% current)
**Then** the wallet is flagged as "potential fake" in the wallet sidebar
**And** a warning indicator displays in the Watchlist table (e.g., ⚠️ icon next to wallet label)

**Given** I am viewing a flagged wallet in the sidebar
**When** the sidebar loads
**Then** the sidebar displays: Warning="Significant performance drop detected. Initial: 80%, Current: 55%"
**And** the sidebar shows: Comparison table (Initial Metrics vs Current Metrics)
**And** the sidebar provides a [Remove Wallet] button for easy curation

**Given** I want to audit all flagged wallets
**When** I view the Watchlist tab
**Then** I can filter by "Flagged Wallets" (if filter implemented) or sort by performance drop
**And** flagged wallets are visually distinct (warning icon, yellow highlight)

**Given** I decide to remove a flagged wallet
**When** I click [Remove Wallet] and confirm
**Then** the wallet is deleted from the `wallets` table (same logic as Story 2.1)
**And** all associated signals remain in the database (audit trail preserved)
**And** all closed positions remain in the database (historical PnL preserved)
**And** all open positions are closed immediately with exit_reason='wallet_removed' (cleanup)

**Given** fake wallet detection is active
**When** the performance refresh worker runs (daily batch)
**Then** the worker recalculates degradation for all wallets with ≥30 days history
**And** flagged wallets are updated in the database (flag stored in `wallets` table or derived on-demand)
**And** the detection is logged with structured logging (level: WARN, event: fake_wallet_detected, wallet_id: value, degradation_percent: value)
