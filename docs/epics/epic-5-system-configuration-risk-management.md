# Epic 5: System Configuration & Risk Management

Operator can configure all system parameters (capital, risk limits, safety thresholds, exit strategy templates), monitor system health (webhook status, circuit breakers), and receive automated protection against excessive losses via circuit breakers.

### Story 5.1: System Configuration Management - Capital, Risk Limits, Safety

As an operator,
I want to configure all system parameters in the Config tab,
So that I can control capital allocation, risk exposure, and safety thresholds.

**Acceptance Criteria:**

**Given** I am on the Config tab in the "Risk Limits" accordion section
**When** I view the form fields
**Then** I see the following fields pre-filled with current values from the `config` table:
- Total Capital USD: number input (e.g., 10000)
- Max Capital Per Trade %: number input (e.g., 5)
- Max Total Capital %: number input (e.g., 80)
- Circuit Breaker Loss Threshold %: number input (e.g., 15)
- Daily Loss Limit USD: number input (e.g., 500)
- Safety Score Threshold: number input (range 0.00-1.00, e.g., 0.60)

**Given** the Risk Limits form is displayed
**When** I modify any field value and click [Save]
**Then** the system validates the input (e.g., Total Capital > 0, percentages in valid range)
**And** if validation passes, the `config` table is updated with new values
**And** a success message displays: "Configuration saved successfully"
**And** the update is logged with structured logging (level: INFO, event: config_updated, fields: changed_fields)

**Given** I enter invalid values (e.g., negative capital, percentage > 100)
**When** I click [Save]
**Then** validation errors display next to the invalid fields
**And** the form does not submit
**And** the `config` table is not modified

**Given** the configuration is updated
**When** new positions are created
**Then** the system uses the updated values immediately (e.g., new max_capital_per_trade_percent for position sizing)
**And** existing open positions are not affected (configuration is immutable at position creation)

**Given** I am on the Config tab in the "Exit Strategies" accordion section
**When** I view the default exit strategy fields
**Then** I see fields for: Stop Loss %, Trailing Stop %, Scaling Out Levels (text), Mirror Exit Enabled (checkbox)
**And** the fields are pre-filled with values from the `config` table or a default exit strategy template

**Given** I modify exit strategy defaults and click [Save]
**When** the update executes
**Then** the default exit strategy is updated in the `config` table or linked `exit_strategies` template
**And** future positions use the updated defaults (unless overridden at position level)

**Given** the Config tab is loaded
**When** I navigate between accordion sections (Risk Limits, Exit Strategies, API Keys)
**Then** all unsaved changes are preserved within the current session
**And** a warning displays if I navigate away with unsaved changes: "You have unsaved changes. Discard?"

### Story 5.2: Exit Strategy Templates - Create, Edit, Delete

As an operator,
I want to create reusable exit strategy templates,
So that I can apply different strategies to different wallets or positions.

**Acceptance Criteria:**

**Given** I am on the Config tab in the "Exit Strategies" section
**When** I click [+ Create Template] button
**Then** a modal form appears with fields:
- Template Name: text input (required, e.g., "Conservative", "Aggressive")
- Stop Loss %: number input (default: 20)
- Trailing Stop %: number input (default: 15)
- Scaling Out Levels: text input (e.g., "25% at +50%, 50% at +100%, 75% at +150%")
- Mirror Exit Enabled: checkbox (default: checked)

**Given** the Create Template modal is open
**When** I enter a template name and configure strategy parameters, then click [Save]
**Then** a new record is inserted into the `exit_strategies` table with: name (template name), stop_loss_percent, trailing_stop_percent, scaling_out_config (JSONB), mirror_exit_enabled
**And** the modal closes
**And** the template appears in a templates list in the Config tab
**And** a success message displays: "Template created successfully"

**Given** I have created multiple exit strategy templates
**When** I view the templates list in the Config tab
**Then** I see all templates with: Name, Stop Loss %, Trailing Stop %, Actions ([Edit], [Delete], [Set as Default])

**Given** I click [Edit] on a template
**When** the Edit Template modal opens
**Then** the modal is pre-filled with the template's current values
**And** I can modify any field and click [Save] to update the `exit_strategies` table

