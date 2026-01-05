-- ============================================================================
-- Migration: 006_orders_table.sql (Command Log Pattern)
-- ============================================================================

CREATE TABLE IF NOT EXISTS walltrack.orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Relations
    wallet_id UUID NOT NULL REFERENCES walltrack.wallets(id) ON DELETE CASCADE,
    token_id UUID NOT NULL REFERENCES walltrack.tokens(id),
    position_id UUID REFERENCES walltrack.positions(id) ON DELETE CASCADE,
    signal_id UUID REFERENCES walltrack.signals(id),

    -- Config
    mode TEXT NOT NULL CHECK (mode IN ('simulation', 'live')),
    order_type TEXT NOT NULL CHECK (order_type IN ('entry', 'exit_stop_loss', 'exit_trailing_stop', 'exit_scaling', 'exit_mirror', 'exit_manual')),

    -- Request (what we wanted)
    requested_price NUMERIC(20,10) NOT NULL,
    requested_amount NUMERIC(20,6) NOT NULL,
    requested_value_usd NUMERIC(12,2),
    requested_at TIMESTAMPTZ DEFAULT NOW(),

    -- Execution (what we got)
    executed_price NUMERIC(20,10),
    executed_amount NUMERIC(20,6),
    executed_value_usd NUMERIC(12,2),
    executed_at TIMESTAMPTZ,
    tx_signature TEXT UNIQUE,  -- Idempotency

    -- Slippage (auto-calculated)
    slippage_percent NUMERIC(8,4),

    -- Retry
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    retry_reason TEXT,

    -- Status
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'submitted', 'executed', 'failed', 'cancelled')),

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    execution_duration_ms INTEGER
);

COMMENT ON TABLE walltrack.orders IS 'Command log - Transaction history with retry mechanism.';
COMMENT ON COLUMN walltrack.orders.tx_signature IS 'Solana tx signature. UNIQUE for idempotency.';
COMMENT ON COLUMN walltrack.orders.slippage_percent IS 'Auto-calculated: ((executed - requested) / requested) * 100.';

CREATE INDEX idx_orders_wallet_id ON walltrack.orders(wallet_id);
CREATE INDEX idx_orders_status ON walltrack.orders(status) WHERE status IN ('pending', 'submitted');
CREATE INDEX idx_orders_retry ON walltrack.orders(retry_count, max_retries) WHERE status = 'failed' AND retry_count < max_retries;

CREATE TRIGGER orders_updated_at BEFORE UPDATE ON walltrack.orders FOR EACH ROW EXECUTE FUNCTION walltrack.update_updated_at_column();

-- Rollback
-- DROP TABLE IF EXISTS walltrack.orders CASCADE;
