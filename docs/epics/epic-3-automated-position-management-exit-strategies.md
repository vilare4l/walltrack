# Epic 3: Automated Position Management & Exit Strategies

Operator can automatically create positions from safe signals (dual-mode: simulation + live), monitor prices in real-time via Jupiter Price API V3 and DexScreener fallback, and execute sophisticated exit strategies (stop-loss, trailing-stop, scaling-out) without manual trading.

### Story 3.1: Position Creation from Safe Signals - Dual-Mode Execution

As an operator,
I want positions to be automatically created from safe signals in both simulation and live modes,
So that I can validate strategies in simulation before risking real capital.

**Acceptance Criteria:**

**Given** a signal has passed safety filtering (filtered=false) and the source wallet is active
**When** the position creation pipeline processes the signal
**Then** the system checks the source wallet's mode (simulation/live) from the `wallets` table
**And** the system retrieves the default exit strategy for the wallet from the `exit_strategies` table (via `wallets.default_exit_strategy_id`)
**And** the system calculates the position size: (config.max_capital_per_trade_percent / 100) * config.total_capital_usd

**Given** the source wallet is in simulation mode
**When** a position is created
**Then** a new record is inserted into the `positions` table with: token_id (FK to tokens), source_wallet_id (FK to wallets), entry_price_usd (from signal), amount_tokens (calculated), mode='simulation', status='open', opened_at=NOW(), exit_strategy_override=NULL (uses default)
**And** NO Jupiter API call is made (simulation mode = no real trades)
**And** a new record is inserted into the `orders` table with: position_id (FK), type='entry', status='simulated', amount_tokens (same as position), price_usd (entry price), executed_at=NOW()
**And** the position creation is logged with structured logging (level: INFO, event: position_created, mode: simulation)

**Given** the source wallet is in live mode
**When** a position is created
**Then** a Jupiter API swap call is executed: input_mint=SOL/USDC, output_mint=token_mint, amount=position_size_usd
**And** if the Jupiter API call succeeds, a new record is inserted into the `positions` table with mode='live', status='open'
**And** a new record is inserted into the `orders` table with type='entry', status='filled', tx_signature (from Jupiter response)
**And** the position creation is logged with structured logging (level: INFO, event: position_created, mode: live, tx_signature: value)

**Given** the Jupiter API call fails (timeout, slippage too high, network error)
**When** the position creation worker encounters the error
**Then** the system retries the Jupiter API call up to 3 times with exponential backoff (5s, 15s, 30s)
**And** if all retries fail, a new record is inserted into the `orders` table with type='entry', status='failed', last_error (error message), retry_count=3
**And** NO position is created in the `positions` table
**And** the failure is logged with structured logging (level: ERROR, event: position_creation_failed, mode: live, error: message)

**Given** positions are being created from signals
**When** I view the Dashboard tab Active Positions table
**Then** new positions appear in the table within <5 seconds of signal receipt (NFR-1: P95 latency)
**And** simulation positions display with 🔵 Blue mode badge
**And** live positions display with 🟠 Amber mode badge
**And** I can see: Token symbol, Entry price, Current price (placeholder until price monitoring), PnL (initially $0.00), Status (Open)

**Given** the system is creating multiple positions concurrently (burst of 10 signals within 30s)
**When** the position creation pipeline processes the queue
**Then** all positions are created sequentially (to avoid race conditions on config/wallet data)
**And** the total processing time is <30 seconds for 10 positions (NFR-7: scalability)
**And** each position creation is logged independently

### Story 3.2: Real-Time Price Monitoring - Jupiter & DexScreener Fallback

As an operator,
I want token prices for active positions to be monitored continuously,
So that exit strategies can be triggered based on current market conditions.

**Acceptance Criteria:**

**Given** the system has active positions (status='open') in the `positions` table
**When** the price monitoring worker starts
**Then** the worker queries the `positions` table for all open positions
**And** the worker extracts unique token_ids to create a polling list
**And** the worker schedules polling at 30-60 second intervals for each token

**Given** a token requires price polling
**When** the price monitoring worker executes for that token
**Then** the worker calls Jupiter Price API V3 with token_mint address
**And** if Jupiter returns a valid price, the price is stored temporarily in memory (cache)
**And** the worker updates all positions for that token with current_price_usd (calculated field or cached value)
**And** the price fetch is logged with structured logging (level: DEBUG, event: price_fetched, source: jupiter, price: value)

