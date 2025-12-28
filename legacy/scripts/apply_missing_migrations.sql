-- Supabase migration: signals table for signal logging
-- Story 3-6: Signal Logging & Storage (FR18)

CREATE TABLE IF NOT EXISTS signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tx_signature VARCHAR(100) NOT NULL UNIQUE,
    wallet_address VARCHAR(50) NOT NULL,
    token_address VARCHAR(50) NOT NULL,
    direction VARCHAR(10) NOT NULL,

    -- Transaction details
    amount_token DECIMAL(30, 10),
    amount_sol DECIMAL(20, 10),
    slot BIGINT,

    -- Scores
    final_score DECIMAL(5, 4),
    wallet_score DECIMAL(5, 4),
    cluster_score DECIMAL(5, 4),
    token_score DECIMAL(5, 4),
    context_score DECIMAL(5, 4),

    -- Status
    status VARCHAR(20) NOT NULL DEFAULT 'received',
    eligibility_status VARCHAR(30),
    conviction_tier VARCHAR(20),

    -- Filter info
    filter_status VARCHAR(20),
    filter_reason TEXT,

    -- Trade link (FK to trades table when Epic 4 completes)
    trade_id UUID,

    -- Timestamps
    timestamp TIMESTAMPTZ NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processing_time_ms DECIMAL(10, 2),

    -- Metadata
    raw_factors JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for query performance (AC2, NFR23: 6 months of data)
