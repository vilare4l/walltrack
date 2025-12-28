-- =============================================================================
-- WallTrack - Apply Missing Tables
-- =============================================================================
-- Run this in Supabase SQL Editor
-- Tables that exist: wallets, signals, positions, position_sizing_config,
--                    exit_strategies, discovery_runs, discovery_config, config
-- Tables missing: webhook_logs, exit_executions, system_config, capital_snapshots,
--                 and other risk management tables
-- =============================================================================

-- Set search path to walltrack schema
SET search_path TO walltrack, public;

-- =============================================================================
-- 1. webhook_logs - For tracking Helius webhook events
-- =============================================================================
CREATE TABLE IF NOT EXISTS walltrack.webhook_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tx_signature VARCHAR(100) NOT NULL UNIQUE,
    wallet_address VARCHAR(50) NOT NULL,
    token_address VARCHAR(50) NOT NULL,
    direction VARCHAR(10) NOT NULL CHECK (direction IN ('buy', 'sell')),
    amount_token DECIMAL(30, 10) NOT NULL,
    amount_sol DECIMAL(20, 10) NOT NULL,
    slot BIGINT NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processing_started_at TIMESTAMPTZ,
    processing_completed_at TIMESTAMPTZ,
    processing_time_ms DECIMAL(10, 2),
    status VARCHAR(20) NOT NULL DEFAULT 'received' CHECK (status IN ('received', 'processing', 'completed', 'failed')),
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_webhook_logs_received_at ON walltrack.webhook_logs(received_at DESC);
CREATE INDEX IF NOT EXISTS idx_webhook_logs_wallet ON walltrack.webhook_logs(wallet_address);
CREATE INDEX IF NOT EXISTS idx_webhook_logs_status ON walltrack.webhook_logs(status);

-- =============================================================================
-- 2. exit_executions - For tracking position exits
-- =============================================================================
CREATE TABLE IF NOT EXISTS walltrack.exit_executions (
    id TEXT PRIMARY KEY,
    position_id TEXT NOT NULL,
    exit_reason TEXT NOT NULL,
    trigger_level TEXT NOT NULL,
    sell_percentage DECIMAL(5, 2) NOT NULL,
    amount_tokens_sold DECIMAL(30, 0) NOT NULL,
    amount_sol_received DECIMAL(20, 9) NOT NULL,
    exit_price DECIMAL(30, 18) NOT NULL,
    tx_signature TEXT NOT NULL,
    realized_pnl_sol DECIMAL(20, 9) NOT NULL,
    executed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT valid_exit_execution_reason CHECK (exit_reason IN (
        'stop_loss', 'take_profit', 'trailing_stop', 'time_limit',
        'stagnation', 'manual', 'moonbag_stop'
    ))
);

CREATE INDEX IF NOT EXISTS idx_exit_executions_position ON walltrack.exit_executions(position_id);
CREATE INDEX IF NOT EXISTS idx_exit_executions_time ON walltrack.exit_executions(executed_at DESC);

-- =============================================================================
-- 3. system_config - Key-value store for system configuration
-- =============================================================================
CREATE TABLE IF NOT EXISTS walltrack.system_config (
    key VARCHAR(100) PRIMARY KEY,
    value JSONB NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert default configs
INSERT INTO walltrack.system_config (key, value) VALUES
('system_status', '"running"'),
('drawdown_config', '{"threshold_percent": "20.0", "initial_capital": "1000.0"}'),
('risk_config', '{
    "drawdown_threshold_percent": "20.0",
    "win_rate_threshold_percent": "40.0",
    "win_rate_window_size": 50,
    "consecutive_loss_threshold": 3,
    "max_concurrent_positions": 5
}'),
('consecutive_loss_state', '{
    "consecutive_loss_count": 0,
    "sizing_mode": "normal",
    "current_size_factor": "1.0"
}'),
('webhook_status', '{"healthy": true, "last_check": null}')
ON CONFLICT (key) DO NOTHING;

-- =============================================================================
-- 4. capital_snapshots - For tracking capital and drawdown
-- =============================================================================
CREATE TABLE IF NOT EXISTS walltrack.capital_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    capital DECIMAL(20, 8) NOT NULL,
    peak_capital DECIMAL(20, 8) NOT NULL,
    drawdown_percent DECIMAL(10, 4) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_capital_snapshots_timestamp ON walltrack.capital_snapshots(timestamp DESC);

-- =============================================================================
-- 5. alerts - System alerts
-- =============================================================================
CREATE TABLE IF NOT EXISTS walltrack.alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_type VARCHAR(100) NOT NULL,
    severity VARCHAR(50) NOT NULL,
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    details JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status VARCHAR(50) NOT NULL DEFAULT 'new',
    acknowledged_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_alerts_status ON walltrack.alerts(status);
CREATE INDEX IF NOT EXISTS idx_alerts_created ON walltrack.alerts(created_at DESC);

-- =============================================================================
-- 6. circuit_breaker_triggers - Risk management triggers
-- =============================================================================
CREATE TABLE IF NOT EXISTS walltrack.circuit_breaker_triggers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    breaker_type VARCHAR(50) NOT NULL,
    triggered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    threshold_value DECIMAL(10, 4) NOT NULL,
    actual_value DECIMAL(10, 4) NOT NULL,
    reset_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_circuit_breaker_type ON walltrack.circuit_breaker_triggers(breaker_type);

-- =============================================================================
-- 7. Insert default exit strategy
-- =============================================================================
INSERT INTO walltrack.exit_strategies (id, name, description, is_active, is_default, config, created_at, updated_at)
VALUES (
    'default-exit-strategy',
    'Default Strategy',
    'Standard exit strategy with 3 take-profit levels',
    true,
    true,
    '{
        "stop_loss_percent": 50,
        "take_profit_levels": [
            {"multiplier": 2.0, "sell_percent": 33},
            {"multiplier": 3.0, "sell_percent": 33},
            {"multiplier": 5.0, "sell_percent": 34}
        ],
        "trailing_stop": {
            "activation_multiplier": 2.0,
            "distance_percent": 30
        },
        "moonbag_percent": 0
    }'::jsonb,
    NOW(),
    NOW()
)
ON CONFLICT (id) DO NOTHING;

-- =============================================================================
-- 8. Insert default position sizing config
-- =============================================================================
INSERT INTO walltrack.position_sizing_config (id, name, description, is_active, is_default, config, created_at, updated_at)
VALUES (
    'default-sizing',
    'Default Sizing',
    'Standard position sizing based on conviction',
    true,
    true,
    '{
        "base_size_sol": 0.1,
        "max_size_sol": 0.5,
        "high_conviction_multiplier": 1.5,
        "standard_multiplier": 1.0,
        "score_threshold": 0.70,
        "high_conviction_threshold": 0.85
    }'::jsonb,
    NOW(),
    NOW()
)
ON CONFLICT (id) DO NOTHING;

-- =============================================================================
-- Verify tables created
-- =============================================================================
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'walltrack'
ORDER BY table_name;