**Given** Jupiter Price API V3 fails or returns an error
**When** the price monitoring worker detects the failure
**Then** the worker immediately falls back to DexScreener API
**And** the worker calls DexScreener API with token_mint address
**And** if DexScreener returns a valid price, the price is used and logged (level: WARN, event: price_fallback, source: dexscreener)
**And** if DexScreener also fails, the worker logs the error (level: ERROR, event: price_fetch_failed, token: mint) and retries after 60 seconds

**Given** price monitoring is active for all open positions
**When** I view the Dashboard tab Active Positions table
**Then** the "Current" column updates every 30-60 seconds with the latest fetched price
**And** the "PnL" column recalculates automatically: (current_price - entry_price) * amount_tokens
**And** PnL values are color-coded: Green for profit, Red for loss

**Given** a position's current price changes
**When** the price update triggers exit strategy evaluation
**Then** the worker checks all configured exit strategies for that position (stop-loss, trailing-stop, scaling-out)
**And** if any exit condition is met, the exit execution pipeline is triggered (implemented in later stories)

**Given** the price monitoring worker is running
**When** a position is closed (status='closed')
**Then** the worker removes that position from the polling list
**And** no further price fetches occur for that token (unless other positions remain open)

### Story 3.3: Stop-Loss & Trailing-Stop Exit Strategies

As an operator,
I want stop-loss and trailing-stop strategies to protect my capital and lock in profits,
So that I minimize losses and capture gains automatically.

**Acceptance Criteria:**

**Given** a position is open and price monitoring is active
**When** the exit strategy evaluation worker checks stop-loss conditions
**Then** the worker retrieves the stop-loss threshold from the position's exit strategy (exit_strategy_override or default)
**And** the worker calculates the loss percentage: ((current_price - entry_price) / entry_price) * 100
**And** if the loss percentage ≤ -stop_loss_percent (e.g., -20%), the stop-loss is triggered

**Given** a stop-loss condition is met
**When** the exit execution pipeline runs
**Then** the position is marked for exit with exit_reason='stop_loss'
**And** the system calculates the exit amount: 100% of remaining_amount_tokens (full exit)
**And** if the position is in simulation mode, an order is created with type='exit', status='simulated', executed_at=NOW()
**And** if the position is in live mode, a Jupiter API swap call is executed: input_mint=token_mint, output_mint=SOL/USDC, amount=remaining_amount_tokens
**And** the position's status is updated to 'closed', closed_at=NOW(), realized_pnl_usd=(exit_price - entry_price) * amount_tokens

**Given** a position is open and has reached a profit threshold
**When** the trailing-stop strategy is evaluated
**Then** the worker checks if the position is profitable: current_price > entry_price
**And** if profitable, the worker retrieves the trailing_stop_percent from the exit strategy
**And** the worker tracks the peak_price (highest price since position opened) in memory or position metadata
**And** the worker calculates the trailing-stop trigger: peak_price - (peak_price * trailing_stop_percent / 100)
**And** if current_price ≤ trailing_stop_trigger, the trailing-stop is activated

**Given** a trailing-stop condition is met
**When** the exit execution pipeline runs
**Then** the position is marked for exit with exit_reason='trailing_stop'
**And** the exit process follows the same logic as stop-loss (100% exit, dual-mode execution)
**And** the position is closed with realized_pnl_usd reflecting the profit captured

**Given** stop-loss and trailing-stop strategies are active
**When** both conditions are evaluated for a position
**Then** the stop-loss is checked FIRST (capital protection priority, FR-6)
**And** if stop-loss triggers, trailing-stop is ignored
**And** if stop-loss does NOT trigger and position is profitable, trailing-stop is evaluated

**Given** exit strategies are executing
**When** I view the Dashboard sidebar for a closed position
**Then** the sidebar displays: Exit Reason (e.g., "Stop-Loss @ -20%"), Exit Price, Exit Date, Realized PnL
**And** I can see the full transaction history: Entry order → Exit order with timestamps and prices

### Story 3.4: Scaling-Out Exit Strategy

As an operator,
I want to scale out of positions at predefined profit levels,
So that I can lock in partial profits while maintaining exposure to further upside.

**Acceptance Criteria:**

**Given** a position is open and profitable
**When** the scaling-out strategy is evaluated
**Then** the worker retrieves the scaling levels from the exit strategy (e.g., "25% at +50%, 50% at +100%, 75% at +150%")
**And** the worker parses the scaling configuration into a list of (profit_percent, exit_percent) tuples

