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
