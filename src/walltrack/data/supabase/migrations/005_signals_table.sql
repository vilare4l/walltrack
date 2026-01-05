-- ============================================================================
-- Migration: 005_signals_table.sql (Event Sourcing - Immutable)
-- ============================================================================

CREATE TABLE IF NOT EXISTS walltrack.signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    wallet_address TEXT NOT NULL,  -- Not FK (can receive signals from non-tracked wallets)
    token_address TEXT NOT NULL,
    signal_type TEXT NOT NULL CHECK (signal_type IN ('swap_detected', 'liquidity_add', 'liquidity_remove', 'other')),
    action TEXT CHECK (action IN ('buy', 'sell')),
    amount NUMERIC(20,6),
    price_usd NUMERIC(20,10),
    value_usd NUMERIC(12,2),

    -- Processing
    processed BOOLEAN NOT NULL DEFAULT false,
    processed_at TIMESTAMPTZ,
    action_taken TEXT,  -- 'position_created', 'rejected_safety', 'ignored_sell', 'circuit_breaker_active'
    rejection_reason TEXT,

    -- Metadata
    received_at TIMESTAMPTZ DEFAULT NOW(),
    helius_signature TEXT,
    raw_payload JSONB
);

COMMENT ON TABLE walltrack.signals IS 'Event sourcing - Audit trail of ALL Helius signals (immutable).';
COMMENT ON COLUMN walltrack.signals.processed IS 'Processed by worker? Worker polls WHERE processed = false.';
COMMENT ON COLUMN walltrack.signals.raw_payload IS 'Raw Helius payload (JSONB) for forensics/debug.';

CREATE INDEX idx_signals_processed ON walltrack.signals(processed, received_at) WHERE processed = false;
CREATE INDEX idx_signals_wallet ON walltrack.signals(wallet_address, received_at DESC);
CREATE INDEX idx_signals_received_at ON walltrack.signals(received_at DESC);

-- Rollback
-- DROP TABLE IF EXISTS walltrack.signals CASCADE;