**Given** scaling levels are configured for a position
**When** the current price crosses a scaling level threshold
**Then** the worker calculates the profit percentage: ((current_price - entry_price) / entry_price) * 100
**And** if profit_percent ≥ scaling_level_threshold (e.g., +50%), the scaling exit is triggered

**Given** a scaling-out condition is met
**When** the exit execution pipeline runs
**Then** the position is marked for PARTIAL exit with exit_reason='scaling_out_level_N'
**And** the system calculates the exit amount: (scaling_exit_percent / 100) * original_amount_tokens (e.g., 25% of original)
**And** if the position is in simulation mode, an order is created with type='exit', status='simulated', amount_tokens=exit_amount
**And** if the position is in live mode, a Jupiter API swap call is executed for the partial amount
**And** the position's remaining_amount_tokens is updated: original_amount - exit_amount
**And** the position's realized_pnl_usd is updated: realized_pnl_usd + ((exit_price - entry_price) * exit_amount)
**And** the position status remains 'open' (partial exit, not full close)

**Given** a position has executed a partial scaling exit
**When** the price continues to rise and crosses the next scaling level
**Then** the next scaling exit is triggered using the ORIGINAL amount_tokens as the basis (not remaining amount)
**And** the exit amount is calculated: (next_scaling_percent / 100) * original_amount_tokens
**And** the process repeats until all scaling levels are exhausted or the position is fully closed

**Given** multiple scaling exits occur for a position
**When** I view the Dashboard sidebar for that position
**Then** the sidebar displays: Multiple exit orders with timestamps, amounts, and prices
**And** the "PnL Breakdown" section shows: Realized PnL (from scaling exits), Unrealized PnL (from remaining amount)
**And** the "Remaining Amount" field shows the current remaining_amount_tokens

**Given** a position has scaled out at multiple levels
**When** another exit strategy triggers (e.g., stop-loss, mirror-exit)
**Then** the exit applies to the remaining_amount_tokens only (not the original amount)
**And** the position is fully closed with status='closed'

### Story 3.5: Exit Strategy Execution Engine - Priority Logic & Order Creation

As an operator,
I want all exit strategies to execute in the correct priority order with proper error handling,
So that capital protection takes precedence and trades execute reliably.

**Acceptance Criteria:**

**Given** price monitoring is active for an open position
**When** the exit strategy evaluation worker runs (every 30-60s)
**Then** the worker evaluates exit conditions in the following priority order:
1. Stop-Loss (highest priority, capital protection)
2. Trailing-Stop (profit protection)
3. Scaling-Out (profit taking)
**And** only the FIRST triggered condition executes (no multiple simultaneous exits)

**Given** an exit condition is triggered
**When** the exit execution engine creates an order
**Then** a new record is inserted into the `orders` table with: position_id (FK), type='exit', amount_tokens (full or partial), price_usd (current market price), status='pending', retry_count=0

**Given** an exit order is in 'pending' status for a simulation position
**When** the order worker processes the order
**Then** the order status is immediately updated to 'simulated' (no API call required)
**And** the order's executed_at timestamp is set to NOW()
**And** the position is updated accordingly (partial or full close)

**Given** an exit order is in 'pending' status for a live position
**When** the order worker processes the order
**Then** the worker calls Jupiter API to execute the swap: input_mint=token_mint, output_mint=SOL/USDC, amount=order.amount_tokens
**And** if Jupiter API succeeds, the order status is updated to 'filled', tx_signature is stored, slippage_percent is calculated and stored
**And** the position is updated with new remaining_amount_tokens and realized_pnl_usd

**Given** a Jupiter API call fails during exit order execution
**When** the order worker encounters the error
**Then** the worker retries the API call up to 3 times with exponential backoff (5s, 15s, 30s)
**And** the order's retry_count is incremented with each attempt
**And** if all retries fail, the order status is set to 'failed', last_error is stored
**And** the position remains 'open' (exit did not complete)
**And** the failure is logged with structured logging (level: ERROR, event: exit_order_failed, position_id: value, error: message)

**Given** exit orders are being processed
**When** I view the Dashboard sidebar for a position with a failed exit order
**Then** the sidebar displays a warning: "Exit order failed - manual intervention required"
**And** I can see the error details: Retry count, Last error message, Last attempt timestamp
**And** I have an option to [Retry Order] manually (placeholder for future enhancement)