**Given** I click [Delete] on a template
**When** the confirmation dialog appears
**Then** the dialog warns: "Delete template [Name]? This will not affect existing positions using this template."
**And** if I confirm, the template is deleted from the `exit_strategies` table (soft delete or hard delete)
**And** wallets using this template as default revert to the system default template

**Given** I click [Set as Default] on a template
**When** the action executes
**Then** the `config` table is updated with: default_exit_strategy_id = template_id
**And** all NEW wallets added to the watchlist use this template by default
**And** existing wallets are not affected (they retain their configured default)

**Given** I am adding a new wallet (Story 2.1)
**When** the Add Wallet modal is displayed
**Then** I see an "Exit Strategy" dropdown with all available templates
**And** the default template is pre-selected
**And** I can choose a different template for this wallet

### Story 5.3: Circuit Breaker Logic - Automatic Position Blocking

As an operator,
I want the system to automatically block new positions when losses exceed thresholds,
So that I prevent catastrophic capital loss during adverse market conditions.

**Acceptance Criteria:**

**Given** Epic 5 Story 5.3 is being implemented
**When** the circuit breaker feature is initialized
**Then** the `circuit_breaker_events` table is created in the database with schema: id (SERIAL PRIMARY KEY), event_type (VARCHAR: 'triggered' or 'reset'), triggered_at (TIMESTAMP), reason (VARCHAR), loss_amount_usd (DECIMAL, nullable), loss_percent (DECIMAL, nullable), reset_by (VARCHAR, nullable: 'operator' or 'automatic_daily_reset')
**And** the table has COMMENT ON TABLE documenting its architectural pattern (Event Sourcing for audit trail)
**And** all necessary indexes are created (triggered_at for time-based queries, event_type for status checks)

**Given** positions are being closed throughout the day
**When** the circuit breaker evaluation worker runs (after each position close or every 5 minutes)
**Then** the worker calculates the daily loss: SUM(realized_pnl_usd) for all positions closed today (WHERE closed_at >= TODAY)
**And** the worker retrieves the circuit breaker threshold from the `config` table: circuit_breaker_loss_threshold_percent, daily_loss_limit_usd

**Given** the daily loss exceeds the USD threshold
**When** the circuit breaker logic evaluates: daily_loss_usd < -daily_loss_limit_usd (e.g., -$550 < -$500)
**Then** the circuit breaker is TRIGGERED
**And** a new record is inserted into the `circuit_breaker_events` table with: event_type='triggered', triggered_at=NOW(), reason='daily_loss_limit_exceeded', loss_amount_usd (daily loss)

**Given** the daily loss exceeds the percentage threshold
**When** the circuit breaker logic evaluates: (daily_loss_usd / total_capital_usd) * 100 < -circuit_breaker_loss_threshold_percent (e.g., -15.5% < -15%)
**Then** the circuit breaker is TRIGGERED
**And** a new record is inserted into the `circuit_breaker_events` table with event_type='triggered', reason='percentage_loss_threshold_exceeded', loss_percent (daily loss %)

**Given** the circuit breaker is triggered
**When** a new signal passes safety filtering and is ready for position creation
**Then** the position creation pipeline checks the circuit breaker status
**And** if a 'triggered' event exists with no corresponding 'reset' event, position creation is BLOCKED
**And** the signal is logged as filtered with filter_reason='circuit_breaker_active'
**And** the block is logged with structured logging (level: WARN, event: position_blocked_circuit_breaker, signal_id: value)

**Given** the circuit breaker is active (triggered)
**When** open positions reach their exit conditions
**Then** exit strategies continue to execute normally (ADR-004: Circuit Breaker Non-Closing)
**And** positions are closed to preserve remaining capital
**And** NO new positions are created until the circuit breaker is reset

**Given** the circuit breaker is active
**When** I view the Dashboard tab
**Then** a prominent warning banner displays: "⚠️ Circuit Breaker Active - New positions blocked. Daily loss: -$550 (-15.5%)"
**And** the banner has a [View Details] button that shows circuit breaker events

**Given** the circuit breaker is active
**When** I view the Config tab
**Then** the Circuit Breaker status indicator shows: "Active 🔴" with trigger reason and timestamp
**And** a [Reset Circuit Breaker] button is available for manual reset

### Story 5.4: Circuit Breaker Reset & Event Logging

As an operator,
I want to manually reset the circuit breaker or have it auto-reset daily,
So that I can resume trading after addressing the underlying issues.

