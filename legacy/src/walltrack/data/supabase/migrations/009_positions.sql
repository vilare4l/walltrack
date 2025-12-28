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