CREATE INDEX IF NOT EXISTS idx_signals_timestamp ON signals(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_signals_wallet ON signals(wallet_address, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_signals_score ON signals(final_score DESC) WHERE final_score IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_signals_status ON signals(status, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_signals_eligibility ON signals(eligibility_status, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_signals_trade ON signals(trade_id) WHERE trade_id IS NOT NULL;

-- Composite index for common queries
CREATE INDEX IF NOT EXISTS idx_signals_wallet_score ON signals(wallet_address, final_score DESC, timestamp DESC);

-- Function for calculating averages
CREATE OR REPLACE FUNCTION get_signal_averages(start_ts TIMESTAMPTZ, end_ts TIMESTAMPTZ)
RETURNS TABLE(avg_score DECIMAL, avg_processing_ms DECIMAL) AS $$
BEGIN
    RETURN QUERY
    SELECT
        AVG(final_score)::DECIMAL,
        AVG(processing_time_ms)::DECIMAL
    FROM signals
    WHERE timestamp >= start_ts AND timestamp <= end_ts
    AND final_score IS NOT NULL;
END;
$$ LANGUAGE plpgsql;

-- Comment for documentation
COMMENT ON TABLE signals IS 'Signal logging table for all processed signals (FR18)';
COMMENT ON COLUMN signals.tx_signature IS 'Unique transaction signature from Solana';
COMMENT ON COLUMN signals.final_score IS 'Multi-factor composite score (0-1)';
COMMENT ON COLUMN signals.eligibility_status IS 'Trade eligibility: trade_eligible, below_threshold';
COMMENT ON COLUMN signals.conviction_tier IS 'Position sizing tier: high, standard, none';
COMMENT ON COLUMN signals.trade_id IS 'Link to executed trade (Epic 4)';
-- Trade executions log
-- Schema: walltrack

SET search_path TO walltrack, public;

-- =============================================================================
-- Trades table
-- =============================================================================

CREATE TABLE IF NOT EXISTS walltrack.trades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id UUID REFERENCES walltrack.signals(id),

    -- Trade details
    direction TEXT NOT NULL CHECK (direction IN ('buy', 'sell')),
    token_address TEXT NOT NULL,
    input_mint TEXT NOT NULL,
    output_mint TEXT NOT NULL,

    -- Amounts
    input_amount BIGINT NOT NULL,
    output_amount BIGINT,
    output_amount_min BIGINT,
    slippage_bps INTEGER NOT NULL,

    -- Execution
    status TEXT NOT NULL DEFAULT 'pending',
    tx_signature TEXT UNIQUE,
    quote_source TEXT NOT NULL DEFAULT 'jupiter',
    entry_price DECIMAL(30, 18),
    execution_time_ms DECIMAL(10, 2),

    -- Failure tracking
    failure_reason TEXT,
    error_message TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    submitted_at TIMESTAMPTZ,
    confirmed_at TIMESTAMPTZ,

    -- Constraints
    CONSTRAINT valid_status CHECK (status IN (
        'pending', 'quoting', 'signing', 'submitted',
        'confirming', 'success', 'failed', 'retry'
    )),
    CONSTRAINT valid_failure_reason CHECK (
        failure_reason IS NULL OR failure_reason IN (
            'quote_failed', 'slippage_exceeded', 'insufficient_balance',
            'transaction_expired', 'network_error', 'rpc_error', 'unknown'
        )
    )
);

-- Trigger for auto-updating updated_at if exists
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'update_updated_at_column') THEN
        -- No updated_at column in trades, skip
        NULL;
    END IF;
END$$;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_trades_signal ON walltrack.trades(signal_id);
CREATE INDEX IF NOT EXISTS idx_trades_token ON walltrack.trades(token_address);
CREATE INDEX IF NOT EXISTS idx_trades_status ON walltrack.trades(status);
CREATE INDEX IF NOT EXISTS idx_trades_created ON walltrack.trades(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_trades_signature ON walltrack.trades(tx_signature)
    WHERE tx_signature IS NOT NULL;

-- =============================================================================
-- Trade execution metrics (aggregated)
-- =============================================================================

CREATE TABLE IF NOT EXISTS walltrack.trade_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    date DATE NOT NULL,
    hour INTEGER NOT NULL CHECK (hour >= 0 AND hour < 24),

    -- Counts
    total_trades INTEGER NOT NULL DEFAULT 0,
    successful_trades INTEGER NOT NULL DEFAULT 0,
    failed_trades INTEGER NOT NULL DEFAULT 0,

    -- Volumes
    total_input_sol DECIMAL(20, 9) NOT NULL DEFAULT 0,
    total_output_sol DECIMAL(20, 9) NOT NULL DEFAULT 0,

    -- Performance
    avg_execution_time_ms DECIMAL(10, 2),
    avg_slippage_bps DECIMAL(10, 2),

    -- Source breakdown
    jupiter_trades INTEGER NOT NULL DEFAULT 0,
    raydium_trades INTEGER NOT NULL DEFAULT 0,

    UNIQUE(date, hour)
);

CREATE INDEX IF NOT EXISTS idx_trade_metrics_date ON walltrack.trade_metrics(date DESC);

-- =============================================================================
-- RLS Policies
-- =============================================================================

ALTER TABLE walltrack.trades ENABLE ROW LEVEL SECURITY;
ALTER TABLE walltrack.trade_metrics ENABLE ROW LEVEL SECURITY;

-- Service role full access
CREATE POLICY "Service role full access on trades"
ON walltrack.trades FOR ALL TO service_role USING (true);

CREATE POLICY "Service role full access on trade_metrics"
ON walltrack.trade_metrics FOR ALL TO service_role USING (true);

-- Read access for dashboard
CREATE POLICY "Allow read on trades"
ON walltrack.trades FOR SELECT USING (true);

CREATE POLICY "Allow read on trade_metrics"
ON walltrack.trade_metrics FOR SELECT USING (true);

-- =============================================================================
-- Helper function to record trade
-- =============================================================================

CREATE OR REPLACE FUNCTION walltrack.record_trade(
    p_signal_id UUID,
    p_direction TEXT,
    p_token_address TEXT,
    p_input_mint TEXT,
    p_output_mint TEXT,
    p_input_amount BIGINT,
    p_slippage_bps INTEGER
)
RETURNS UUID AS $$
DECLARE
    v_trade_id UUID;
BEGIN
    INSERT INTO walltrack.trades (
        signal_id, direction, token_address, input_mint, output_mint,
        input_amount, slippage_bps, status
    )
    VALUES (
        p_signal_id, p_direction, p_token_address, p_input_mint, p_output_mint,
        p_input_amount, p_slippage_bps, 'pending'
    )
    RETURNING id INTO v_trade_id;

    RETURN v_trade_id;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- Helper function to update trade result
-- =============================================================================

CREATE OR REPLACE FUNCTION walltrack.update_trade_result(
    p_trade_id UUID,
    p_status TEXT,
    p_tx_signature TEXT,
    p_output_amount BIGINT,
    p_entry_price DECIMAL(30, 18),
    p_execution_time_ms DECIMAL(10, 2),
    p_failure_reason TEXT,
    p_error_message TEXT
)
RETURNS VOID AS $$
BEGIN
    UPDATE walltrack.trades
    SET
        status = p_status,
        tx_signature = p_tx_signature,
        output_amount = p_output_amount,
        entry_price = p_entry_price,
        execution_time_ms = p_execution_time_ms,
        failure_reason = p_failure_reason,
        error_message = p_error_message,
        confirmed_at = CASE WHEN p_status = 'success' THEN NOW() ELSE NULL END
    WHERE id = p_trade_id;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- Function to update hourly trade metrics
-- =============================================================================

CREATE OR REPLACE FUNCTION walltrack.update_trade_metrics()
RETURNS TRIGGER AS $$
DECLARE
    v_date DATE;
    v_hour INTEGER;
BEGIN
    v_date := DATE(NEW.created_at);
    v_hour := EXTRACT(HOUR FROM NEW.created_at);

    INSERT INTO walltrack.trade_metrics (date, hour, total_trades, successful_trades, failed_trades,
                                         total_input_sol, jupiter_trades, raydium_trades)
    VALUES (v_date, v_hour, 1,
            CASE WHEN NEW.status = 'success' THEN 1 ELSE 0 END,
            CASE WHEN NEW.status = 'failed' THEN 1 ELSE 0 END,
            NEW.input_amount::DECIMAL / 1000000000,
            CASE WHEN NEW.quote_source = 'jupiter' THEN 1 ELSE 0 END,
            CASE WHEN NEW.quote_source = 'raydium' THEN 1 ELSE 0 END)
    ON CONFLICT (date, hour) DO UPDATE
    SET
        total_trades = trade_metrics.total_trades + 1,
        successful_trades = trade_metrics.successful_trades +
            CASE WHEN NEW.status = 'success' THEN 1 ELSE 0 END,
        failed_trades = trade_metrics.failed_trades +
            CASE WHEN NEW.status = 'failed' THEN 1 ELSE 0 END,
        total_input_sol = trade_metrics.total_input_sol +
            NEW.input_amount::DECIMAL / 1000000000,
        jupiter_trades = trade_metrics.jupiter_trades +
            CASE WHEN NEW.quote_source = 'jupiter' THEN 1 ELSE 0 END,
        raydium_trades = trade_metrics.raydium_trades +
            CASE WHEN NEW.quote_source = 'raydium' THEN 1 ELSE 0 END;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to update metrics on trade insert
CREATE TRIGGER update_trade_metrics_on_insert
    AFTER INSERT ON walltrack.trades
    FOR EACH ROW
    EXECUTE FUNCTION walltrack.update_trade_metrics();
-- Migration: 007_position_sizing.sql
-- Story: 4-3 Dynamic Position Sizing

CREATE TABLE IF NOT EXISTS position_sizing_config (
    id UUID PRIMARY KEY DEFAULT '00000000-0000-0000-0000-000000000001',
    base_position_pct DECIMAL(5, 2) NOT NULL DEFAULT 2.0,
    min_position_sol DECIMAL(20, 9) NOT NULL DEFAULT 0.01,
    max_position_sol DECIMAL(20, 9) NOT NULL DEFAULT 1.0,
    high_conviction_multiplier DECIMAL(5, 2) NOT NULL DEFAULT 1.5,
    standard_conviction_multiplier DECIMAL(5, 2) NOT NULL DEFAULT 1.0,
    high_conviction_threshold DECIMAL(5, 4) NOT NULL DEFAULT 0.85,
    min_conviction_threshold DECIMAL(5, 4) NOT NULL DEFAULT 0.70,
    max_concurrent_positions INTEGER NOT NULL DEFAULT 5,
    max_capital_allocation_pct DECIMAL(5, 2) NOT NULL DEFAULT 50.0,
    reserve_sol DECIMAL(20, 9) NOT NULL DEFAULT 0.05,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by TEXT,
    CONSTRAINT valid_base_pct CHECK (base_position_pct > 0 AND base_position_pct <= 100),
    CONSTRAINT valid_thresholds CHECK (high_conviction_threshold > min_conviction_threshold)
);

CREATE TABLE IF NOT EXISTS position_sizing_audit (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id UUID,
    token_address TEXT,
    signal_score DECIMAL(5, 4) NOT NULL,
    available_balance_sol DECIMAL(20, 9) NOT NULL,
    current_position_count INTEGER NOT NULL,
    current_allocated_sol DECIMAL(20, 9) NOT NULL,
    config_snapshot JSONB NOT NULL,
    decision TEXT NOT NULL,
    conviction_tier TEXT NOT NULL,
    base_size_sol DECIMAL(20, 9) NOT NULL,
    multiplier DECIMAL(5, 2) NOT NULL,
    calculated_size_sol DECIMAL(20, 9) DEFAULT 0,
    final_size_sol DECIMAL(20, 9) NOT NULL,
    reason TEXT,
    reduction_applied BOOLEAN DEFAULT FALSE,
    reduction_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_position_audit_signal ON position_sizing_audit(signal_id);
CREATE INDEX IF NOT EXISTS idx_position_audit_created ON position_sizing_audit(created_at DESC);

INSERT INTO position_sizing_config (id) VALUES ('00000000-0000-0000-0000-000000000001')
ON CONFLICT (id) DO NOTHING;

ALTER TABLE position_sizing_config ENABLE ROW LEVEL SECURITY;
ALTER TABLE position_sizing_audit ENABLE ROW LEVEL SECURITY;
-- Migration: 008_exit_strategies.sql
-- Story: 4-4 Exit Strategy Data Model

CREATE TABLE IF NOT EXISTS exit_strategies (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    preset TEXT NOT NULL DEFAULT 'custom',
    is_default BOOLEAN NOT NULL DEFAULT false,
    take_profit_levels JSONB NOT NULL DEFAULT '[]',
    stop_loss DECIMAL(5, 4) NOT NULL DEFAULT 0.5,
    trailing_stop JSONB NOT NULL DEFAULT '{"enabled": false, "activation_multiplier": 2.0, "distance_percentage": 30.0}',
    time_rules JSONB NOT NULL DEFAULT '{"max_hold_hours": null, "stagnation_exit_enabled": false, "stagnation_threshold_pct": 5.0, "stagnation_hours": 24}',
    moonbag JSONB NOT NULL DEFAULT '{"percentage": 0.0, "stop_loss": null}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by TEXT,
    CONSTRAINT valid_preset CHECK (preset IN ('conservative', 'balanced', 'moonbag_aggressive', 'quick_flip', 'diamond_hands', 'custom')),
    CONSTRAINT valid_stop_loss CHECK (stop_loss >= 0.1 AND stop_loss <= 1.0)
);

CREATE INDEX IF NOT EXISTS idx_exit_strategies_preset ON exit_strategies(preset);
CREATE INDEX IF NOT EXISTS idx_exit_strategies_default ON exit_strategies(is_default);

CREATE TABLE IF NOT EXISTS exit_strategy_assignments (
    id TEXT PRIMARY KEY,
    strategy_id TEXT NOT NULL REFERENCES exit_strategies(id) ON DELETE CASCADE,
    conviction_tier TEXT,
    position_id UUID,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT assignment_target CHECK (
        (conviction_tier IS NOT NULL AND position_id IS NULL) OR
        (conviction_tier IS NULL AND position_id IS NOT NULL)
    ),
    CONSTRAINT valid_tier CHECK (conviction_tier IS NULL OR conviction_tier IN ('high', 'standard'))
);

CREATE INDEX IF NOT EXISTS idx_assignments_tier ON exit_strategy_assignments(conviction_tier) WHERE conviction_tier IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_assignments_active ON exit_strategy_assignments(is_active);

ALTER TABLE exit_strategies ENABLE ROW LEVEL SECURITY;
ALTER TABLE exit_strategy_assignments ENABLE ROW LEVEL SECURITY;
-- Migration: 009_positions.sql
-- Story: 4-5 Stop-Loss and Take-Profit Monitoring

-- Positions table
CREATE TABLE IF NOT EXISTS positions (
    id TEXT PRIMARY KEY,
    signal_id TEXT NOT NULL,
    token_address TEXT NOT NULL,
    token_symbol TEXT,

    -- Status
    status TEXT NOT NULL DEFAULT 'pending',

    -- Entry details
    entry_tx_signature TEXT,
    entry_price DECIMAL(30, 18) NOT NULL,
    entry_amount_sol DECIMAL(20, 9) NOT NULL,
    entry_amount_tokens DECIMAL(30, 0) NOT NULL,
    entry_time TIMESTAMPTZ NOT NULL,

    -- Current state
    current_amount_tokens DECIMAL(30, 0) NOT NULL,
    realized_pnl_sol DECIMAL(20, 9) NOT NULL DEFAULT 0,

    -- Exit strategy
    exit_strategy_id TEXT NOT NULL REFERENCES exit_strategies(id),
    conviction_tier TEXT NOT NULL,
    levels JSONB,

    -- Moonbag
    is_moonbag BOOLEAN NOT NULL DEFAULT false,
    moonbag_percentage DECIMAL(5, 2) NOT NULL DEFAULT 0,

    -- Exit details
    exit_reason TEXT,
    exit_time TIMESTAMPTZ,
    exit_price DECIMAL(30, 18),
    exit_tx_signatures TEXT[] NOT NULL DEFAULT '{}',

    -- Tracking
    last_price_check TIMESTAMPTZ,
    peak_price DECIMAL(30, 18),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT valid_position_status CHECK (status IN (
        'pending', 'open', 'partial_exit', 'closing', 'closed', 'moonbag'
    )),
    CONSTRAINT valid_position_exit_reason CHECK (exit_reason IS NULL OR exit_reason IN (
        'stop_loss', 'take_profit', 'trailing_stop', 'time_limit',
        'stagnation', 'manual', 'moonbag_stop'
    )),
    CONSTRAINT valid_conviction_tier CHECK (conviction_tier IN ('high', 'standard'))
);

CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status);
CREATE INDEX IF NOT EXISTS idx_positions_token ON positions(token_address);
CREATE INDEX IF NOT EXISTS idx_positions_created ON positions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_positions_open ON positions(status)
    WHERE status IN ('open', 'partial_exit', 'moonbag');
CREATE INDEX IF NOT EXISTS idx_positions_signal ON positions(signal_id);

-- Exit executions table
CREATE TABLE IF NOT EXISTS exit_executions (
    id TEXT PRIMARY KEY,
    position_id TEXT NOT NULL REFERENCES positions(id) ON DELETE CASCADE,
    exit_reason TEXT NOT NULL,
    trigger_level TEXT NOT NULL,

    sell_percentage DECIMAL(5, 2) NOT NULL,
    amount_tokens_sold DECIMAL(30, 0) NOT NULL,
    amount_sol_received DECIMAL(20, 9) NOT NULL,
    exit_price DECIMAL(30, 18) NOT NULL,
    tx_signature TEXT NOT NULL,

    realized_pnl_sol DECIMAL(20, 9) NOT NULL,
    executed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT valid_exit_execution_reason CHECK (exit_reason IN (
        'stop_loss', 'take_profit', 'trailing_stop', 'time_limit',
        'stagnation', 'manual', 'moonbag_stop'
    ))
);

CREATE INDEX IF NOT EXISTS idx_exit_executions_position ON exit_executions(position_id);
CREATE INDEX IF NOT EXISTS idx_exit_executions_reason ON exit_executions(exit_reason);
CREATE INDEX IF NOT EXISTS idx_exit_executions_time ON exit_executions(executed_at DESC);

-- RLS Policies
ALTER TABLE positions ENABLE ROW LEVEL SECURITY;
ALTER TABLE exit_executions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role full access on positions"
ON positions FOR ALL TO service_role USING (true);

CREATE POLICY "Service role full access on exit_executions"
ON exit_executions FOR ALL TO service_role USING (true);
-- Risk Management Schema
-- Story 5-1: Drawdown Circuit Breaker

-- Capital snapshots for tracking peak and drawdown
CREATE TABLE IF NOT EXISTS capital_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    capital DECIMAL(20, 8) NOT NULL,
    peak_capital DECIMAL(20, 8) NOT NULL,
    drawdown_percent DECIMAL(10, 4) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_capital_snapshots_timestamp ON capital_snapshots(timestamp DESC);

-- Circuit breaker trigger history
CREATE TABLE IF NOT EXISTS circuit_breaker_triggers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    breaker_type VARCHAR(50) NOT NULL,
    triggered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    threshold_value DECIMAL(10, 4) NOT NULL,
    actual_value DECIMAL(10, 4) NOT NULL,
    capital_at_trigger DECIMAL(20, 8) NOT NULL,
    peak_capital_at_trigger DECIMAL(20, 8) NOT NULL,
    reset_at TIMESTAMPTZ,
    reset_by VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_circuit_breaker_type ON circuit_breaker_triggers(breaker_type);
CREATE INDEX IF NOT EXISTS idx_circuit_breaker_active ON circuit_breaker_triggers(breaker_type)
    WHERE reset_at IS NULL;

-- Blocked signals due to circuit breakers
CREATE TABLE IF NOT EXISTS blocked_signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id VARCHAR(100) NOT NULL,
    blocked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    breaker_type VARCHAR(50) NOT NULL,
    reason TEXT NOT NULL,
    signal_data JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_blocked_signals_date ON blocked_signals(blocked_at DESC);

-- System configuration (key-value store) if not exists
CREATE TABLE IF NOT EXISTS system_config (
    key VARCHAR(100) PRIMARY KEY,
    value JSONB NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert default drawdown config
INSERT INTO system_config (key, value) VALUES
('drawdown_config', '{"threshold_percent": "20.0", "initial_capital": "1000.0"}'),
('system_status', '"running"')
ON CONFLICT (key) DO NOTHING;

-- Story 5-2: Consecutive Loss Position Reduction

-- Loss streak events for audit trail
CREATE TABLE IF NOT EXISTS loss_streak_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR(50) NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    consecutive_losses INTEGER NOT NULL,
    previous_mode VARCHAR(50) NOT NULL,
    new_mode VARCHAR(50) NOT NULL,
    previous_factor DECIMAL(5, 4) NOT NULL,
    new_factor DECIMAL(5, 4) NOT NULL,
    triggering_trade_id VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_loss_streak_events_date ON loss_streak_events(occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_loss_streak_events_type ON loss_streak_events(event_type);

-- Insert default consecutive loss config
INSERT INTO system_config (key, value) VALUES
('consecutive_loss_config', '{
    "reduction_threshold": 3,
    "reduction_factor": "0.5",
    "critical_threshold": 5,
    "critical_action": "pause",
    "further_reduction_factor": "0.25"
}'),
('consecutive_loss_state', '{
    "consecutive_loss_count": 0,
    "sizing_mode": "normal",
    "current_size_factor": "1.0",
    "last_trade_outcome": null,
    "streak_started_at": null
}')
ON CONFLICT (key) DO NOTHING;

-- Story 5-3: Win Rate Circuit Breaker

-- Win rate snapshots for historical tracking
CREATE TABLE IF NOT EXISTS win_rate_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    window_size INTEGER NOT NULL,
    trades_in_window INTEGER NOT NULL,
    winning_trades INTEGER NOT NULL,
    win_rate_percent DECIMAL(6, 2) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_win_rate_snapshots_timestamp ON win_rate_snapshots(timestamp DESC);

-- Insert default win rate config
INSERT INTO system_config (key, value) VALUES
('win_rate_config', '{
    "threshold_percent": "40.0",
    "window_size": 50,
    "minimum_trades": 20,
    "enable_caution_flag": true
}')
ON CONFLICT (key) DO NOTHING;

-- Story 5-4: Max Concurrent Position Limits

-- Queued signals awaiting execution
CREATE TABLE IF NOT EXISTS queued_signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id VARCHAR(100) NOT NULL,
    queued_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    signal_data JSONB DEFAULT '{}',
    priority INTEGER DEFAULT 0,
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_queued_signals_status ON queued_signals(status);
CREATE INDEX IF NOT EXISTS idx_queued_signals_expires ON queued_signals(expires_at) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_queued_signals_queued_at ON queued_signals(queued_at);

-- Position slot events for audit trail
CREATE TABLE IF NOT EXISTS position_slot_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR(50) NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    position_id VARCHAR(100),
    signal_id VARCHAR(100),
    queue_length_before INTEGER NOT NULL,
    queue_length_after INTEGER NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_position_slot_events_date ON position_slot_events(occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_position_slot_events_type ON position_slot_events(event_type);

-- Insert default position limit config
INSERT INTO system_config (key, value) VALUES
('position_limit_config', '{
    "max_positions": 5,
    "enable_queue": true,
    "max_queue_size": 10,
    "queue_expiry_minutes": 60
}')
ON CONFLICT (key) DO NOTHING;

-- Story 5-5: Circuit Breaker Alert System

-- System alerts table
CREATE TABLE IF NOT EXISTS alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_type VARCHAR(100) NOT NULL,
    severity VARCHAR(50) NOT NULL,
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    details JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status VARCHAR(50) NOT NULL DEFAULT 'new',
    acknowledged_at TIMESTAMPTZ,
    acknowledged_by VARCHAR(100),
    resolved_at TIMESTAMPTZ,
    related_trigger_id VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status);
CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity);
CREATE INDEX IF NOT EXISTS idx_alerts_created ON alerts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_type ON alerts(alert_type);
CREATE INDEX IF NOT EXISTS idx_alerts_active ON alerts(status) WHERE status IN ('new', 'acknowledged');

-- Story 5-6: Manual Pause/Resume Controls

-- Pause/resume events history
CREATE TABLE IF NOT EXISTS pause_resume_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR(50) NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    operator_id VARCHAR(100) NOT NULL,
    previous_status VARCHAR(50) NOT NULL,
    new_status VARCHAR(50) NOT NULL,
    reason VARCHAR(50),
    note TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pause_resume_events_date ON pause_resume_events(occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_pause_resume_events_type ON pause_resume_events(event_type);

-- Insert default system state
INSERT INTO system_config (key, value) VALUES
('system_state', '{
    "status": "running",
    "paused_at": null,
    "paused_by": null,
    "pause_reason": null,
    "pause_note": null,
    "resumed_at": null,
    "resumed_by": null
}')
ON CONFLICT (key) DO NOTHING;

-- Story 5-7: Dashboard Status & Risk Configuration

-- Config change log for audit trail
CREATE TABLE IF NOT EXISTS config_change_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    changed_by VARCHAR(100) NOT NULL,
    field_name VARCHAR(100) NOT NULL,
    previous_value TEXT NOT NULL,
    new_value TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_config_change_log_date ON config_change_log(changed_at DESC);
CREATE INDEX IF NOT EXISTS idx_config_change_log_field ON config_change_log(field_name);

-- Insert default risk config
INSERT INTO system_config (key, value) VALUES
('risk_config', '{
    "drawdown_threshold_percent": "20.0",
    "win_rate_threshold_percent": "40.0",
    "win_rate_window_size": 50,
    "consecutive_loss_threshold": 3,
    "consecutive_loss_critical": 5,
    "position_size_reduction": "0.5",
    "max_concurrent_positions": 5,
    "no_signal_warning_hours": 48
}'),
('webhook_status', '{"healthy": true, "last_check": null}')
ON CONFLICT (key) DO NOTHING;
-- Trade outcomes table for recording trade results
-- Story 6-1: Trade Outcome Recording

-- Trade outcomes table
CREATE TABLE trade_outcomes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    position_id UUID NOT NULL REFERENCES positions(id),
    signal_id UUID NOT NULL REFERENCES signals(id),
    wallet_address TEXT NOT NULL,
    token_address TEXT NOT NULL,
    token_symbol TEXT NOT NULL,
    entry_price DECIMAL(30, 18) NOT NULL,
    exit_price DECIMAL(30, 18) NOT NULL,
    amount_tokens DECIMAL(30, 18) NOT NULL,
    amount_sol DECIMAL(30, 18) NOT NULL,
    exit_reason TEXT NOT NULL CHECK (exit_reason IN (
        'stop_loss', 'take_profit', 'trailing_stop',
        'time_based', 'manual', 'circuit_breaker', 'partial_tp'
    )),
    signal_score DECIMAL(5, 4) NOT NULL,
    entry_timestamp TIMESTAMPTZ NOT NULL,
    exit_timestamp TIMESTAMPTZ NOT NULL,
    is_partial BOOLEAN DEFAULT FALSE,
    parent_trade_id UUID REFERENCES trade_outcomes(id),
    realized_pnl_sol DECIMAL(30, 18) NOT NULL,
    realized_pnl_percent DECIMAL(10, 4) NOT NULL,
    duration_seconds INTEGER NOT NULL,
    is_win BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for common queries (AC 4: Query Support)
CREATE INDEX idx_trade_outcomes_exit_timestamp ON trade_outcomes(exit_timestamp DESC);
CREATE INDEX idx_trade_outcomes_wallet ON trade_outcomes(wallet_address);
CREATE INDEX idx_trade_outcomes_token ON trade_outcomes(token_address);
CREATE INDEX idx_trade_outcomes_exit_reason ON trade_outcomes(exit_reason);
CREATE INDEX idx_trade_outcomes_position ON trade_outcomes(position_id);
CREATE INDEX idx_trade_outcomes_signal ON trade_outcomes(signal_id);
CREATE INDEX idx_trade_outcomes_parent ON trade_outcomes(parent_trade_id) WHERE parent_trade_id IS NOT NULL;
CREATE INDEX idx_trade_outcomes_is_win ON trade_outcomes(is_win);

-- Composite index for date range + wallet queries
CREATE INDEX idx_trade_outcomes_wallet_date ON trade_outcomes(wallet_address, exit_timestamp DESC);

-- Aggregate metrics table (singleton for running totals)
CREATE TABLE aggregate_metrics (
    id TEXT PRIMARY KEY DEFAULT 'current',
    total_pnl_sol DECIMAL(30, 18) DEFAULT 0,
    total_pnl_percent DECIMAL(10, 4) DEFAULT 0,
    win_count INTEGER DEFAULT 0,
    loss_count INTEGER DEFAULT 0,
    total_trades INTEGER DEFAULT 0,
    average_win_sol DECIMAL(30, 18) DEFAULT 0,
    average_loss_sol DECIMAL(30, 18) DEFAULT 0,
    largest_win_sol DECIMAL(30, 18) DEFAULT 0,
    largest_loss_sol DECIMAL(30, 18) DEFAULT 0,
    gross_profit DECIMAL(30, 18) DEFAULT 0,
    gross_loss DECIMAL(30, 18) DEFAULT 0,
    total_volume_sol DECIMAL(30, 18) DEFAULT 0,
    last_updated TIMESTAMPTZ DEFAULT NOW()
);

-- Initialize aggregate metrics
INSERT INTO aggregate_metrics (id) VALUES ('current');

-- Performance optimization for 1 year data (NFR22)
ALTER TABLE trade_outcomes SET (autovacuum_vacuum_scale_factor = 0.0);
ALTER TABLE trade_outcomes SET (autovacuum_vacuum_threshold = 5000);
-- Migration: 012_wallet_metrics
-- Description: Wallet metrics and score history tables for feedback loop
-- Story: 6-2 Wallet Score Updates

-- Wallet metrics table
CREATE TABLE IF NOT EXISTS wallet_metrics (
    wallet_address TEXT PRIMARY KEY,
    current_score DECIMAL(5, 4) NOT NULL DEFAULT 0.5,
    lifetime_trades INTEGER DEFAULT 0,
    lifetime_wins INTEGER DEFAULT 0,
    lifetime_losses INTEGER DEFAULT 0,
    lifetime_pnl DECIMAL(30, 18) DEFAULT 0,
    rolling_trades INTEGER DEFAULT 0,
    rolling_wins INTEGER DEFAULT 0,
    rolling_pnl DECIMAL(30, 18) DEFAULT 0,
    last_trade_timestamp TIMESTAMPTZ,
    last_score_update TIMESTAMPTZ DEFAULT NOW(),
    is_flagged BOOLEAN DEFAULT FALSE,
    is_blacklisted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for wallet metrics
CREATE INDEX IF NOT EXISTS idx_wallet_metrics_score ON wallet_metrics(current_score);
CREATE INDEX IF NOT EXISTS idx_wallet_metrics_flagged ON wallet_metrics(is_flagged) WHERE is_flagged = TRUE;
CREATE INDEX IF NOT EXISTS idx_wallet_metrics_blacklisted ON wallet_metrics(is_blacklisted) WHERE is_blacklisted = TRUE;
CREATE INDEX IF NOT EXISTS idx_wallet_metrics_last_trade ON wallet_metrics(last_trade_timestamp DESC);

-- Wallet score history table
CREATE TABLE IF NOT EXISTS wallet_score_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    wallet_address TEXT NOT NULL,
    score DECIMAL(5, 4) NOT NULL,
    previous_score DECIMAL(5, 4) NOT NULL,
    change DECIMAL(5, 4) NOT NULL,
    update_type TEXT NOT NULL CHECK (update_type IN (
        'trade_outcome', 'manual_adjustment', 'decay_penalty', 'recalibration'
    )),
    trade_id UUID,
    reason TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for score history
CREATE INDEX IF NOT EXISTS idx_score_history_wallet ON wallet_score_history(wallet_address);
CREATE INDEX IF NOT EXISTS idx_score_history_created ON wallet_score_history(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_score_history_trade ON wallet_score_history(trade_id) WHERE trade_id IS NOT NULL;

-- Score update configuration (singleton)
CREATE TABLE IF NOT EXISTS score_update_config (
    id TEXT PRIMARY KEY DEFAULT 'current',
    base_win_increase DECIMAL(5, 4) DEFAULT 0.02,
    profit_multiplier DECIMAL(5, 4) DEFAULT 0.01,
    max_win_increase DECIMAL(5, 4) DEFAULT 0.10,
    base_loss_decrease DECIMAL(5, 4) DEFAULT 0.03,
    loss_multiplier DECIMAL(5, 4) DEFAULT 0.015,
    max_loss_decrease DECIMAL(5, 4) DEFAULT 0.15,
    decay_flag_threshold DECIMAL(5, 4) DEFAULT 0.30,
    blacklist_threshold DECIMAL(5, 4) DEFAULT 0.15,
    rolling_window_trades INTEGER DEFAULT 20,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Initialize config if not exists
INSERT INTO score_update_config (id)
VALUES ('current')
ON CONFLICT (id) DO NOTHING;

-- Enable Row Level Security
ALTER TABLE wallet_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE wallet_score_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE score_update_config ENABLE ROW LEVEL SECURITY;

-- RLS Policies for service role access
CREATE POLICY "Service role full access to wallet_metrics"
    ON wallet_metrics FOR ALL
    USING (auth.role() = 'service_role');

CREATE POLICY "Service role full access to wallet_score_history"
    ON wallet_score_history FOR ALL
    USING (auth.role() = 'service_role');

CREATE POLICY "Service role full access to score_update_config"
    ON score_update_config FOR ALL
    USING (auth.role() = 'service_role');
-- Migration: 013_calibration
-- Description: Tables for scoring model calibration
-- Epic: 6 - Feedback Loop & Performance Analytics
-- Story: 6-3 - Scoring Model Recalibration

-- Calibration analyses
CREATE TABLE IF NOT EXISTS calibration_analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analyzed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    trade_count INTEGER NOT NULL DEFAULT 0,
    min_trades_required INTEGER NOT NULL DEFAULT 100,

    -- Current weights at time of analysis (JSONB)
    current_weights JSONB NOT NULL,

    -- Suggested weights based on analysis (JSONB)
    suggested_weights JSONB NOT NULL,

    -- Factor correlations (array of JSONB)
    correlations JSONB NOT NULL DEFAULT '[]'::jsonb,

    -- Estimated win rate improvement percentage
    estimated_improvement DECIMAL(5,2) NOT NULL DEFAULT 0,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for recent analyses
CREATE INDEX IF NOT EXISTS idx_calibration_analyses_analyzed_at
    ON calibration_analyses(analyzed_at DESC);


-- Calibration suggestions for operator review
CREATE TABLE IF NOT EXISTS calibration_suggestions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_id UUID NOT NULL REFERENCES calibration_analyses(id),

    -- Status: pending, approved, rejected, modified
    status VARCHAR(20) NOT NULL DEFAULT 'pending',

    -- Weight configurations (JSONB)
    current_weights JSONB NOT NULL,
    suggested_weights JSONB NOT NULL,

    -- Individual weight change suggestions (array of JSONB)
    suggestions JSONB NOT NULL DEFAULT '[]'::jsonb,

    -- Estimated improvement percentage
    estimated_improvement DECIMAL(5,2) NOT NULL DEFAULT 0,

    -- Application tracking
    applied_at TIMESTAMPTZ,
    applied_weights JSONB,
    operator_notes TEXT,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for pending suggestions
CREATE INDEX IF NOT EXISTS idx_calibration_suggestions_status
    ON calibration_suggestions(status) WHERE status = 'pending';

-- Index for analysis lookup
CREATE INDEX IF NOT EXISTS idx_calibration_suggestions_analysis_id
    ON calibration_suggestions(analysis_id);


-- Weight archive for historical tracking
CREATE TABLE IF NOT EXISTS weight_archives (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Weight configuration (JSONB)
    weights JSONB NOT NULL,

    -- Active period
    active_from TIMESTAMPTZ NOT NULL,
    active_until TIMESTAMPTZ NOT NULL,

    -- Associated suggestion if from calibration
    suggestion_id UUID REFERENCES calibration_suggestions(id),

    -- Performance during this weight period
    performance_during DECIMAL(5,2),

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for date range queries
CREATE INDEX IF NOT EXISTS idx_weight_archives_active_range
    ON weight_archives(active_from, active_until);


-- Current active weights (singleton row pattern)
CREATE TABLE IF NOT EXISTS scoring_weights (
    id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),  -- Singleton
    wallet_weight DECIMAL(4,3) NOT NULL DEFAULT 0.350,
    cluster_weight DECIMAL(4,3) NOT NULL DEFAULT 0.250,
    token_weight DECIMAL(4,3) NOT NULL DEFAULT 0.250,
    context_weight DECIMAL(4,3) NOT NULL DEFAULT 0.150,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by TEXT,

    -- Ensure weights sum to approximately 1
    CONSTRAINT weights_sum_check CHECK (
        ABS(wallet_weight + cluster_weight + token_weight + context_weight - 1.0) < 0.01
    )
);

-- Insert default weights
INSERT INTO scoring_weights (wallet_weight, cluster_weight, token_weight, context_weight)
VALUES (0.350, 0.250, 0.250, 0.150)
ON CONFLICT (id) DO NOTHING;


-- Auto-calibration configuration (singleton)
CREATE TABLE IF NOT EXISTS auto_calibration_config (
    id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),  -- Singleton
    enabled BOOLEAN NOT NULL DEFAULT FALSE,
    min_trades_between INTEGER NOT NULL DEFAULT 100,
    max_weight_change DECIMAL(4,3) NOT NULL DEFAULT 0.100,
    min_improvement_threshold DECIMAL(5,2) NOT NULL DEFAULT 2.0,
    log_all_changes BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Insert default config
INSERT INTO auto_calibration_config (enabled)
VALUES (FALSE)
ON CONFLICT (id) DO NOTHING;


-- Add updated_at trigger function if not exists
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply triggers
DROP TRIGGER IF EXISTS update_calibration_suggestions_updated_at ON calibration_suggestions;
CREATE TRIGGER update_calibration_suggestions_updated_at
    BEFORE UPDATE ON calibration_suggestions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_scoring_weights_updated_at ON scoring_weights;
CREATE TRIGGER update_scoring_weights_updated_at
    BEFORE UPDATE ON scoring_weights
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_auto_calibration_config_updated_at ON auto_calibration_config;
CREATE TRIGGER update_auto_calibration_config_updated_at
    BEFORE UPDATE ON auto_calibration_config
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();


-- RLS policies (assuming auth is set up)
ALTER TABLE calibration_analyses ENABLE ROW LEVEL SECURITY;
ALTER TABLE calibration_suggestions ENABLE ROW LEVEL SECURITY;
ALTER TABLE weight_archives ENABLE ROW LEVEL SECURITY;
ALTER TABLE scoring_weights ENABLE ROW LEVEL SECURITY;
ALTER TABLE auto_calibration_config ENABLE ROW LEVEL SECURITY;

-- Service role policies (for backend access)
CREATE POLICY calibration_analyses_service_all ON calibration_analyses
    FOR ALL USING (TRUE) WITH CHECK (TRUE);

CREATE POLICY calibration_suggestions_service_all ON calibration_suggestions
    FOR ALL USING (TRUE) WITH CHECK (TRUE);

CREATE POLICY weight_archives_service_all ON weight_archives
    FOR ALL USING (TRUE) WITH CHECK (TRUE);

CREATE POLICY scoring_weights_service_all ON scoring_weights
    FOR ALL USING (TRUE) WITH CHECK (TRUE);

CREATE POLICY auto_calibration_config_service_all ON auto_calibration_config
    FOR ALL USING (TRUE) WITH CHECK (TRUE);
-- Migration: Signal Accuracy Tracking
-- Created: 2025-12-20
-- Description: Tables for signal accuracy tracking, snapshots, and retrospective analysis

-- Accuracy snapshots for trend analysis
CREATE TABLE IF NOT EXISTS accuracy_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    signal_to_win_rate DECIMAL(5, 2) NOT NULL,
    signal_to_trade_rate DECIMAL(5, 2) NOT NULL DEFAULT 0,
    sample_size INTEGER NOT NULL DEFAULT 0,
    avg_signal_score DECIMAL(5, 4) NOT NULL DEFAULT 0,
    avg_score_winners DECIMAL(5, 4) NOT NULL DEFAULT 0,
    avg_score_losers DECIMAL(5, 4) NOT NULL DEFAULT 0,
    score_differential DECIMAL(5, 4) NOT NULL DEFAULT 0,
    optimal_threshold DECIMAL(5, 4) NOT NULL DEFAULT 0.6,
    total_signals INTEGER NOT NULL DEFAULT 0,
    traded_signals INTEGER NOT NULL DEFAULT 0,
    winning_trades INTEGER NOT NULL DEFAULT 0,
    losing_trades INTEGER NOT NULL DEFAULT 0,
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for time-based queries
CREATE INDEX IF NOT EXISTS idx_accuracy_snapshots_date
    ON accuracy_snapshots(snapshot_date DESC);

-- Threshold analyses for optimization
CREATE TABLE IF NOT EXISTS threshold_analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    threshold DECIMAL(5, 4) NOT NULL,
    would_trade_count INTEGER NOT NULL DEFAULT 0,
    would_win_count INTEGER NOT NULL DEFAULT 0,
    would_lose_count INTEGER NOT NULL DEFAULT 0,
    win_rate DECIMAL(5, 2) NOT NULL DEFAULT 0,
    total_pnl DECIMAL(20, 8) NOT NULL DEFAULT 0,
    profit_factor DECIMAL(10, 4) NOT NULL DEFAULT 0,
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for threshold lookups
CREATE INDEX IF NOT EXISTS idx_threshold_analyses_date
    ON threshold_analyses(analysis_date DESC);
CREATE INDEX IF NOT EXISTS idx_threshold_analyses_threshold
    ON threshold_analyses(threshold);

-- Factor accuracy breakdown
CREATE TABLE IF NOT EXISTS factor_accuracy (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    factor_name VARCHAR(100) NOT NULL,
    high_score_win_rate DECIMAL(5, 2) NOT NULL DEFAULT 0,
    low_score_win_rate DECIMAL(5, 2) NOT NULL DEFAULT 0,
    is_predictive BOOLEAN NOT NULL DEFAULT FALSE,
    correlation_with_outcome DECIMAL(6, 4) NOT NULL DEFAULT 0,
    recommended_weight_adjustment VARCHAR(20) NOT NULL DEFAULT 'none',
    sample_size INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for factor lookups
CREATE INDEX IF NOT EXISTS idx_factor_accuracy_date
    ON factor_accuracy(analysis_date DESC);
CREATE INDEX IF NOT EXISTS idx_factor_accuracy_factor
    ON factor_accuracy(factor_name);

-- Retrospective signal analysis
CREATE TABLE IF NOT EXISTS retrospective_signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id UUID NOT NULL,
    signal_score DECIMAL(5, 4) NOT NULL,
    token_address VARCHAR(64) NOT NULL,
    wallet_address VARCHAR(64) NOT NULL,
    signal_timestamp TIMESTAMPTZ NOT NULL,
    threshold_at_time DECIMAL(5, 4) NOT NULL,
    outcome VARCHAR(20) NOT NULL, -- missed_opportunity, bullet_dodged, uncertain
    estimated_pnl DECIMAL(20, 8),
    price_at_signal DECIMAL(30, 15),
    peak_price_after DECIMAL(30, 15),
    min_price_after DECIMAL(30, 15),
    window_hours INTEGER NOT NULL DEFAULT 24,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for retrospective analysis
CREATE INDEX IF NOT EXISTS idx_retrospective_signals_signal
    ON retrospective_signals(signal_id);
CREATE INDEX IF NOT EXISTS idx_retrospective_signals_date
    ON retrospective_signals(signal_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_retrospective_signals_outcome
    ON retrospective_signals(outcome);
CREATE INDEX IF NOT EXISTS idx_retrospective_signals_token
    ON retrospective_signals(token_address);

-- Retrospective analysis summaries
CREATE TABLE IF NOT EXISTS retrospective_summaries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    window_hours INTEGER NOT NULL DEFAULT 24,
    total_non_traded INTEGER NOT NULL DEFAULT 0,
    missed_opportunities INTEGER NOT NULL DEFAULT 0,
    bullets_dodged INTEGER NOT NULL DEFAULT 0,
    uncertain INTEGER NOT NULL DEFAULT 0,
    total_missed_pnl DECIMAL(20, 8) NOT NULL DEFAULT 0,
    total_avoided_loss DECIMAL(20, 8) NOT NULL DEFAULT 0,
    net_impact DECIMAL(20, 8) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for summary lookups
CREATE INDEX IF NOT EXISTS idx_retrospective_summaries_date
    ON retrospective_summaries(period_start DESC, period_end DESC);

-- RLS policies
ALTER TABLE accuracy_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE threshold_analyses ENABLE ROW LEVEL SECURITY;
ALTER TABLE factor_accuracy ENABLE ROW LEVEL SECURITY;
ALTER TABLE retrospective_signals ENABLE ROW LEVEL SECURITY;
ALTER TABLE retrospective_summaries ENABLE ROW LEVEL SECURITY;

-- Service role access policies
CREATE POLICY accuracy_snapshots_service_policy ON accuracy_snapshots
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY threshold_analyses_service_policy ON threshold_analyses
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY factor_accuracy_service_policy ON factor_accuracy
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY retrospective_signals_service_policy ON retrospective_signals
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY retrospective_summaries_service_policy ON retrospective_summaries
    FOR ALL USING (true) WITH CHECK (true);

-- Cleanup function for old snapshots (keep 90 days)
CREATE OR REPLACE FUNCTION cleanup_old_accuracy_data()
RETURNS void AS $$
BEGIN
    DELETE FROM accuracy_snapshots WHERE snapshot_date < NOW() - INTERVAL '90 days';
    DELETE FROM threshold_analyses WHERE analysis_date < NOW() - INTERVAL '30 days';
    DELETE FROM factor_accuracy WHERE analysis_date < NOW() - INTERVAL '30 days';
    DELETE FROM retrospective_signals WHERE created_at < NOW() - INTERVAL '30 days';
    DELETE FROM retrospective_summaries WHERE created_at < NOW() - INTERVAL '90 days';
END;
$$ LANGUAGE plpgsql;

COMMENT ON TABLE accuracy_snapshots IS 'Point-in-time accuracy metrics for trend analysis';
COMMENT ON TABLE threshold_analyses IS 'Analysis of different threshold effectiveness';
COMMENT ON TABLE factor_accuracy IS 'Accuracy breakdown by scoring factor';
COMMENT ON TABLE retrospective_signals IS 'Retrospective analysis of non-traded signals';
COMMENT ON TABLE retrospective_summaries IS 'Aggregated retrospective analysis summaries';
-- Migration: Pattern Analysis
-- Description: Tables for pattern analysis and insights (Story 6-5)
-- Created: 2025-12-20

-- Pattern analyses table stores analysis results
CREATE TABLE IF NOT EXISTS pattern_analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analyzed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    trade_count INTEGER NOT NULL,
    baseline_win_rate DECIMAL(5, 2) NOT NULL,
    patterns JSONB NOT NULL DEFAULT '[]',
    time_patterns JSONB NOT NULL DEFAULT '[]',
    wallet_patterns JSONB NOT NULL DEFAULT '[]',
    token_patterns JSONB NOT NULL DEFAULT '[]',
    cluster_patterns JSONB NOT NULL DEFAULT '[]',
    top_positive_patterns JSONB NOT NULL DEFAULT '[]',
    top_negative_patterns JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Pattern alerts table for significant pattern notifications
CREATE TABLE IF NOT EXISTS pattern_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pattern_id UUID NOT NULL,
    pattern_type VARCHAR(50) NOT NULL,
    pattern_name VARCHAR(255) NOT NULL,
    sentiment VARCHAR(20) NOT NULL CHECK (sentiment IN ('positive', 'negative', 'neutral')),
    message TEXT NOT NULL,
    suggested_action TEXT NOT NULL,
    acknowledged BOOLEAN NOT NULL DEFAULT FALSE,
    acknowledged_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_pattern_analyses_analyzed_at
    ON pattern_analyses(analyzed_at DESC);

CREATE INDEX IF NOT EXISTS idx_pattern_alerts_acknowledged
    ON pattern_alerts(acknowledged) WHERE acknowledged = FALSE;

CREATE INDEX IF NOT EXISTS idx_pattern_alerts_created_at
    ON pattern_alerts(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_pattern_alerts_pattern_type
    ON pattern_alerts(pattern_type);

CREATE INDEX IF NOT EXISTS idx_pattern_alerts_sentiment
    ON pattern_alerts(sentiment);

-- Enable Row Level Security
ALTER TABLE pattern_analyses ENABLE ROW LEVEL SECURITY;
ALTER TABLE pattern_alerts ENABLE ROW LEVEL SECURITY;

-- RLS policies for pattern_analyses
CREATE POLICY pattern_analyses_select_policy ON pattern_analyses
    FOR SELECT USING (true);

CREATE POLICY pattern_analyses_insert_policy ON pattern_analyses
    FOR INSERT WITH CHECK (true);

CREATE POLICY pattern_analyses_update_policy ON pattern_analyses
    FOR UPDATE USING (true);

-- RLS policies for pattern_alerts
CREATE POLICY pattern_alerts_select_policy ON pattern_alerts
    FOR SELECT USING (true);

CREATE POLICY pattern_alerts_insert_policy ON pattern_alerts
    FOR INSERT WITH CHECK (true);

CREATE POLICY pattern_alerts_update_policy ON pattern_alerts
    FOR UPDATE USING (true);

-- Function to cleanup old pattern analyses (keep last 30 days)
CREATE OR REPLACE FUNCTION cleanup_old_pattern_analyses()
RETURNS void AS $$
BEGIN
    DELETE FROM pattern_analyses
    WHERE analyzed_at < NOW() - INTERVAL '30 days';
END;
$$ LANGUAGE plpgsql;

-- Function to cleanup acknowledged alerts older than 7 days
CREATE OR REPLACE FUNCTION cleanup_acknowledged_alerts()
RETURNS void AS $$
BEGIN
    DELETE FROM pattern_alerts
    WHERE acknowledged = TRUE
    AND acknowledged_at < NOW() - INTERVAL '7 days';
END;
$$ LANGUAGE plpgsql;

-- Trigger to set acknowledged_at when alert is acknowledged
CREATE OR REPLACE FUNCTION set_acknowledged_at()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.acknowledged = TRUE AND OLD.acknowledged = FALSE THEN
        NEW.acknowledged_at = NOW();
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_set_acknowledged_at
    BEFORE UPDATE ON pattern_alerts
    FOR EACH ROW
    EXECUTE FUNCTION set_acknowledged_at();

-- Comments for documentation
COMMENT ON TABLE pattern_analyses IS 'Stores results of pattern analysis runs';
COMMENT ON TABLE pattern_alerts IS 'Alerts generated for significant trading patterns';
COMMENT ON COLUMN pattern_analyses.patterns IS 'JSON array of all identified Pattern objects';
COMMENT ON COLUMN pattern_analyses.top_positive_patterns IS 'Top patterns correlated with success';
COMMENT ON COLUMN pattern_analyses.top_negative_patterns IS 'Top patterns correlated with failure';
COMMENT ON COLUMN pattern_alerts.acknowledged IS 'Whether the alert has been reviewed by user';
-- Performance Analytics Migration
-- Materialized views and indexes for fast dashboard queries
-- Story 6-6: Dashboard Performance Analytics

-- =====================================================
-- Materialized View: Daily PnL Aggregation
-- =====================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_daily_pnl_summary AS
SELECT
    DATE(closed_at) AS trade_date,
    COUNT(*) AS trade_count,
    SUM(CASE WHEN pnl_sol > 0 THEN 1 ELSE 0 END) AS winning_trades,
    SUM(CASE WHEN pnl_sol < 0 THEN 1 ELSE 0 END) AS losing_trades,
    SUM(pnl_sol) AS total_pnl_sol,
    SUM(CASE WHEN pnl_sol > 0 THEN pnl_sol ELSE 0 END) AS gross_profit_sol,
    SUM(CASE WHEN pnl_sol < 0 THEN ABS(pnl_sol) ELSE 0 END) AS gross_loss_sol,
    AVG(CASE WHEN pnl_sol > 0 THEN pnl_sol END) AS avg_win_sol,
    AVG(CASE WHEN pnl_sol < 0 THEN ABS(pnl_sol) END) AS avg_loss_sol,
    AVG(EXTRACT(EPOCH FROM (closed_at - created_at))) AS avg_duration_seconds
FROM trades
WHERE status = 'closed' AND closed_at IS NOT NULL
GROUP BY DATE(closed_at)
ORDER BY trade_date;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_daily_pnl_trade_date
ON mv_daily_pnl_summary (trade_date);

-- =====================================================
-- Materialized View: Wallet Performance Summary
-- =====================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_wallet_performance AS
SELECT
    source_wallet_id,
    COUNT(*) AS trade_count,
    SUM(CASE WHEN pnl_sol > 0 THEN 1 ELSE 0 END) AS winning_trades,
    SUM(pnl_sol) AS total_pnl_sol,
    CASE
        WHEN COUNT(*) > 0
        THEN ROUND((SUM(CASE WHEN pnl_sol > 0 THEN 1 ELSE 0 END)::NUMERIC / COUNT(*)) * 100, 2)
        ELSE 0
    END AS win_rate,
    CASE
        WHEN COUNT(*) > 0
        THEN ROUND(SUM(pnl_sol) / COUNT(*), 6)
        ELSE 0
    END AS avg_pnl_sol,
    MIN(closed_at) AS first_trade_at,
    MAX(closed_at) AS last_trade_at
FROM trades
WHERE status = 'closed' AND closed_at IS NOT NULL
GROUP BY source_wallet_id;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_wallet_perf_wallet
ON mv_wallet_performance (source_wallet_id);

-- =====================================================
-- Materialized View: Exit Strategy Performance
-- =====================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_exit_strategy_performance AS
SELECT
    exit_strategy_id,
    exit_type,
    COUNT(*) AS trade_count,
    SUM(CASE WHEN pnl_sol > 0 THEN 1 ELSE 0 END) AS winning_trades,
    SUM(pnl_sol) AS total_pnl_sol,
    CASE
        WHEN COUNT(*) > 0
        THEN ROUND((SUM(CASE WHEN pnl_sol > 0 THEN 1 ELSE 0 END)::NUMERIC / COUNT(*)) * 100, 2)
        ELSE 0
    END AS win_rate,
    CASE
        WHEN COUNT(*) > 0
        THEN ROUND(SUM(pnl_sol) / COUNT(*), 6)
        ELSE 0
    END AS avg_pnl_sol
FROM trades
WHERE status = 'closed' AND closed_at IS NOT NULL
GROUP BY exit_strategy_id, exit_type;

CREATE INDEX IF NOT EXISTS idx_mv_exit_strategy_perf_strategy
ON mv_exit_strategy_performance (exit_strategy_id);

CREATE INDEX IF NOT EXISTS idx_mv_exit_strategy_perf_type
ON mv_exit_strategy_performance (exit_type);

-- =====================================================
-- Materialized View: Time-of-Day Performance
-- =====================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_time_of_day_performance AS
SELECT
    CASE
        WHEN EXTRACT(HOUR FROM closed_at) BETWEEN 0 AND 5 THEN 'night'
        WHEN EXTRACT(HOUR FROM closed_at) BETWEEN 6 AND 11 THEN 'morning'
        WHEN EXTRACT(HOUR FROM closed_at) BETWEEN 12 AND 17 THEN 'afternoon'
        ELSE 'evening'
    END AS time_period,
    COUNT(*) AS trade_count,
    SUM(CASE WHEN pnl_sol > 0 THEN 1 ELSE 0 END) AS winning_trades,
    SUM(pnl_sol) AS total_pnl_sol,
    CASE
        WHEN COUNT(*) > 0
        THEN ROUND((SUM(CASE WHEN pnl_sol > 0 THEN 1 ELSE 0 END)::NUMERIC / COUNT(*)) * 100, 2)
        ELSE 0
    END AS win_rate,
    CASE
        WHEN COUNT(*) > 0
        THEN ROUND(SUM(pnl_sol) / COUNT(*), 6)
        ELSE 0
    END AS avg_pnl_sol
FROM trades
WHERE status = 'closed' AND closed_at IS NOT NULL
GROUP BY time_period;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_time_of_day_period
ON mv_time_of_day_performance (time_period);

-- =====================================================
-- Materialized View: Day-of-Week Performance
-- =====================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_day_of_week_performance AS
SELECT
    EXTRACT(DOW FROM closed_at) AS day_of_week,
    TO_CHAR(closed_at, 'Day') AS day_name,
    COUNT(*) AS trade_count,
    SUM(CASE WHEN pnl_sol > 0 THEN 1 ELSE 0 END) AS winning_trades,
    SUM(pnl_sol) AS total_pnl_sol,
    CASE
        WHEN COUNT(*) > 0
        THEN ROUND((SUM(CASE WHEN pnl_sol > 0 THEN 1 ELSE 0 END)::NUMERIC / COUNT(*)) * 100, 2)
        ELSE 0
    END AS win_rate,
    CASE
        WHEN COUNT(*) > 0
        THEN ROUND(SUM(pnl_sol) / COUNT(*), 6)
        ELSE 0
    END AS avg_pnl_sol
FROM trades
WHERE status = 'closed' AND closed_at IS NOT NULL
GROUP BY day_of_week, day_name
ORDER BY day_of_week;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_day_of_week_dow
ON mv_day_of_week_performance (day_of_week);

-- =====================================================
-- Function: Refresh All Performance Materialized Views
-- =====================================================
CREATE OR REPLACE FUNCTION refresh_performance_views()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_daily_pnl_summary;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_wallet_performance;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_exit_strategy_performance;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_time_of_day_performance;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_day_of_week_performance;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- Indexes on trades table for performance queries
-- =====================================================
CREATE INDEX IF NOT EXISTS idx_trades_closed_at_pnl
ON trades (closed_at, pnl_sol)
WHERE status = 'closed' AND closed_at IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_trades_source_wallet_closed
ON trades (source_wallet_id, closed_at)
WHERE status = 'closed';

CREATE INDEX IF NOT EXISTS idx_trades_exit_strategy_closed
ON trades (exit_strategy_id, closed_at)
WHERE status = 'closed';

-- =====================================================
-- Table: Performance Dashboard Cache
-- =====================================================
CREATE TABLE IF NOT EXISTS performance_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cache_key TEXT UNIQUE NOT NULL,
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_performance_cache_key
ON performance_cache (cache_key);

CREATE INDEX IF NOT EXISTS idx_performance_cache_expires
ON performance_cache (expires_at);

-- Function to clean expired cache entries
CREATE OR REPLACE FUNCTION cleanup_performance_cache()
RETURNS void AS $$
BEGIN
    DELETE FROM performance_cache WHERE expires_at < NOW();
END;
$$ LANGUAGE plpgsql;

-- RLS Policy for performance cache (service account only)
ALTER TABLE performance_cache ENABLE ROW LEVEL SECURITY;

CREATE POLICY performance_cache_service_policy ON performance_cache
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- =====================================================
-- Comment on objects
-- =====================================================
COMMENT ON MATERIALIZED VIEW mv_daily_pnl_summary IS 'Daily aggregated PnL metrics for performance dashboard';
COMMENT ON MATERIALIZED VIEW mv_wallet_performance IS 'Per-wallet performance aggregation';
COMMENT ON MATERIALIZED VIEW mv_exit_strategy_performance IS 'Performance breakdown by exit strategy';
COMMENT ON MATERIALIZED VIEW mv_time_of_day_performance IS 'Performance breakdown by time of day';
COMMENT ON MATERIALIZED VIEW mv_day_of_week_performance IS 'Performance breakdown by day of week';
COMMENT ON TABLE performance_cache IS 'Server-side cache for dashboard data';
COMMENT ON FUNCTION refresh_performance_views() IS 'Refresh all performance materialized views concurrently';
COMMENT ON FUNCTION cleanup_performance_cache() IS 'Remove expired cache entries';
-- Migration: 017_backtest.sql
-- Description: Backtest preview tables for parameter optimization
-- Epic 6, Story 6-7: Backtest Preview

-- ============================================================================
-- BACKTEST RESULTS TABLE
-- ============================================================================
-- Stores completed backtest runs with configuration and results

CREATE TABLE IF NOT EXISTS backtest_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    config JSONB NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    duration_seconds INTEGER,
    total_signals_analyzed INTEGER DEFAULT 0,
    signals_above_threshold INTEGER DEFAULT 0,
    metrics_comparison JSONB,
    simulated_trades JSONB DEFAULT '[]'::jsonb,
    trade_comparisons JSONB DEFAULT '[]'::jsonb,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT valid_status CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    CONSTRAINT valid_dates CHECK (completed_at IS NULL OR completed_at >= started_at)
);

-- Index for querying recent backtests
CREATE INDEX IF NOT EXISTS idx_backtest_results_started_at
ON backtest_results(started_at DESC);

-- Index for filtering by status
CREATE INDEX IF NOT EXISTS idx_backtest_results_status
ON backtest_results(status);

-- ============================================================================
-- SIGNAL CACHE TABLE
-- ============================================================================
-- Caches historical signals for faster backtest execution

CREATE TABLE IF NOT EXISTS signal_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cache_key VARCHAR(255) NOT NULL UNIQUE,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    signals JSONB NOT NULL DEFAULT '[]'::jsonb,
    signal_count INTEGER NOT NULL DEFAULT 0,
    cached_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT valid_date_range CHECK (end_date >= start_date)
);

-- Index for cache lookup
CREATE INDEX IF NOT EXISTS idx_signal_cache_key
ON signal_cache(cache_key);

-- Index for cache expiry cleanup
CREATE INDEX IF NOT EXISTS idx_signal_cache_expires
ON signal_cache(expires_at);

-- ============================================================================
-- TOKEN PRICE HISTORY TABLE
-- ============================================================================
-- Stores historical price data for tokens (for backtest simulations)

CREATE TABLE IF NOT EXISTS token_price_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token_address VARCHAR(44) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    price_usd DECIMAL(30, 18) NOT NULL,
    price_sol DECIMAL(30, 18),
    volume_24h DECIMAL(30, 2),
    liquidity_usd DECIMAL(30, 2),
    source VARCHAR(50) DEFAULT 'dexscreener',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT unique_token_price UNIQUE (token_address, timestamp, source)
);

-- Index for price lookups by token and time range
CREATE INDEX IF NOT EXISTS idx_token_price_history_lookup
ON token_price_history(token_address, timestamp DESC);

-- Index for time-based queries
CREATE INDEX IF NOT EXISTS idx_token_price_history_timestamp
ON token_price_history(timestamp DESC);

-- ============================================================================
-- APPLIED SETTINGS HISTORY TABLE
-- ============================================================================
-- Tracks when backtest settings are applied to production

CREATE TABLE IF NOT EXISTS applied_settings_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    backtest_id UUID NOT NULL REFERENCES backtest_results(id),
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    changes_applied JSONB NOT NULL DEFAULT '[]'::jsonb,
    previous_values JSONB NOT NULL DEFAULT '{}'::jsonb,
    applied_by VARCHAR(100),
    rollback_at TIMESTAMPTZ,
    rollback_reason TEXT,

    CONSTRAINT fk_backtest FOREIGN KEY (backtest_id)
        REFERENCES backtest_results(id) ON DELETE CASCADE
);

-- Index for finding settings by backtest
CREATE INDEX IF NOT EXISTS idx_applied_settings_backtest
ON applied_settings_history(backtest_id);

-- Index for chronological queries
CREATE INDEX IF NOT EXISTS idx_applied_settings_applied_at
ON applied_settings_history(applied_at DESC);

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Function to clean expired signal cache entries
CREATE OR REPLACE FUNCTION cleanup_expired_signal_cache()
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM signal_cache
    WHERE expires_at < NOW();

    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$;

-- Function to get or create cache entry
CREATE OR REPLACE FUNCTION get_or_create_signal_cache(
    p_cache_key VARCHAR(255),
    p_start_date DATE,
    p_end_date DATE,
    p_ttl_minutes INTEGER DEFAULT 30
)
RETURNS TABLE (
    cache_id UUID,
    is_fresh BOOLEAN,
    signals JSONB
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_cache_id UUID;
    v_signals JSONB;
    v_is_fresh BOOLEAN;
BEGIN
    -- Try to get existing valid cache
    SELECT sc.id, sc.signals, (sc.expires_at > NOW()) INTO v_cache_id, v_signals, v_is_fresh
    FROM signal_cache sc
    WHERE sc.cache_key = p_cache_key
    LIMIT 1;

    IF v_cache_id IS NOT NULL AND v_is_fresh THEN
        RETURN QUERY SELECT v_cache_id, TRUE, v_signals;
    ELSE
        -- Create new cache entry (signals will be populated by application)
        INSERT INTO signal_cache (cache_key, start_date, end_date, signals, expires_at)
        VALUES (
            p_cache_key,
            p_start_date,
            p_end_date,
            '[]'::jsonb,
            NOW() + (p_ttl_minutes || ' minutes')::interval
        )
        ON CONFLICT (cache_key) DO UPDATE SET
            expires_at = NOW() + (p_ttl_minutes || ' minutes')::interval,
            cached_at = NOW()
        RETURNING id INTO v_cache_id;

        RETURN QUERY SELECT v_cache_id, FALSE, '[]'::jsonb;
    END IF;
END;
$$;

-- Function to update backtest progress
CREATE OR REPLACE FUNCTION update_backtest_progress(
    p_backtest_id UUID,
    p_status VARCHAR(20),
    p_signals_analyzed INTEGER DEFAULT NULL,
    p_signals_above_threshold INTEGER DEFAULT NULL,
    p_error_message TEXT DEFAULT NULL
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE backtest_results
    SET
        status = p_status,
        total_signals_analyzed = COALESCE(p_signals_analyzed, total_signals_analyzed),
        signals_above_threshold = COALESCE(p_signals_above_threshold, signals_above_threshold),
        error_message = COALESCE(p_error_message, error_message),
        completed_at = CASE WHEN p_status IN ('completed', 'failed', 'cancelled') THEN NOW() ELSE completed_at END,
        duration_seconds = CASE
            WHEN p_status IN ('completed', 'failed', 'cancelled')
            THEN EXTRACT(EPOCH FROM (NOW() - started_at))::INTEGER
            ELSE duration_seconds
        END,
        updated_at = NOW()
    WHERE id = p_backtest_id;
END;
$$;

-- ============================================================================
-- ROW LEVEL SECURITY (RLS)
-- ============================================================================

ALTER TABLE backtest_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE signal_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE token_price_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE applied_settings_history ENABLE ROW LEVEL SECURITY;

-- Allow authenticated users full access (single-user system)
CREATE POLICY backtest_results_policy ON backtest_results
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY signal_cache_policy ON signal_cache
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY token_price_history_policy ON token_price_history
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY applied_settings_policy ON applied_settings_history
    FOR ALL USING (true) WITH CHECK (true);

-- ============================================================================
-- TRIGGERS
-- ============================================================================

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_backtest_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_backtest_results_updated_at
    BEFORE UPDATE ON backtest_results
    FOR EACH ROW
    EXECUTE FUNCTION update_backtest_updated_at();

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE backtest_results IS 'Stores backtest run configurations and results';
COMMENT ON TABLE signal_cache IS 'Caches historical signals for faster backtest execution';
COMMENT ON TABLE token_price_history IS 'Historical price data for backtest simulations';
COMMENT ON TABLE applied_settings_history IS 'Audit trail of settings applied from backtests';

COMMENT ON FUNCTION cleanup_expired_signal_cache() IS 'Removes expired cache entries';
COMMENT ON FUNCTION get_or_create_signal_cache(VARCHAR, DATE, DATE, INTEGER) IS 'Gets existing cache or creates placeholder';
COMMENT ON FUNCTION update_backtest_progress(UUID, VARCHAR, INTEGER, INTEGER, TEXT) IS 'Updates backtest status and metrics';