**Acceptance Criteria:**

**Given** the circuit breaker is active (triggered event exists)
**When** I click [Reset Circuit Breaker] in the Config tab
**Then** a confirmation dialog appears: "Reset circuit breaker and resume position creation?"
**And** the dialog has [Confirm] and [Cancel] buttons

**Given** I confirm the circuit breaker reset
**When** the reset executes
**Then** a new record is inserted into the `circuit_breaker_events` table with: event_type='reset', triggered_at=NOW(), reason='manual_reset', reset_by='operator'
**And** the reset is logged with structured logging (level: INFO, event: circuit_breaker_reset, reason: manual)
**And** position creation is re-enabled immediately
**And** a success message displays: "Circuit breaker reset successfully"

**Given** the circuit breaker is active
**When** the daily reset worker runs (scheduled at 00:00 UTC, beginning of new trading day)
**Then** the worker checks for active circuit breaker events (triggered with no matching reset)
**And** if found, the worker automatically inserts a 'reset' event with reason='automatic_daily_reset'
**And** the reset is logged with structured logging (level: INFO, event: circuit_breaker_auto_reset)

**Given** I want to audit circuit breaker history
**When** I view the Config tab Circuit Breaker section
**Then** I see a history table showing all circuit breaker events:
- Event Type (Triggered/Reset)
- Timestamp
- Reason (daily_loss_limit_exceeded, percentage_loss_threshold_exceeded, manual_reset, automatic_daily_reset)
- Loss Amount/Percent (for triggered events)
**And** the table shows the last 30 days of events

**Given** the circuit breaker has been triggered and reset multiple times
**When** I analyze the event history
**Then** I can identify patterns (e.g., "Circuit breaker triggered 3 times in past 7 days")
**And** I can make informed decisions about adjusting thresholds or pausing live trading

### Story 5.5: System Health Monitoring & Status Indicators

As an operator,
I want to monitor system health across all critical components,
So that I can quickly identify and resolve issues affecting trading operations.

**Acceptance Criteria:**

**Given** I am on the Config tab in the "API Keys" section
**When** the tab loads
**Then** I see status indicators for all critical services:
- Helius Webhook: "Connected ✅" or "Disconnected ❌" with last signal timestamp
- Supabase Database: "Connected ✅" or "Error ❌" with connection status
- Jupiter API: "Operational ✅" or "Degraded ⚠️" based on recent API call success rate
- DexScreener API: "Operational ✅" or "Degraded ⚠️" based on recent API call success rate

**Given** the Helius webhook is connected and receiving signals
**When** the status indicator updates
**Then** it displays: "Connected ✅ | Last signal: 2 minutes ago"
**And** the timestamp updates in real-time (or near real-time)

**Given** the Helius webhook has not received signals for >30 minutes
**When** the health check worker evaluates the status
**Then** the indicator changes to: "Warning ⚠️ | No signals for 35 minutes"
**And** a warning is logged with structured logging (level: WARN, event: webhook_silence_detected, duration_minutes: value)

**Given** the Jupiter API has failed >20% of calls in the past hour
**When** the health check worker evaluates the status
**Then** the indicator changes to: "Degraded ⚠️ | 25% failure rate (past hour)"
**And** the degradation is logged with structured logging (level: WARN, event: api_degraded, service: jupiter, failure_rate: value)

**Given** I want to refresh system health status manually
**When** I click a [Refresh Status] button in the Config tab
**Then** the system executes health checks for all services immediately
**And** all status indicators update with current data
**And** a timestamp displays: "Last checked: just now"

**Given** critical system errors occur (database connection lost, all API sources down)
**When** the health check worker detects the errors
**Then** the errors are logged with structured logging (level: ERROR, event: critical_system_failure, component: value)
**And** a critical alert banner displays across all UI tabs: "🚨 Critical Error: [Component] unavailable"
**And** the system continues to operate in degraded mode (e.g., no new positions, existing positions monitored)

**Given** I am on the Dashboard tab
**When** the application loads
**Then** I see a System Health summary widget showing:
- Overall Status: "Healthy ✅" or "Degraded ⚠️" or "Critical 🔴"
- Active Positions: count
- Webhook Status: Connected/Disconnected
- Circuit Breaker Status: Inactive/Active
**And** clicking the widget navigates to the Config tab for detailed status
