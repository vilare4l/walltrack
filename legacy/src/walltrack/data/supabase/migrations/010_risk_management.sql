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
