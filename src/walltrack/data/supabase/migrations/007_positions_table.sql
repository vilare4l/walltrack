-- ============================================================================
-- Migration: 007_positions_table.sql (Aggregate Root Pattern)
-- ============================================================================

CREATE TABLE IF NOT EXISTS walltrack.positions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Relations
    wallet_id UUID NOT NULL REFERENCES walltrack.wallets(id) ON DELETE CASCADE,
    token_id UUID NOT NULL REFERENCES walltrack.tokens(id),
    signal_id UUID REFERENCES walltrack.signals(id),

    -- Config
    mode TEXT NOT NULL CHECK (mode IN ('simulation', 'live')),

    -- Entry (immutable)
    entry_price NUMERIC(20,10) NOT NULL,
    entry_amount NUMERIC(20,6) NOT NULL,
    entry_value_usd NUMERIC(12,2) NOT NULL,
    entry_timestamp TIMESTAMPTZ DEFAULT NOW(),
    entry_tx_signature TEXT,

    -- Current
    current_amount NUMERIC(20,6) NOT NULL,  -- Decremented on partial exits
    current_price NUMERIC(20,10),
    current_value_usd NUMERIC(12,2),
    current_pnl_usd NUMERIC(12,2),
    current_pnl_percent NUMERIC(8,4),
    peak_price NUMERIC(20,10),  -- For trailing stop
    peak_value_usd NUMERIC(12,2),
    last_price_update_at TIMESTAMPTZ,

    -- PnL (Realized vs Unrealized)
    unrealized_pnl_usd NUMERIC(12,2),
    unrealized_pnl_percent NUMERIC(8,4),
    realized_pnl_usd NUMERIC(12,2),
    realized_pnl_percent NUMERIC(8,4),

    -- Exit
    exit_price NUMERIC(20,10),  -- Weighted average of all exits
    exit_amount NUMERIC(20,6),
    exit_value_usd NUMERIC(12,2),
    exit_timestamp TIMESTAMPTZ,
    exit_tx_signature TEXT,
    exit_reason TEXT,  -- 'stop_loss', 'trailing_stop', 'scaling_out', 'mirror_exit', 'manual'

    -- Strategy (snapshot immutable)
    exit_strategy_id UUID NOT NULL REFERENCES walltrack.exit_strategies(id),
    exit_strategy_override JSONB,

    -- Status
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed', 'error')),

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    closed_at TIMESTAMPTZ,
    notes TEXT
);

COMMENT ON TABLE walltrack.positions IS 'Aggregate root - Position tracking with PnL (realized/unrealized separation).';
COMMENT ON COLUMN walltrack.positions.exit_strategy_id IS 'Exit strategy snapshot (immutable). NOT NULL - every position must have strategy.';
COMMENT ON COLUMN walltrack.positions.exit_strategy_override IS 'JSONB overrides (ex: {"stop_loss_percent": 25}). Merged with strategy template.';
COMMENT ON COLUMN walltrack.positions.realized_pnl_usd IS 'PnL from partial exits already done. Accumulated: SUM((exit_price - entry_price) * exit_amount).';

CREATE INDEX idx_positions_wallet_id ON walltrack.positions(wallet_id);
CREATE INDEX idx_positions_status ON walltrack.positions(status) WHERE status = 'open';
CREATE INDEX idx_positions_last_price_update ON walltrack.positions(last_price_update_at) WHERE status = 'open';

CREATE TRIGGER positions_updated_at BEFORE UPDATE ON walltrack.positions FOR EACH ROW EXECUTE FUNCTION walltrack.update_updated_at_column();

-- Rollback
-- DROP TABLE IF EXISTS walltrack.positions CASCADE;
